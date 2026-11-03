"""
Service layer for M09.08 Order Book Imbalance.
Orchestrates:
- Point-in-time order book imbalance calculations across depths and weightings
- Persistence estimation over observation sequences
- Reversal detection with hysteresis
- Multi-venue comparison
- Configuration lifecycle
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.market_microstructure.order_book_imbalance.calculations.imbalance_math import (
    OrderBookLevelData,
    ImbalanceSnapshotResult,
    TimeSeriesObservation,
    OrderBookImbalanceMath,
)
from backend.app.modules.market_microstructure.order_book_imbalance.models.imbalance_models import (
    OrderBookImbalanceConfig,
    OrderBookImbalanceSnapshot,
    OrderBookImbalancePersistenceResult,
    OrderBookImbalanceReversalEvent,
    OrderBookImbalanceMonitoringSnapshot,
)
from backend.app.modules.market_microstructure.order_book_imbalance.repositories.imbalance_repository import (
    OrderBookImbalanceRepository,
)
from backend.app.modules.market_microstructure.order_book_imbalance.schemas.imbalance_schemas import (
    ImbalanceConfigCreateRequest,
    ImbalanceConfigResponse,
    ImbalanceCalculateRequest,
    ImbalanceSnapshotResponse,
    PersistenceAnalysisRequest,
    PersistenceResponse,
    ReversalDetectionRequest,
    ReversalEventSchema,
    ReversalDetectionResponse,
    VenueComparisonRequest,
    VenueComparisonResponse,
)


class OrderBookImbalanceService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = OrderBookImbalanceRepository(session)

    async def get_or_create_default_config(self) -> OrderBookImbalanceConfig:
        cfg = await self.repo.get_default_config()
        if cfg:
            return cfg

        default_cfg = OrderBookImbalanceConfig(
            config_id="CFG-DEFAULT-IMBALANCE",
            config_name="Default 5-Level Imbalance Configuration",
            description="Standard 5-level equal-weighted order book imbalance configuration",
            depth_level_count=5,
            weighting_method="EQUAL",
            decay_parameter=Decimal("0.5000"),
            distance_unit="PRICE",
            persistence_threshold=Decimal("0.2000"),
            reversal_entry_threshold=Decimal("0.2000"),
            reversal_exit_threshold=Decimal("0.0500"),
            version=1,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        return await self.repo.save_config(default_cfg)

    async def create_config(self, req: ImbalanceConfigCreateRequest) -> ImbalanceConfigResponse:
        config_id = f"CFG-{uuid.uuid4().hex[:10].upper()}"
        now = datetime.now(timezone.utc)
        cfg = OrderBookImbalanceConfig(
            config_id=config_id,
            config_name=req.config_name,
            description=req.description,
            depth_level_count=req.depth_level_count,
            weighting_method=req.weighting_method,
            decay_parameter=req.decay_parameter,
            distance_unit=req.distance_unit,
            custom_weights_json=str(req.custom_weights) if req.custom_weights else None,
            persistence_threshold=req.persistence_threshold,
            reversal_entry_threshold=req.reversal_entry_threshold,
            reversal_exit_threshold=req.reversal_exit_threshold,
            version=1,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        await self.repo.save_config(cfg)
        return ImbalanceConfigResponse.model_validate(cfg)

    async def calculate_and_save_imbalance(self, req: ImbalanceCalculateRequest) -> ImbalanceSnapshotResponse:
        cfg = await self.get_or_create_default_config()
        config_id = req.config_id or cfg.config_id

        # Convert level inputs
        domain_levels: List[OrderBookLevelData] = [
            OrderBookLevelData(
                level_index=lvl.level_index,
                bid_price=lvl.bid_price,
                ask_price=lvl.ask_price,
                bid_quantity=lvl.bid_quantity,
                ask_quantity=lvl.ask_quantity,
                bid_notional=lvl.bid_notional,
                ask_notional=lvl.ask_notional,
            )
            for lvl in sorted(req.levels, key=lambda x: x.level_index)
        ]

        res = OrderBookImbalanceMath.calculate_snapshot_imbalance(
            levels=domain_levels,
            requested_levels=req.requested_levels,
            weighting_method=req.weighting_method,
            decay_parameter=req.decay_parameter,
            distance_unit=req.distance_unit,
            tick_size=req.tick_size,
        )

        regime = OrderBookImbalanceMath.classify_regime(
            res.multi_level_quantity_imbalance or Decimal("0.0")
        )

        snapshot_id = f"IMB-{uuid.uuid4().hex[:12].upper()}"
        now = datetime.now(timezone.utc)

        db_snapshot = OrderBookImbalanceSnapshot(
            snapshot_id=snapshot_id,
            instrument_id=req.instrument_id,
            listing_id=req.listing_id,
            venue_id=req.venue_id,
            event_timestamp=now,
            calculation_timestamp=now,
            best_level_imbalance=res.best_level_imbalance,
            multi_level_quantity_imbalance=res.multi_level_quantity_imbalance,
            multi_level_notional_imbalance=res.multi_level_notional_imbalance,
            weighted_quantity_imbalance=res.weighted_quantity_imbalance,
            weighted_notional_imbalance=res.weighted_notional_imbalance,
            bid_share=res.bid_share,
            ask_share=res.ask_share,
            total_bid_quantity=res.total_bid_quantity,
            total_ask_quantity=res.total_ask_quantity,
            total_bid_notional=res.total_bid_notional,
            total_ask_notional=res.total_ask_notional,
            microprice=res.microprice,
            midpoint=res.midpoint,
            microprice_deviation_bps=res.microprice_deviation_bps,
            actual_level_count=res.actual_level_count,
            regime=regime,
            config_id=config_id,
            quality_status="ELIGIBLE",
            created_at=now,
        )
        await self.repo.save_snapshot(db_snapshot)

        return ImbalanceSnapshotResponse.model_validate(db_snapshot)

    async def get_latest_imbalance(
        self, instrument_id: str, venue_id: Optional[str] = None
    ) -> Optional[ImbalanceSnapshotResponse]:
        db_snap = await self.repo.get_latest_snapshot(instrument_id, venue_id)
        if not db_snap:
            return None
        return ImbalanceSnapshotResponse.model_validate(db_snap)

    async def analyze_persistence(self, req: PersistenceAnalysisRequest) -> PersistenceResponse:
        obs_list = [
            TimeSeriesObservation(
                timestamp=datetime.fromisoformat(o["timestamp"]) if isinstance(o["timestamp"], str) else o["timestamp"],
                imbalance=Decimal(str(o["imbalance"])),
                duration_seconds=float(o.get("duration_seconds", 1.0)),
            )
            for o in req.observations
        ]

        p_res = OrderBookImbalanceMath.calculate_persistence_and_runs(
            observations=obs_list,
            threshold=req.threshold,
        )

        pers_id = f"PERS-{uuid.uuid4().hex[:10].upper()}"
        now = datetime.now(timezone.utc)
        start_ts = obs_list[0].timestamp if obs_list else now
        end_ts = obs_list[-1].timestamp if obs_list else now

        db_pers = OrderBookImbalancePersistenceResult(
            persistence_id=pers_id,
            instrument_id=req.instrument_id,
            venue_id=req.venue_id,
            window_start=start_ts,
            window_end=end_ts,
            bid_persistence_ratio=p_res["bid_persistence_ratio"],
            ask_persistence_ratio=p_res["ask_persistence_ratio"],
            neutral_persistence_ratio=p_res["neutral_persistence_ratio"],
            current_state=p_res["current_state"],
            current_run_duration_seconds=Decimal(str(p_res["current_run_duration_seconds"])),
            max_bid_run_seconds=Decimal(str(p_res["max_bid_run_seconds"])),
            max_ask_run_seconds=Decimal(str(p_res["max_ask_run_seconds"])),
            average_bid_run_seconds=Decimal(str(round(p_res["average_bid_run_seconds"], 4))),
            average_ask_run_seconds=Decimal(str(round(p_res["average_ask_run_seconds"], 4))),
            total_valid_duration_seconds=Decimal(str(p_res["total_valid_duration_seconds"])),
            created_at=now,
        )
        await self.repo.save_persistence_result(db_pers)

        return PersistenceResponse(
            instrument_id=req.instrument_id,
            venue_id=req.venue_id,
            bid_persistence_ratio=p_res["bid_persistence_ratio"],
            ask_persistence_ratio=p_res["ask_persistence_ratio"],
            neutral_persistence_ratio=p_res["neutral_persistence_ratio"],
            current_state=p_res["current_state"],
            current_run_duration_seconds=Decimal(str(p_res["current_run_duration_seconds"])),
            max_bid_run_seconds=Decimal(str(p_res["max_bid_run_seconds"])),
            max_ask_run_seconds=Decimal(str(p_res["max_ask_run_seconds"])),
            average_bid_run_seconds=Decimal(str(round(p_res["average_bid_run_seconds"], 4))),
            average_ask_run_seconds=Decimal(str(round(p_res["average_ask_run_seconds"], 4))),
            total_valid_duration_seconds=Decimal(str(p_res["total_valid_duration_seconds"])),
        )

    async def detect_reversals(self, req: ReversalDetectionRequest) -> ReversalDetectionResponse:
        obs_list = [
            TimeSeriesObservation(
                timestamp=datetime.fromisoformat(o["timestamp"]) if isinstance(o["timestamp"], str) else o["timestamp"],
                imbalance=Decimal(str(o["imbalance"])),
                duration_seconds=float(o.get("duration_seconds", 1.0)),
            )
            for o in req.observations
        ]

        raw_reversals = OrderBookImbalanceMath.detect_reversals(
            observations=obs_list,
            entry_threshold=req.entry_threshold,
            exit_threshold=req.exit_threshold,
        )

        db_events = []
        schema_events = []
        now = datetime.now(timezone.utc)

        for rev in raw_reversals:
            rev_id = f"REV-{uuid.uuid4().hex[:10].upper()}"
            db_ev = OrderBookImbalanceReversalEvent(
                reversal_id=rev_id,
                instrument_id=req.instrument_id,
                venue_id=req.venue_id,
                reversal_timestamp=rev["timestamp"],
                previous_state=rev["previous_state"],
                new_state=rev["new_state"],
                previous_imbalance=rev["previous_imbalance"],
                current_imbalance=rev["current_imbalance"],
                reversal_magnitude=rev["reversal_magnitude"],
                reversal_rate_per_sec=rev["reversal_rate_per_sec"],
                duration_seconds=Decimal(str(rev["duration_seconds"])),
                created_at=now,
            )
            db_events.append(db_ev)
            schema_events.append(
                ReversalEventSchema(
                    timestamp=rev["timestamp"],
                    previous_state=rev["previous_state"],
                    new_state=rev["new_state"],
                    previous_imbalance=rev["previous_imbalance"],
                    current_imbalance=rev["current_imbalance"],
                    reversal_magnitude=rev["reversal_magnitude"],
                    reversal_rate_per_sec=rev["reversal_rate_per_sec"],
                    duration_seconds=Decimal(str(rev["duration_seconds"])),
                )
            )

        if db_events:
            await self.repo.save_reversal_events(db_events)

        return ReversalDetectionResponse(
            instrument_id=req.instrument_id,
            reversal_count=len(schema_events),
            reversals=schema_events,
        )

    async def compare_venues(self, req: VenueComparisonRequest) -> VenueComparisonResponse:
        venue_outcomes: Dict[str, Any] = {}

        for venue_code, levels_in in req.venues_data.items():
            domain_levels = [
                OrderBookLevelData(
                    level_index=lvl.level_index,
                    bid_price=lvl.bid_price,
                    ask_price=lvl.ask_price,
                    bid_quantity=lvl.bid_quantity,
                    ask_quantity=lvl.ask_quantity,
                    bid_notional=lvl.bid_notional,
                    ask_notional=lvl.ask_notional,
                )
                for lvl in sorted(levels_in, key=lambda x: x.level_index)
            ]
            snap_res = OrderBookImbalanceMath.calculate_snapshot_imbalance(
                levels=domain_levels, requested_levels=5
            )
            regime = OrderBookImbalanceMath.classify_regime(
                snap_res.multi_level_quantity_imbalance or Decimal("0.0")
            )

            venue_outcomes[venue_code] = {
                "venue_id": venue_code,
                "best_level_imbalance": float(snap_res.best_level_imbalance) if snap_res.best_level_imbalance is not None else None,
                "top5_quantity_imbalance": float(snap_res.multi_level_quantity_imbalance) if snap_res.multi_level_quantity_imbalance is not None else None,
                "top5_notional_imbalance": float(snap_res.multi_level_notional_imbalance) if snap_res.multi_level_notional_imbalance is not None else None,
                "bid_share": float(snap_res.bid_share) if snap_res.bid_share is not None else None,
                "ask_share": float(snap_res.ask_share) if snap_res.ask_share is not None else None,
                "microprice": float(snap_res.microprice) if snap_res.microprice is not None else None,
                "midpoint": float(snap_res.midpoint) if snap_res.midpoint is not None else None,
                "regime": regime,
                "level_count": snap_res.actual_level_count,
            }

        return VenueComparisonResponse(
            instrument_id=req.instrument_id,
            venues=venue_outcomes,
        )

