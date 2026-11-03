"""
M09.02 Order Book Depth - Service Layer.
Coordinates:
- OrderBookDepthService: End-to-end depth calculation, quality checking, level extraction, and persistence.
- DepthLevelCalculator & DepthBandCalculator.
- Integration with M02 OrderBookSnapshotRecord / ReconstructedOrderBook.
- DepthPersistenceService: Windowed time-weighted stability and coefficient of variation calculations.
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from backend.app.modules.market_microstructure.order_book_depth.calculations import (
    sort_and_validate_levels,
    compute_depth_by_level,
    compute_cumulative_depth,
    compute_depth_imbalance,
    compute_distance_weighted_depth,
    compute_price_band_depth,
    compute_depth_persistence,
)
from backend.app.modules.market_microstructure.order_book_depth.models import (
    DepthCalculationConfig,
    OrderBookDepthSnapshot,
    OrderBookDepthLevel,
    OrderBookDepthBand,
    OrderBookDepthPersistence,
    OrderBookDepthHistoryAggregate,
)
from backend.app.modules.market_microstructure.order_book_depth.repositories.repository import DepthRepository
from backend.app.modules.market_microstructure.order_book_depth.schemas import (
    DirectDepthCalculationRequest,
    DirectDepthLevelInput,
    DepthCalculationConfigCreate,
    OrderBookDepthSnapshotResponse,
    OrderBookDepthLevelResponse,
    OrderBookDepthBandResponse,
    CumulativeDepthResponse,
    DepthImbalanceResponse,
    DepthPersistenceResponse,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OrderBookDepthService:
    """
    Main orchestration engine for M09.02 Order Book Depth.
    """

    DEFAULT_BANDS = [
        (0.0, 5.0, "BAND_0_5_BPS"),
        (5.0, 10.0, "BAND_5_10_BPS"),
        (10.0, 25.0, "BAND_10_25_BPS"),
        (25.0, 50.0, "BAND_25_50_BPS"),
    ]

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = DepthRepository(session)

    async def get_or_create_default_config(self) -> DepthCalculationConfig:
        cfg = await self.repo.get_default_config()
        if cfg:
            return cfg

        config_data = {
            "config_code": "DEFAULT_M09_02_CFG",
            "name": "Standard Institutional 5-Level Depth Policy",
            "level_count": 5,
            "aggregation_mode": "LEVEL_BASED",
            "reference_price_method": "MIDPOINT",
            "weighting_parameter": 0.05,
        }
        cfg_hash = hashlib.sha256(json.dumps(config_data, sort_keys=True).encode()).hexdigest()

        cfg = DepthCalculationConfig(
            config_id=str(uuid.uuid4()),
            config_code="DEFAULT_M09_02_CFG",
            version=1,
            name="Standard Institutional 5-Level Depth Policy",
            description="Default policy computing top 5 levels, exponential decay weighted imbalance, and bps bands.",
            aggregation_mode="LEVEL_BASED",
            level_count=5,
            distance_unit="BPS",
            reference_price_method="MIDPOINT",
            measure_type="QUANTITY_AND_NOTIONAL",
            currency="INR",
            contract_multiplier=Decimal("1.0"),
            weighting_method="EXPONENTIAL_DECAY",
            weighting_parameter=0.05,
            minimum_depth_threshold=Decimal("1000.0"),
            maximum_state_age_seconds=10.0,
            config_hash=cfg_hash,
            status="ACTIVE",
            created_at=utc_now(),
            created_by="SYSTEM",
        )
        await self.repo.create_config(cfg)
        return cfg

    async def create_config(self, req: DepthCalculationConfigCreate, created_by: str = "SYSTEM") -> DepthCalculationConfig:
        config_dict = req.model_dump()
        cfg_hash = hashlib.sha256(json.dumps(config_dict, sort_keys=True, default=str).encode()).hexdigest()

        existing = await self.repo.get_config_by_code(req.config_code)
        version = existing.version + 1 if existing else 1

        cfg = DepthCalculationConfig(
            config_id=str(uuid.uuid4()),
            config_code=req.config_code,
            version=version,
            name=req.name,
            description=req.description,
            instrument_id=req.instrument_id,
            venue=req.venue,
            aggregation_mode=req.aggregation_mode.value,
            level_count=req.level_count,
            distance_unit=req.distance_unit,
            distance_threshold=req.distance_threshold,
            reference_price_method=req.reference_price_method,
            currency=req.currency,
            contract_multiplier=req.contract_multiplier,
            weighting_method=req.weighting_method,
            weighting_parameter=req.weighting_parameter,
            minimum_depth_threshold=req.minimum_depth_threshold,
            maximum_state_age_seconds=req.maximum_state_age_seconds,
            config_hash=cfg_hash,
            status="ACTIVE",
            created_at=utc_now(),
            created_by=created_by,
        )
        return await self.repo.create_config(cfg)

    async def calculate_depth(self, req: DirectDepthCalculationRequest) -> Tuple[OrderBookDepthSnapshot, List[OrderBookDepthLevel], List[OrderBookDepthBand]]:
        """
        Executes depth calculation from input bid and ask levels.
        Validates quality rules, extracts per-level metrics, computes imbalances and price bands.
        """
        # 1. Resolve configuration
        config = None
        if req.config_code:
            config = await self.repo.get_config_by_code(req.config_code)
        if not config:
            config = await self.get_or_create_default_config()

        eval_time = req.event_timestamp or utc_now()
        max_levels = req.level_count or config.level_count

        bids_raw = [{"price": b.price, "quantity": b.quantity, "order_count": b.order_count} for b in req.bids]
        asks_raw = [{"price": a.price, "quantity": a.quantity, "order_count": a.order_count} for a in req.asks]

        # 2. Extract per-level depth & calculate midpoint
        midpoint, proc_bids, proc_asks, status = compute_depth_by_level(
            bids=bids_raw,
            asks=asks_raw,
            contract_multiplier=req.contract_multiplier or config.contract_multiplier,
            tick_size=req.tick_size,
            max_levels=max_levels,
        )

        snap_id = str(uuid.uuid4())
        best_bid_p = proc_bids[0]["price"] if proc_bids else None
        best_ask_p = proc_asks[0]["price"] if proc_asks else None

        # Cumulative totals across considered levels
        bid_tot_q = proc_bids[-1]["cumulative_quantity"] if proc_bids else Decimal("0")
        ask_tot_q = proc_asks[-1]["cumulative_quantity"] if proc_asks else Decimal("0")
        bid_tot_n = proc_bids[-1]["cumulative_notional"] if proc_bids else Decimal("0")
        ask_tot_n = proc_asks[-1]["cumulative_notional"] if proc_asks else Decimal("0")

        # Weighted depth
        decay_param = config.weighting_parameter
        w_bids = compute_distance_weighted_depth(proc_bids, decay_lambda=decay_param) if proc_bids else None
        w_asks = compute_distance_weighted_depth(proc_asks, decay_lambda=decay_param) if proc_asks else None

        # Imbalances
        imbalances = compute_depth_imbalance(
            bid_quantity=bid_tot_q,
            ask_quantity=ask_tot_q,
            bid_notional=bid_tot_n,
            ask_notional=ask_tot_n,
            weighted_bids=w_bids,
            weighted_asks=w_asks,
        )

        # Build Snapshot Entity
        snapshot = OrderBookDepthSnapshot(
            depth_snapshot_id=snap_id,
            instrument_id=req.instrument_id,
            listing_id=req.listing_id,
            exchange=req.exchange,
            venue=req.venue,
            book_scope=req.book_scope,
            source_feed_id=req.source_feed_id,
            source_book_snapshot_id=req.source_book_snapshot_id,
            sequence_number=req.sequence_number,
            event_timestamp=eval_time,
            received_timestamp=utc_now(),
            calculation_timestamp=utc_now(),
            best_bid_price=best_bid_p,
            best_ask_price=best_ask_p,
            midpoint_price=midpoint,
            bid_level_count=len(proc_bids),
            ask_level_count=len(proc_asks),
            bid_total_quantity=bid_tot_q,
            ask_total_quantity=ask_tot_q,
            bid_total_notional=bid_tot_n,
            ask_total_notional=ask_tot_n,
            quantity_imbalance=imbalances["quantity_imbalance"],
            notional_imbalance=imbalances["notional_imbalance"],
            weighted_imbalance=imbalances["weighted_imbalance"],
            depth_quality_status=status,
            calculation_config_id=config.config_id,
            calculation_config_version=config.version,
        )

        # Build Per-Level Entities
        level_entities: List[OrderBookDepthLevel] = []
        for b in proc_bids:
            level_entities.append(OrderBookDepthLevel(
                level_id=str(uuid.uuid4()),
                depth_snapshot_id=snap_id,
                side="BID",
                level_index=b["level_index"],
                price=b["price"],
                displayed_quantity=b["quantity"],
                displayed_notional=b["notional"],
                cumulative_quantity=b["cumulative_quantity"],
                cumulative_notional=b["cumulative_notional"],
                distance_from_midpoint=b["distance_from_midpoint"],
                distance_bps=b["distance_bps"],
                distance_ticks=b["distance_ticks"],
                order_count=b.get("order_count"),
                created_at=utc_now(),
            ))

        for a in proc_asks:
            level_entities.append(OrderBookDepthLevel(
                level_id=str(uuid.uuid4()),
                depth_snapshot_id=snap_id,
                side="ASK",
                level_index=a["level_index"],
                price=a["price"],
                displayed_quantity=a["quantity"],
                displayed_notional=a["notional"],
                cumulative_quantity=a["cumulative_quantity"],
                cumulative_notional=a["cumulative_notional"],
                distance_from_midpoint=a["distance_from_midpoint"],
                distance_bps=a["distance_bps"],
                distance_ticks=a["distance_ticks"],
                order_count=a.get("order_count"),
                created_at=utc_now(),
            ))

        # Build Price-Band Entities
        band_entities: List[OrderBookDepthBand] = []
        if status == "VALID" and proc_bids and proc_asks:
            bands_data = compute_price_band_depth(
                bid_levels=proc_bids,
                ask_levels=proc_asks,
                bands=self.DEFAULT_BANDS,
                contract_multiplier=req.contract_multiplier or config.contract_multiplier,
            )
            for bd in bands_data:
                band_entities.append(OrderBookDepthBand(
                    band_record_id=str(uuid.uuid4()),
                    depth_snapshot_id=snap_id,
                    band_id=bd["band_id"],
                    band_lower_bound=bd["band_lower_bound"],
                    band_upper_bound=bd["band_upper_bound"],
                    distance_unit=bd["distance_unit"],
                    bid_quantity=bd["bid_quantity"],
                    ask_quantity=bd["ask_quantity"],
                    bid_notional=bd["bid_notional"],
                    ask_notional=bd["ask_notional"],
                    bid_level_count=bd["bid_level_count"],
                    ask_level_count=bd["ask_level_count"],
                    quantity_imbalance=bd["quantity_imbalance"],
                    notional_imbalance=bd["notional_imbalance"],
                    created_at=utc_now(),
                ))

        if req.persist_snapshot:
            await self.repo.save_snapshot(snapshot, level_entities, band_entities)

        return snapshot, level_entities, band_entities

    async def resolve_from_m02_and_calculate(
        self,
        instrument_id: str,
        venue: str = "NSE",
        exchange: str = "NSE",
    ) -> Optional[Tuple[OrderBookDepthSnapshot, List[OrderBookDepthLevel], List[OrderBookDepthBand]]]:
        """
        Consumes authoritative reconstructed L2 order book snapshot from M02 (OrderBookSnapshotRecord)
        and computes displayed depth without duplicating order-book reconstruction.
        """
        from backend.app.modules.market_data_ingestion.persistence.models import OrderBookSnapshotRecord
        stmt = select(OrderBookSnapshotRecord).where(
            OrderBookSnapshotRecord.instrument_id == instrument_id,
        ).order_by(desc(OrderBookSnapshotRecord.snapshot_timestamp))
        res = await self.session.execute(stmt)
        record = res.scalars().first()
        if not record:
            return None

        bid_inputs = [
            DirectDepthLevelInput(
                price=Decimal(str(b["price"])),
                quantity=Decimal(str(b["quantity"])),
                order_count=b.get("order_count"),
            )
            for b in record.bid_levels
        ]
        ask_inputs = [
            DirectDepthLevelInput(
                price=Decimal(str(a["price"])),
                quantity=Decimal(str(a["quantity"])),
                order_count=a.get("order_count"),
            )
            for a in record.ask_levels
        ]

        req = DirectDepthCalculationRequest(
            instrument_id=instrument_id,
            exchange=record.exchange or exchange,
            venue=venue,
            book_scope="VENUE_SPECIFIC",
            source_feed_id=record.feed_id,
            source_book_snapshot_id=record.event_id,
            sequence_number=record.sequence_number,
            event_timestamp=record.snapshot_timestamp,
            bids=bid_inputs,
            asks=ask_inputs,
            persist_snapshot=True,
        )
        return await self.calculate_depth(req)

    async def compute_persistence_window(
        self,
        instrument_id: str,
        start_time: datetime,
        end_time: datetime,
        venue: Optional[str] = None,
        minimum_depth_threshold: Optional[Decimal] = None,
        target_price: Optional[Decimal] = None,
    ) -> OrderBookDepthPersistence:
        """
        Calculates time-weighted depth persistence, coefficient of variation, and stability score over a window.
        """
        snapshots = await self.repo.query_snapshots(
            instrument_id=instrument_id,
            start_time=start_time,
            end_time=end_time,
            venue=venue,
            limit=2000,
        )

        obs_dicts = []
        for s in snapshots:
            obs_dicts.append({
                "timestamp": s.event_timestamp,
                "bid_depth": s.bid_total_quantity,
                "ask_depth": s.ask_total_quantity,
                "quality_status": s.depth_quality_status,
            })

        duration_sec = (end_time - start_time).total_seconds()
        res = compute_depth_persistence(
            observations=obs_dicts,
            session_start=start_time,
            session_end=end_time,
            minimum_depth_threshold=minimum_depth_threshold,
            target_price=target_price,
        )

        persistence = OrderBookDepthPersistence(
            persistence_id=str(uuid.uuid4()),
            instrument_id=instrument_id,
            venue=venue or (snapshots[0].venue if snapshots else "NSE"),
            config_id="DEFAULT_M09_02_CFG",
            config_version=1,
            window_start=start_time,
            window_end=end_time,
            window_duration_seconds=duration_sec,
            bid_time_weighted_mean=Decimal(str(res["bid_time_weighted_mean"])) if res["bid_time_weighted_mean"] is not None else None,
            ask_time_weighted_mean=Decimal(str(res["ask_time_weighted_mean"])) if res["ask_time_weighted_mean"] is not None else None,
            bid_time_weighted_stddev=Decimal(str(res["bid_time_weighted_stddev"])) if res["bid_time_weighted_stddev"] is not None else None,
            ask_time_weighted_stddev=Decimal(str(res["ask_time_weighted_stddev"])) if res["ask_time_weighted_stddev"] is not None else None,
            bid_depth_cv=res["bid_depth_cv"],
            ask_depth_cv=res["ask_depth_cv"],
            bid_threshold_persistence=res["bid_threshold_persistence"],
            ask_threshold_persistence=res["ask_threshold_persistence"],
            price_level_persistence=res["price_level_persistence"],
            depth_stability_score=res["depth_stability_score"],
            valid_duration_seconds=res["valid_duration_seconds"],
            expected_duration_seconds=res["expected_duration_seconds"],
            coverage_percentage=res["coverage_percentage"],
            valid_state_count=res["valid_state_count"],
            quality_status="SUFFICIENT" if res["coverage_percentage"] >= 70.0 else "INSUFFICIENT_COVERAGE",
            created_at=utc_now(),
        )
        return await self.repo.save_persistence(persistence)
