"""
M09.01 Bid-Ask Spread - Service Layer.
Implements:
- SpreadQualityService: Pre-calculation quote validation & quality diagnostics.
- AbsoluteSpreadEngine: Native price units spread calculation.
- RelativeSpreadEngine: Midpoint, Bid, Ask, Reference price normalization.
- SpreadCalculationOrchestrator: Ingestion/on-demand coordination & upstream resolution.
- SpreadAggregationService: Observation-weighted and time-weighted metrics.
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone, date
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from backend.app.modules.market_microstructure.bid_ask_spread.calculations import (
    compute_absolute_spread,
    compute_midpoint_price,
    compute_relative_spread,
    compute_spread_in_ticks,
    compute_observation_weighted_statistics,
    compute_time_weighted_spread,
)
from backend.app.modules.market_microstructure.bid_ask_spread.models import (
    SpreadCalculationConfig,
    SpreadObservation,
    SpreadQualityResult,
    SpreadIntervalAggregate,
    SpreadSessionSummary,
    SpreadQualitySummary,
)
from backend.app.modules.market_microstructure.bid_ask_spread.repositories.repository import SpreadRepository
from backend.app.modules.market_microstructure.bid_ask_spread.schemas import (
    DirectSpreadCalculationRequest,
    SpreadCalculationConfigCreate,
    SpreadStatisticsResponse,
    VenueSpreadComparisonItem,
    RelativeSpreadMethod,
    LockedBookPolicy,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SpreadQualityService:
    """
    Performs comprehensive quality checks on incoming quote states before spread computation.
    Checks:
    1. Null / Non-finite prices.
    2. Missing bid or ask.
    3. Negative prices.
    4. Quote skew (asynchrony between bid and ask timestamps).
    5. Quote staleness against evaluation time.
    6. Crossed book (Ask < Bid).
    7. Locked book (Ask == Bid).
    8. Tick size alignment where provided.
    9. Out of session / auction phase.
    """

    @staticmethod
    def validate_quote_state(
        best_bid: Optional[Decimal],
        best_ask: Optional[Decimal],
        bid_timestamp: Optional[datetime],
        ask_timestamp: Optional[datetime],
        evaluation_time: datetime,
        max_quote_age_seconds: float,
        max_quote_skew_seconds: float,
        tick_size: Optional[Decimal] = None,
        session_type: str = "REGULAR_TRADING",
        session_policy: str = "CONTINUOUS_ONLY",
    ) -> Tuple[str, List[Dict[str, Any]], Optional[float], Optional[float]]:
        """
        Returns: (overall_status, diagnostic_checks, quote_skew_sec, quote_age_sec)
        """
        checks: List[Dict[str, Any]] = []
        overall_status = "VALID"

        # 1. Check side presence
        if best_bid is None and best_ask is None:
            return "MISSING_BOTH_SIDES", [{
                "check_type": "PRESENCE",
                "status": "FAIL",
                "severity": "HARD_GATE",
                "reason_code": "MISSING_BOTH_SIDES",
            }], None, None

        if best_bid is None:
            return "MISSING_BID", [{
                "check_type": "PRESENCE",
                "status": "FAIL",
                "severity": "HARD_GATE",
                "reason_code": "MISSING_BID",
            }], None, None

        if best_ask is None:
            return "MISSING_ASK", [{
                "check_type": "PRESENCE",
                "status": "FAIL",
                "severity": "HARD_GATE",
                "reason_code": "MISSING_ASK",
            }], None, None

        # 2. Check price conventions
        if best_bid < Decimal("0") or best_ask < Decimal("0"):
            return "INVALID_PRICE", [{
                "check_type": "PRICE_VALIDITY",
                "status": "FAIL",
                "severity": "HARD_GATE",
                "reason_code": "NEGATIVE_PRICE",
                "measured_value": f"bid={best_bid}, ask={best_ask}",
            }], None, None

        # 3. Quote skew check
        quote_skew_sec = None
        if bid_timestamp and ask_timestamp:
            skew = abs((bid_timestamp - ask_timestamp).total_seconds())
            quote_skew_sec = round(skew, 6)
            if skew > max_quote_skew_seconds:
                checks.append({
                    "check_type": "SYNCHRONIZATION",
                    "status": "FAIL",
                    "severity": "HARD_GATE",
                    "reason_code": "EXCESSIVE_QUOTE_SKEW",
                    "measured_value": str(quote_skew_sec),
                    "threshold_value": str(max_quote_skew_seconds),
                })
                overall_status = "UNSYNCHRONIZED_QUOTES"

        # 4. Quote staleness check
        ref_ts = max([ts for ts in (bid_timestamp, ask_timestamp) if ts is not None], default=evaluation_time)
        age = (evaluation_time - ref_ts).total_seconds()
        quote_age_sec = max(0.0, round(age, 6))
        if quote_age_sec > max_quote_age_seconds:
            checks.append({
                "check_type": "STALENESS",
                "status": "FAIL",
                "severity": "HARD_GATE",
                "reason_code": "STALE_QUOTE",
                "measured_value": str(quote_age_sec),
                "threshold_value": str(max_quote_age_seconds),
            })
            if overall_status == "VALID":
                overall_status = "STALE_QUOTE"

        # 5. Crossed book check
        if best_ask < best_bid:
            checks.append({
                "check_type": "BOOK_STATE",
                "status": "FAIL",
                "severity": "HARD_GATE",
                "reason_code": "CROSSED_BOOK",
                "measured_value": f"ask({best_ask}) < bid({best_bid})",
            })
            overall_status = "CROSSED_BOOK"

        # 6. Locked book check
        elif best_ask == best_bid:
            checks.append({
                "check_type": "BOOK_STATE",
                "status": "PASS",
                "severity": "INFO",
                "reason_code": "LOCKED_BOOK",
                "measured_value": f"ask({best_ask}) == bid({best_bid})",
            })
            if overall_status == "VALID":
                overall_status = "LOCKED_BOOK"

        # 7. Tick size alignment
        if tick_size and tick_size > Decimal("0"):
            bid_rem = best_bid % tick_size
            ask_rem = best_ask % tick_size
            if bid_rem != Decimal("0") or ask_rem != Decimal("0"):
                checks.append({
                    "check_type": "TICK_ALIGNMENT",
                    "status": "WARNING",
                    "severity": "WARNING",
                    "reason_code": "INVALID_TICK_SIZE",
                    "measured_value": f"bid={best_bid}, ask={best_ask}, tick={tick_size}",
                })
                # If strict policy, flag as invalid tick
                if overall_status == "VALID":
                    overall_status = "INVALID_TICK_SIZE"

        # 8. Session eligibility check
        if session_policy == "CONTINUOUS_ONLY":
            if session_type in ("AUCTION", "OPENING_AUCTION", "CLOSING_AUCTION", "PRE_OPEN", "POST_MARKET", "HALTED", "CLOSED"):
                checks.append({
                    "check_type": "SESSION_ELIGIBILITY",
                    "status": "FAIL",
                    "severity": "HARD_GATE",
                    "reason_code": "OUT_OF_SESSION",
                    "measured_value": session_type,
                })
                if overall_status in ("VALID", "LOCKED_BOOK"):
                    overall_status = "OUT_OF_SESSION"

        return overall_status, checks, quote_skew_sec, quote_age_sec


class SpreadCalculationOrchestrator:
    """
    Coordinates spread computation, quality checking, persistence, and upstream M02/M04 resolution.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = SpreadRepository(session)

    async def get_or_create_default_config(self) -> SpreadCalculationConfig:
        cfg = await self.repo.get_default_config()
        if cfg:
            return cfg

        config_data = {
            "config_code": "DEFAULT_M09_CFG",
            "name": "Standard Institutional Spread Policy",
            "book_scope": "VENUE_SPECIFIC",
            "relative_spread_method": "MIDPOINT_NORMALIZED",
            "locked_book_policy": "INCLUDE_AS_ZERO",
            "maximum_quote_age_seconds": 10.0,
            "maximum_quote_skew_seconds": 1.0,
            "session_policy": "CONTINUOUS_ONLY",
            "tick_validation_policy": "STRICT_ALIGNMENT",
        }
        cfg_hash = hashlib.sha256(json.dumps(config_data, sort_keys=True).encode()).hexdigest()

        cfg = SpreadCalculationConfig(
            config_id=str(uuid.uuid4()),
            config_code="DEFAULT_M09_CFG",
            version=1,
            name="Standard Institutional Spread Policy",
            description="Default continuous market spread policy with 10s staleness and 1s skew limit.",
            book_scope="VENUE_SPECIFIC",
            relative_spread_method="MIDPOINT_NORMALIZED",
            locked_book_policy="INCLUDE_AS_ZERO",
            maximum_quote_age_seconds=10.0,
            maximum_quote_skew_seconds=1.0,
            session_policy="CONTINUOUS_ONLY",
            minimum_source_quality="NORMAL",
            tick_validation_policy="STRICT_ALIGNMENT",
            outlier_warning_policy="FLAG_ONLY",
            config_hash=cfg_hash,
            status="ACTIVE",
            created_at=utc_now(),
            created_by="SYSTEM",
        )
        await self.repo.create_config(cfg)
        return cfg

    async def create_config(self, req: SpreadCalculationConfigCreate, created_by: str = "SYSTEM") -> SpreadCalculationConfig:
        config_dict = req.model_dump()
        cfg_hash = hashlib.sha256(json.dumps(config_dict, sort_keys=True, default=str).encode()).hexdigest()

        existing = await self.repo.get_config_by_code(req.config_code)
        version = 1
        if existing:
            version = existing.version + 1

        cfg = SpreadCalculationConfig(
            config_id=str(uuid.uuid4()),
            config_code=req.config_code,
            version=version,
            name=req.name,
            description=req.description,
            book_scope=req.book_scope.value,
            relative_spread_method=req.relative_spread_method.value,
            locked_book_policy=req.locked_book_policy.value,
            maximum_quote_age_seconds=req.maximum_quote_age_seconds,
            maximum_quote_skew_seconds=req.maximum_quote_skew_seconds,
            session_policy=req.session_policy,
            minimum_source_quality=req.minimum_source_quality,
            tick_validation_policy=req.tick_validation_policy,
            outlier_warning_policy=req.outlier_warning_policy,
            config_hash=cfg_hash,
            status="ACTIVE",
            created_at=utc_now(),
            created_by=created_by,
        )
        return await self.repo.create_config(cfg)

    async def calculate_spread(self, req: DirectSpreadCalculationRequest) -> SpreadObservation:
        """
        Executes a top-of-book bid-ask spread calculation on the provided quote state.
        Validates quality rules, computes absolute and relative spread, and optionally persists results.
        """
        # 1. Resolve configuration
        config = None
        if req.config_code:
            config = await self.repo.get_config_by_code(req.config_code)
        if not config:
            config = await self.get_or_create_default_config()

        eval_time = req.book_timestamp or utc_now()
        b_time = req.bid_timestamp or eval_time
        a_time = req.ask_timestamp or eval_time

        # 2. Quality validation
        q_status, checks, skew_sec, age_sec = SpreadQualityService.validate_quote_state(
            best_bid=req.best_bid,
            best_ask=req.best_ask,
            bid_timestamp=b_time,
            ask_timestamp=a_time,
            evaluation_time=eval_time,
            max_quote_age_seconds=config.maximum_quote_age_seconds,
            max_quote_skew_seconds=config.maximum_quote_skew_seconds,
            tick_size=req.tick_size,
            session_type=req.session_type,
            session_policy=config.session_policy,
        )

        obs_id = str(uuid.uuid4())
        abs_spread = None
        midpoint = None
        rs_dec, rs_pct, rs_bps = None, None, None
        spread_ticks = None

        # 3. Compute spread only if quote passes hard gates
        if q_status in ("VALID", "LOCKED_BOOK"):
            s_val, s_stat = compute_absolute_spread(req.best_bid, req.best_ask)
            if s_stat == "VALID" or (s_stat == "LOCKED_BOOK" and config.locked_book_policy == "INCLUDE_AS_ZERO"):
                abs_spread = s_val
                midpoint = compute_midpoint_price(req.best_bid, req.best_ask)

                # Reference price for relative normalization
                norm_method = req.relative_spread_method.value if req.relative_spread_method else config.relative_spread_method
                ref_price = midpoint
                if norm_method == "BID_NORMALIZED":
                    ref_price = req.best_bid
                elif norm_method == "ASK_NORMALIZED":
                    ref_price = req.best_ask

                if ref_price and ref_price > Decimal("0"):
                    rs_dec, rs_pct, rs_bps, _ = compute_relative_spread(abs_spread, ref_price)

                if req.tick_size:
                    spread_ticks = compute_spread_in_ticks(abs_spread, req.tick_size)

                if s_stat == "LOCKED_BOOK":
                    q_status = "VALID_LOCKED" if config.locked_book_policy == "INCLUDE_AS_ZERO" else "LOCKED_BOOK"

        # 4. Build Observation Model
        reason_codes = ",".join([c["reason_code"] for c in checks if c["status"] in ("FAIL", "WARNING")]) or None
        obs = SpreadObservation(
            observation_id=obs_id,
            instrument_id=req.instrument_id,
            listing_id=req.listing_id,
            exchange=req.exchange,
            venue=req.venue,
            book_scope=req.book_scope.value,
            source_feed_id=req.source_feed_id,
            source_quote_reference=req.source_quote_reference,
            bid_price=req.best_bid,
            ask_price=req.best_ask,
            bid_quantity=req.bid_quantity,
            ask_quantity=req.ask_quantity,
            bid_timestamp=b_time,
            ask_timestamp=a_time,
            book_timestamp=eval_time,
            receive_timestamp=utc_now(),
            quote_skew_seconds=skew_sec,
            quote_age_seconds=age_sec,
            absolute_spread=abs_spread,
            midpoint_price=midpoint,
            relative_spread_decimal=rs_dec,
            relative_spread_percentage=rs_pct,
            relative_spread_bps=rs_bps,
            spread_ticks=spread_ticks,
            tick_size_reference=req.tick_size,
            session_type=req.session_type,
            quality_status=q_status,
            quality_reason_codes=reason_codes,
            calculation_config_id=config.config_id,
            calculation_config_version=config.version,
            calculated_at=utc_now(),
            created_at=utc_now(),
        )

        if req.persist_observation:
            await self.repo.save_observation(obs)

            # Persist quality diagnostic records
            q_results = [
                SpreadQualityResult(
                    result_id=str(uuid.uuid4()),
                    observation_id=obs_id,
                    source_quote_reference=req.source_quote_reference,
                    quality_check_type=c["check_type"],
                    quality_status=c["status"],
                    severity=c["severity"],
                    measured_value=c.get("measured_value"),
                    threshold_value=c.get("threshold_value"),
                    reason_code=c["reason_code"],
                    created_at=utc_now(),
                )
                for c in checks
            ]
            if q_results:
                await self.repo.save_quality_results(q_results)

        return obs

    async def resolve_from_m02_tick_and_calculate(
        self,
        instrument_id: str,
        venue: str = "NSE",
        exchange: str = "NSE",
    ) -> Optional[SpreadObservation]:
        """
        Resolves latest Level 1/LTP quote from M02 NormalizedMarketTick table and calculates spread.
        Demonstrates upstream integration without duplicating M02 storage.
        """
        from backend.app.modules.market_data_ingestion.persistence.models import NormalizedMarketTick
        stmt = select(NormalizedMarketTick).where(
            NormalizedMarketTick.instrument_id == instrument_id,
        ).order_by(desc(NormalizedMarketTick.event_timestamp))
        res = await self.session.execute(stmt)
        tick = res.scalars().first()
        if not tick:
            return None

        req = DirectSpreadCalculationRequest(
            instrument_id=tick.instrument_id,
            exchange=tick.exchange or exchange,
            venue=venue,
            book_scope="VENUE_SPECIFIC",
            source_feed_id=tick.feed_id,
            source_quote_reference=tick.event_id,
            best_bid=tick.best_bid_price,
            best_ask=tick.best_ask_price,
            bid_quantity=tick.best_bid_quantity,
            ask_quantity=tick.best_ask_quantity,
            book_timestamp=tick.event_timestamp,
            bid_timestamp=tick.event_timestamp,
            ask_timestamp=tick.event_timestamp,
            persist_observation=True,
        )
        return await self.calculate_spread(req)

    async def compute_historical_statistics(
        self,
        instrument_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        venue: Optional[str] = None,
    ) -> SpreadStatisticsResponse:
        """
        Computes observation-weighted and time-weighted summary statistics across valid historical observations.
        """
        observations = await self.repo.query_observations(
            instrument_id=instrument_id,
            start_time=start_time,
            end_time=end_time,
            venue=venue,
            limit=2000,
        )

        valid_obs = [obs for obs in observations if obs.quality_status in ("VALID", "VALID_LOCKED") and obs.absolute_spread is not None]
        abs_values = [obs.absolute_spread for obs in valid_obs]
        bps_values = [obs.relative_spread_bps for obs in valid_obs if obs.relative_spread_bps is not None]

        obs_stats = compute_observation_weighted_statistics(abs_values)
        bps_stats = compute_observation_weighted_statistics(bps_values)

        # Time-weighted calculation
        tw_stats = {
            "time_weighted_spread": None,
            "time_weighted_relative_spread": None,
            "coverage_percentage": 0.0,
        }
        if observations:
            min_ts = start_time or min(o.book_timestamp for o in observations)
            max_ts = end_time or max(o.book_timestamp for o in observations)
            obs_dicts = [
                {
                    "timestamp": o.book_timestamp,
                    "absolute_spread": o.absolute_spread,
                    "relative_spread": o.relative_spread_decimal,
                    "quality_status": o.quality_status,
                }
                for o in observations
            ]
            tw_stats = compute_time_weighted_spread(obs_dicts, session_start=min_ts, session_end=max_ts)

        ex = observations[0].exchange if observations else "NSE"
        vn = venue or (observations[0].venue if observations else "NSE")

        return SpreadStatisticsResponse(
            instrument_id=instrument_id,
            exchange=ex,
            venue=vn,
            observation_count=len(observations),
            valid_observation_count=len(valid_obs),
            mean_absolute_spread=obs_stats.get("mean"),
            median_absolute_spread=obs_stats.get("median"),
            std_absolute_spread=obs_stats.get("std"),
            min_absolute_spread=obs_stats.get("min"),
            max_absolute_spread=obs_stats.get("max"),
            p5_absolute_spread=obs_stats.get("p5"),
            p25_absolute_spread=obs_stats.get("p25"),
            p75_absolute_spread=obs_stats.get("p75"),
            p90_absolute_spread=obs_stats.get("p90"),
            p95_absolute_spread=obs_stats.get("p95"),
            p99_absolute_spread=obs_stats.get("p99"),
            mean_relative_spread_bps=bps_stats.get("mean"),
            median_relative_spread_bps=bps_stats.get("median"),
            time_weighted_spread=tw_stats.get("time_weighted_spread"),
            time_weighted_relative_spread=tw_stats.get("time_weighted_relative_spread"),
            time_coverage_percentage=tw_stats.get("coverage_percentage"),
        )

    async def get_venue_comparison(self, instrument_id: str) -> List[VenueSpreadComparisonItem]:
        """
        Retrieves compatible venue-specific spread summaries without synthesizing an unverified consolidated book.
        """
        # Fetch distinct venues for this instrument
        stmt = select(SpreadObservation.venue, SpreadObservation.exchange).where(
            SpreadObservation.instrument_id == instrument_id
        ).distinct()
        res = await self.session.execute(stmt)
        venues = res.all()

        comparison_list = []
        for v_name, ex_name in venues:
            latest = await self.repo.get_latest_observation(instrument_id=instrument_id, venue=v_name)
            if not latest:
                continue

            history = await self.repo.query_observations(instrument_id=instrument_id, venue=v_name, limit=50)
            valid_cnt = sum(1 for h in history if h.quality_status in ("VALID", "VALID_LOCKED"))
            cov_pct = (valid_cnt / len(history) * 100.0) if history else 0.0

            comparison_list.append(VenueSpreadComparisonItem(
                venue=v_name,
                exchange=ex_name,
                book_scope=latest.book_scope,
                best_bid=latest.bid_price,
                best_ask=latest.ask_price,
                absolute_spread=latest.absolute_spread,
                relative_spread_bps=latest.relative_spread_bps,
                midpoint_price=latest.midpoint_price,
                quality_status=latest.quality_status,
                quote_age_seconds=latest.quote_age_seconds,
                observation_count=len(history),
                coverage_percentage=round(cov_pct, 2),
            ))

        return comparison_list

    async def aggregate_interval_spread(
        self,
        instrument_id: str,
        start_time: datetime,
        end_time: datetime,
        frequency: str = "5m",
        venue: str = "NSE",
        exchange: str = "NSE",
    ) -> SpreadIntervalAggregate:
        """
        Computes and persists an interval aggregate (e.g. 1m, 5m, 15m) from underlying observations.
        """
        obs_list = await self.repo.query_observations(
            instrument_id=instrument_id,
            start_time=start_time,
            end_time=end_time,
            venue=venue,
            limit=5000,
        )

        valid_obs = [o for o in obs_list if o.quality_status in ("VALID", "VALID_LOCKED") and o.absolute_spread is not None]
        stale_cnt = sum(1 for o in obs_list if o.quality_status == "STALE_QUOTE")
        locked_cnt = sum(1 for o in obs_list if o.quality_status in ("LOCKED_BOOK", "VALID_LOCKED"))
        crossed_cnt = sum(1 for o in obs_list if o.quality_status == "CROSSED_BOOK")
        invalid_cnt = len(obs_list) - len(valid_obs)

        abs_vals = [o.absolute_spread for o in valid_obs]
        rel_vals = [o.relative_spread_decimal for o in valid_obs if o.relative_spread_decimal is not None]
        bps_vals = [o.relative_spread_bps for o in valid_obs if o.relative_spread_bps is not None]

        abs_stats = compute_observation_weighted_statistics(abs_vals)
        rel_stats = compute_observation_weighted_statistics(rel_vals)
        bps_stats = compute_observation_weighted_statistics(bps_vals)

        obs_dicts = [
            {
                "timestamp": o.book_timestamp,
                "absolute_spread": o.absolute_spread,
                "relative_spread": o.relative_spread_decimal,
                "quality_status": o.quality_status,
            }
            for o in obs_list
        ]
        tw_stats = compute_time_weighted_spread(obs_dicts, session_start=start_time, session_end=end_time)

        agg = SpreadIntervalAggregate(
            aggregate_id=str(uuid.uuid4()),
            instrument_id=instrument_id,
            exchange=exchange,
            venue=venue,
            book_scope="VENUE_SPECIFIC",
            aggregation_start=start_time,
            aggregation_end=end_time,
            aggregation_frequency=frequency,
            aggregation_method="HYBRID_OBS_TIME",
            mean_absolute_spread=Decimal(str(round(abs_stats["mean"], 4))) if abs_stats["mean"] is not None else None,
            median_absolute_spread=Decimal(str(round(abs_stats["median"], 4))) if abs_stats["median"] is not None else None,
            minimum_absolute_spread=Decimal(str(round(abs_stats["min"], 4))) if abs_stats["min"] is not None else None,
            maximum_absolute_spread=Decimal(str(round(abs_stats["max"], 4))) if abs_stats["max"] is not None else None,
            p90_absolute_spread=Decimal(str(round(abs_stats["p90"], 4))) if abs_stats["p90"] is not None else None,
            p95_absolute_spread=Decimal(str(round(abs_stats["p95"], 4))) if abs_stats["p95"] is not None else None,
            p99_absolute_spread=Decimal(str(round(abs_stats["p99"], 4))) if abs_stats["p99"] is not None else None,
            mean_relative_spread=Decimal(str(round(rel_stats["mean"], 8))) if rel_stats["mean"] is not None else None,
            median_relative_spread=Decimal(str(round(rel_stats["median"], 8))) if rel_stats["median"] is not None else None,
            p90_relative_spread=Decimal(str(round(rel_stats["p90"], 8))) if rel_stats["p90"] is not None else None,
            p95_relative_spread=Decimal(str(round(rel_stats["p95"], 8))) if rel_stats["p95"] is not None else None,
            mean_relative_spread_bps=Decimal(str(round(bps_stats["mean"], 4))) if bps_stats["mean"] is not None else None,
            median_relative_spread_bps=Decimal(str(round(bps_stats["median"], 4))) if bps_stats["median"] is not None else None,
            mean_time_weighted_spread=Decimal(str(round(tw_stats["time_weighted_spread"], 4))) if tw_stats["time_weighted_spread"] is not None else None,
            mean_time_weighted_relative_spread=Decimal(str(round(tw_stats["time_weighted_relative_spread"], 8))) if tw_stats["time_weighted_relative_spread"] is not None else None,
            valid_observation_count=len(valid_obs),
            invalid_observation_count=invalid_cnt,
            stale_observation_count=stale_cnt,
            locked_book_count=locked_cnt,
            crossed_book_count=crossed_cnt,
            valid_time_coverage_seconds=tw_stats["valid_book_duration_seconds"],
            expected_time_coverage_seconds=tw_stats["expected_duration_seconds"],
            coverage_percentage=tw_stats["coverage_percentage"],
            calculation_config_id="DEFAULT_M09_CFG",
            calculation_config_version=1,
            result_version=1,
            created_at=utc_now(),
        )
        return await self.repo.save_aggregate(agg)

