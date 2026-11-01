"""
M05.07 - Portfolio History Service.
Core engine for bitemporal state reconstruction, snapshot capture, restatement handling,
timeline generation, and risk run input manifest generation.
"""

import hashlib
import json
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.portfolio_management.portfolio_history.models import (
    PortfolioBookSnapshot,
    HistoricalPositionSnapshot,
    HistoricalCashSnapshot,
    HistoricalValuationSnapshot,
    SnapshotSourceManifest,
    PortfolioChangeRecord,
    RiskRunInputManifest,
    SnapshotType,
    ChangeEventCategory,
    ReconstructionMode,
)
from backend.app.modules.portfolio_management.portfolio_history.schemas import (
    PortfolioBookSnapshotCreateRequest,
    PortfolioBookSnapshotResponse,
    HistoricalPositionItemSchema,
    HistoricalCashItemSchema,
    HistoricalValuationItemSchema,
    PortfolioChangeRecordCreateRequest,
    PortfolioChangeRecordResponse,
    BitemporalStateQueryRequest,
    BitemporalStateResponse,
    RiskRunInputManifestCreateRequest,
    RiskRunInputManifestResponse,
)
from backend.app.modules.portfolio_management.portfolio_history.repositories.repository import (
    PortfolioHistoryRepository,
)


class PortfolioHistoryService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = PortfolioHistoryRepository(session)

    # ==========================================
    # Hash calculation helper
    # ==========================================

    @staticmethod
    def _compute_snapshot_hash(
        portfolio_id: str,
        effective_as_of: datetime,
        knowledge_as_of: datetime,
        positions: List[Dict[str, Any]],
        cash: List[Dict[str, Any]],
    ) -> str:
        payload = {
            "portfolio_id": portfolio_id,
            "effective_as_of": effective_as_of.isoformat(),
            "knowledge_as_of": knowledge_as_of.isoformat(),
            "positions": sorted(positions, key=lambda x: (x.get("account_id", ""), x.get("instrument_id", ""))),
            "cash": sorted(cash, key=lambda x: (x.get("account_id", ""), x.get("currency", ""))),
        }
        encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    # ==========================================
    # Snapshot Capture & Restatement
    # ==========================================

    async def capture_snapshot(
        self,
        request: PortfolioBookSnapshotCreateRequest,
    ) -> PortfolioBookSnapshotResponse:
        """
        Captures an authoritative snapshot of positions, cash balances, and valuations.
        """
        now = datetime.utcnow()
        knowledge_time = request.knowledge_as_of or now
        snapshot_id = f"SNAP-{uuid.uuid4().hex[:12].upper()}"

        # Calculate totals
        total_market_value_base = sum(
            (p.market_value_base for p in request.positions),
            Decimal("0.000000"),
        )
        total_cash_value_base = sum(
            (c.available_cash_base for c in request.cash_balances),
            Decimal("0.000000"),
        )
        total_nav = total_market_value_base + total_cash_value_base

        # Determine version
        snapshot_version = 1
        is_restated = False
        if request.superseded_snapshot_id:
            old_snap = await self.repo.get_snapshot_by_id(request.superseded_snapshot_id)
            if old_snap:
                snapshot_version = int(old_snap.snapshot_version) + 1
                is_restated = True

        # Build position and cash payloads for hash
        pos_dicts = [p.model_dump() for p in request.positions]
        cash_dicts = [c.model_dump() for c in request.cash_balances]
        snapshot_hash = self._compute_snapshot_hash(
            portfolio_id=request.portfolio_id,
            effective_as_of=request.effective_as_of,
            knowledge_as_of=knowledge_time,
            positions=pos_dicts,
            cash=cash_dicts,
        )

        snapshot = PortfolioBookSnapshot(
            snapshot_id=snapshot_id,
            portfolio_id=request.portfolio_id,
            snapshot_type=request.snapshot_type.value,
            effective_as_of=request.effective_as_of,
            knowledge_as_of=knowledge_time,
            created_at=now,
            snapshot_version=snapshot_version,
            is_restated=is_restated,
            superseded_snapshot_id=request.superseded_snapshot_id,
            restatement_reason=request.restatement_reason,
            base_currency=request.base_currency,
            total_positions_count=len(request.positions),
            total_market_value_base=total_market_value_base,
            total_cash_value_base=total_cash_value_base,
            total_nav_base=total_nav,
            snapshot_hash=snapshot_hash,
        )

        # Attach positions
        for p in request.positions:
            pos_snap = HistoricalPositionSnapshot(
                id=f"HPOS-{uuid.uuid4().hex[:12].upper()}",
                snapshot_id=snapshot_id,
                portfolio_id=request.portfolio_id,
                account_id=p.account_id,
                instrument_id=p.instrument_id,
                net_signed_quantity=p.net_signed_quantity,
                gross_long_quantity=p.gross_long_quantity,
                gross_short_quantity=p.gross_short_quantity,
                settled_quantity=p.settled_quantity,
                unsettled_buy_quantity=p.unsettled_buy_quantity,
                unsettled_sell_quantity=p.unsettled_sell_quantity,
                available_quantity=p.available_quantity,
                currency=p.currency,
                cost_basis_amount=p.cost_basis_amount,
                cost_basis_base=p.cost_basis_base,
                market_price=p.market_price,
                market_value_base=p.market_value_base,
                unrealized_pnl_base=p.unrealized_pnl_base,
                effective_as_of=p.effective_as_of,
                knowledge_as_of=knowledge_time,
            )
            snapshot.positions.append(pos_snap)

        # Attach cash
        for c in request.cash_balances:
            cash_snap = HistoricalCashSnapshot(
                id=f"HCASH-{uuid.uuid4().hex[:12].upper()}",
                snapshot_id=snapshot_id,
                portfolio_id=request.portfolio_id,
                account_id=c.account_id,
                currency=c.currency,
                settled_cash=c.settled_cash,
                unsettled_receivables=c.unsettled_receivables,
                unsettled_payables=c.unsettled_payables,
                reserved_cash=c.reserved_cash,
                restricted_cash=c.restricted_cash,
                available_cash=c.available_cash,
                fx_rate_to_base=c.fx_rate_to_base,
                available_cash_base=c.available_cash_base,
                effective_as_of=c.effective_as_of,
                knowledge_as_of=knowledge_time,
            )
            snapshot.cash_balances.append(cash_snap)

        # Attach valuations
        for v in request.valuations:
            val_snap = HistoricalValuationSnapshot(
                id=f"HVAL-{uuid.uuid4().hex[:12].upper()}",
                snapshot_id=snapshot_id,
                portfolio_id=request.portfolio_id,
                instrument_id=v.instrument_id,
                price_source=v.price_source,
                price_timestamp=v.price_timestamp,
                market_price=v.market_price,
                price_currency=v.price_currency,
                fx_rate_to_base=v.fx_rate_to_base,
                market_value_local=v.market_value_local,
                market_value_base=v.market_value_base,
                cost_basis_base=v.cost_basis_base,
                unrealized_pnl_base=v.unrealized_pnl_base,
            )
            snapshot.valuations.append(val_snap)

        # Attach manifests
        for m in request.source_manifests:
            src_m = SnapshotSourceManifest(
                id=f"SMAN-{uuid.uuid4().hex[:12].upper()}",
                snapshot_id=snapshot_id,
                source_module=m.source_module,
                event_watermark_id=m.event_watermark_id,
                event_watermark_timestamp=m.event_watermark_timestamp,
                records_count=m.records_count,
                metadata_json=m.metadata_json,
            )
            snapshot.source_manifests.append(src_m)

        saved = await self.repo.create_snapshot(snapshot)

        # Build response directly from request schemas to prevent async lazy loading issues
        resp = PortfolioBookSnapshotResponse(
            snapshot_id=saved.snapshot_id,
            portfolio_id=saved.portfolio_id,
            snapshot_type=saved.snapshot_type,
            effective_as_of=saved.effective_as_of,
            knowledge_as_of=saved.knowledge_as_of,
            created_at=saved.created_at,
            snapshot_version=int(saved.snapshot_version),
            is_restated=saved.is_restated,
            superseded_snapshot_id=saved.superseded_snapshot_id,
            restatement_reason=saved.restatement_reason,
            base_currency=saved.base_currency,
            total_positions_count=int(saved.total_positions_count),
            total_market_value_base=saved.total_market_value_base,
            total_cash_value_base=saved.total_cash_value_base,
            total_nav_base=saved.total_nav_base,
            snapshot_hash=saved.snapshot_hash,
            positions=request.positions,
            cash_balances=request.cash_balances,
            valuations=request.valuations,
        )

        # Also emit a change record for the snapshot capture/restatement
        cat = ChangeEventCategory.SYSTEM_RESTATED if is_restated else ChangeEventCategory.VALUATION_UPDATE
        desc_text = f"Restated snapshot captured (v{snapshot_version}): {request.restatement_reason}" if is_restated else f"Book snapshot captured (v{snapshot_version})"
        await self.record_change_event(
            PortfolioChangeRecordCreateRequest(
                portfolio_id=request.portfolio_id,
                event_category=cat,
                source_module="M05.07_PORTFOLIO_HISTORY",
                source_event_id=snapshot_id,
                effective_at=request.effective_as_of,
                recorded_at=knowledge_time,
                change_description=desc_text,
                change_details={"snapshot_id": snapshot_id, "snapshot_type": request.snapshot_type.value, "version": snapshot_version},
            )
        )

        return resp

    def _to_snapshot_response(self, snap: PortfolioBookSnapshot) -> PortfolioBookSnapshotResponse:
        positions_res = [
            HistoricalPositionItemSchema(
                account_id=p.account_id,
                instrument_id=p.instrument_id,
                net_signed_quantity=p.net_signed_quantity,
                gross_long_quantity=p.gross_long_quantity,
                gross_short_quantity=p.gross_short_quantity,
                settled_quantity=p.settled_quantity,
                unsettled_buy_quantity=p.unsettled_buy_quantity,
                unsettled_sell_quantity=p.unsettled_sell_quantity,
                available_quantity=p.available_quantity,
                currency=p.currency,
                cost_basis_amount=p.cost_basis_amount,
                cost_basis_base=p.cost_basis_base,
                market_price=p.market_price,
                market_value_base=p.market_value_base,
                unrealized_pnl_base=p.unrealized_pnl_base,
                effective_as_of=p.effective_as_of,
                knowledge_as_of=p.knowledge_as_of,
            )
            for p in snap.positions
        ]

        cash_res = [
            HistoricalCashItemSchema(
                account_id=c.account_id,
                currency=c.currency,
                settled_cash=c.settled_cash,
                unsettled_receivables=c.unsettled_receivables,
                unsettled_payables=c.unsettled_payables,
                reserved_cash=c.reserved_cash,
                restricted_cash=c.restricted_cash,
                available_cash=c.available_cash,
                fx_rate_to_base=c.fx_rate_to_base,
                available_cash_base=c.available_cash_base,
                effective_as_of=c.effective_as_of,
                knowledge_as_of=c.knowledge_as_of,
            )
            for c in snap.cash_balances
        ]

        val_res = [
            HistoricalValuationItemSchema(
                instrument_id=v.instrument_id,
                price_source=v.price_source,
                price_timestamp=v.price_timestamp,
                market_price=v.market_price,
                price_currency=v.price_currency,
                fx_rate_to_base=v.fx_rate_to_base,
                market_value_local=v.market_value_local,
                market_value_base=v.market_value_base,
                cost_basis_base=v.cost_basis_base,
                unrealized_pnl_base=v.unrealized_pnl_base,
            )
            for v in snap.valuations
        ]

        return PortfolioBookSnapshotResponse(
            snapshot_id=snap.snapshot_id,
            portfolio_id=snap.portfolio_id,
            snapshot_type=snap.snapshot_type,
            effective_as_of=snap.effective_as_of,
            knowledge_as_of=snap.knowledge_as_of,
            created_at=snap.created_at,
            snapshot_version=int(snap.snapshot_version),
            is_restated=snap.is_restated,
            superseded_snapshot_id=snap.superseded_snapshot_id,
            restatement_reason=snap.restatement_reason,
            base_currency=snap.base_currency,
            total_positions_count=int(snap.total_positions_count),
            total_market_value_base=snap.total_market_value_base,
            total_cash_value_base=snap.total_cash_value_base,
            total_nav_base=snap.total_nav_base,
            snapshot_hash=snap.snapshot_hash,
            positions=positions_res,
            cash_balances=cash_res,
            valuations=val_res,
        )

    # ==========================================
    # Change Timeline Recording & Querying
    # ==========================================

    async def record_change_event(
        self,
        request: PortfolioChangeRecordCreateRequest,
    ) -> PortfolioChangeRecordResponse:
        seq = await self.repo.get_next_sequence_number(request.portfolio_id)
        now = datetime.utcnow()
        rec_time = request.recorded_at or now

        rec = PortfolioChangeRecord(
            change_record_id=f"CHG-{uuid.uuid4().hex[:12].upper()}",
            portfolio_id=request.portfolio_id,
            sequence_number=seq,
            event_category=request.event_category.value,
            source_module=request.source_module,
            source_event_id=request.source_event_id,
            effective_at=request.effective_at,
            recorded_at=rec_time,
            instrument_id=request.instrument_id,
            account_id=request.account_id,
            quantity_delta=request.quantity_delta,
            cash_delta=request.cash_delta,
            currency=request.currency,
            change_description=request.change_description,
            change_details=request.change_details,
        )
        saved = await self.repo.add_change_record(rec)
        return PortfolioChangeRecordResponse.model_validate(saved)

    async def get_change_timeline(
        self,
        portfolio_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        knowledge_cutoff: Optional[datetime] = None,
        instrument_id: Optional[str] = None,
    ) -> List[PortfolioChangeRecordResponse]:
        records = await self.repo.get_change_timeline(
            portfolio_id=portfolio_id,
            start_time=start_time,
            end_time=end_time,
            knowledge_cutoff=knowledge_cutoff,
            instrument_id=instrument_id,
        )
        return [PortfolioChangeRecordResponse.model_validate(r) for r in records]

    # ==========================================
    # Bitemporal Historical State Query (Query A vs Query B)
    # ==========================================

    async def query_bitemporal_state(
        self,
        request: BitemporalStateQueryRequest,
    ) -> BitemporalStateResponse:
        """
        Executes bitemporal portfolio reconstruction.
        - If knowledge_as_of is None -> Query A (Effective-Time State using current/latest knowledge, including post-facto corrections).
        - If knowledge_as_of is set -> Query B (Knowledge-Time State strictly bounded by historical knowledge cutoff).
        """
        now = datetime.utcnow()
        is_query_b = request.knowledge_as_of is not None
        query_type = "QUERY_B_POINT_IN_TIME_KNOWLEDGE" if is_query_b else "QUERY_A_LATEST_KNOWLEDGE"
        knowledge_time = request.knowledge_as_of if is_query_b else now

        # Find authoritative snapshot
        snap = await self.repo.find_snapshot_bitemporal(
            portfolio_id=request.portfolio_id,
            effective_as_of=request.effective_as_of,
            knowledge_as_of=knowledge_time,
        )

        if snap:
            positions = await self.repo.get_snapshot_positions(snap.snapshot_id)
            cash = await self.repo.get_snapshot_cash(snap.snapshot_id)

            explanation = (
                f"Resolved authoritative snapshot {snap.snapshot_id} (version {int(snap.snapshot_version)}) "
                f"under {query_type}. Effective as of {snap.effective_as_of}, "
                f"Knowledge cutoff applied: {knowledge_time}."
            )

            return BitemporalStateResponse(
                portfolio_id=request.portfolio_id,
                query_type=query_type,
                effective_as_of=request.effective_as_of,
                knowledge_as_of=knowledge_time,
                matched_snapshot_id=snap.snapshot_id,
                is_restated=snap.is_restated,
                base_currency=snap.base_currency,
                total_market_value_base=snap.total_market_value_base,
                total_cash_value_base=snap.total_cash_value_base,
                total_nav_base=snap.total_nav_base,
                positions=[
                    HistoricalPositionItemSchema(
                        account_id=p.account_id,
                        instrument_id=p.instrument_id,
                        net_signed_quantity=p.net_signed_quantity,
                        gross_long_quantity=p.gross_long_quantity,
                        gross_short_quantity=p.gross_short_quantity,
                        settled_quantity=p.settled_quantity,
                        unsettled_buy_quantity=p.unsettled_buy_quantity,
                        unsettled_sell_quantity=p.unsettled_sell_quantity,
                        available_quantity=p.available_quantity,
                        currency=p.currency,
                        cost_basis_amount=p.cost_basis_amount,
                        cost_basis_base=p.cost_basis_base,
                        market_price=p.market_price,
                        market_value_base=p.market_value_base,
                        unrealized_pnl_base=p.unrealized_pnl_base,
                        effective_as_of=p.effective_as_of,
                        knowledge_as_of=p.knowledge_as_of,
                    )
                    for p in positions
                ],
                cash_balances=[
                    HistoricalCashItemSchema(
                        account_id=c.account_id,
                        currency=c.currency,
                        settled_cash=c.settled_cash,
                        unsettled_receivables=c.unsettled_receivables,
                        unsettled_payables=c.unsettled_payables,
                        reserved_cash=c.reserved_cash,
                        restricted_cash=c.restricted_cash,
                        available_cash=c.available_cash,
                        fx_rate_to_base=c.fx_rate_to_base,
                        available_cash_base=c.available_cash_base,
                        effective_as_of=c.effective_as_of,
                        knowledge_as_of=c.knowledge_as_of,
                    )
                    for c in cash
                ],
                explanation=explanation,
            )

        # No snapshot found: fallback to event timeline replay
        explanation = f"No direct snapshot found. Reconstructing point-in-time state from change timeline under {query_type}."
        timeline = await self.repo.get_change_timeline(
            portfolio_id=request.portfolio_id,
            end_time=request.effective_as_of,
            knowledge_cutoff=knowledge_time,
        )

        pos_map: Dict[str, Decimal] = {}
        cash_map: Dict[str, Decimal] = {}

        for chg in timeline:
            if chg.instrument_id and chg.quantity_delta is not None:
                pos_map[chg.instrument_id] = pos_map.get(chg.instrument_id, Decimal("0.000000")) + chg.quantity_delta
            if chg.currency and chg.cash_delta is not None:
                cash_map[chg.currency] = cash_map.get(chg.currency, Decimal("0.000000")) + chg.cash_delta

        reconstructed_positions = [
            HistoricalPositionItemSchema(
                account_id="ACC-DEFAULT",
                instrument_id=inst,
                net_signed_quantity=qty,
                gross_long_quantity=qty if qty > 0 else Decimal("0"),
                gross_short_quantity=abs(qty) if qty < 0 else Decimal("0"),
                settled_quantity=qty,
                currency="USD",
                effective_as_of=request.effective_as_of,
                knowledge_as_of=knowledge_time,
            )
            for inst, qty in pos_map.items()
        ]

        reconstructed_cash = [
            HistoricalCashItemSchema(
                account_id="ACC-DEFAULT",
                currency=curr,
                settled_cash=amt,
                available_cash=amt,
                available_cash_base=amt,
                effective_as_of=request.effective_as_of,
                knowledge_as_of=knowledge_time,
            )
            for curr, amt in cash_map.items()
        ]

        return BitemporalStateResponse(
            portfolio_id=request.portfolio_id,
            query_type=query_type,
            effective_as_of=request.effective_as_of,
            knowledge_as_of=knowledge_time,
            matched_snapshot_id=None,
            is_restated=False,
            base_currency="USD",
            total_market_value_base=Decimal("0.000000"),
            total_cash_value_base=sum((c.available_cash_base for c in reconstructed_cash), Decimal("0.000000")),
            total_nav_base=sum((c.available_cash_base for c in reconstructed_cash), Decimal("0.000000")),
            positions=reconstructed_positions,
            cash_balances=reconstructed_cash,
            explanation=explanation,
        )

    # ==========================================
    # Risk Run Input Manifests
    # ==========================================

    async def create_risk_run_input_manifest(
        self,
        request: RiskRunInputManifestCreateRequest,
    ) -> RiskRunInputManifestResponse:
        """
        Creates an immutable reproducibility manifest for an institutional risk run.
        Fingerprints snapshot, pricing policy, FX rate tables, and corporate actions.
        """
        snap = await self.repo.get_snapshot_by_id(request.snapshot_id)
        if not snap:
            raise ValueError(f"Snapshot {request.snapshot_id} not found")

        positions = await self.repo.get_snapshot_positions(snap.snapshot_id)
        cash = await self.repo.get_snapshot_cash(snap.snapshot_id)

        manifest_id = f"RMAN-{uuid.uuid4().hex[:12].upper()}"
        now = datetime.utcnow()

        manifest_payload = {
            "portfolio_id": request.portfolio_id,
            "risk_run_id": request.risk_run_id,
            "snapshot_id": snap.snapshot_id,
            "effective_as_of": snap.effective_as_of.isoformat(),
            "knowledge_as_of": snap.knowledge_as_of.isoformat(),
            "base_currency": snap.base_currency,
            "total_nav_base": str(snap.total_nav_base),
            "market_data_partition_id": request.market_data_partition_id,
            "pricing_policy_version": request.pricing_policy_version,
            "fx_rate_table_version": request.fx_rate_table_version,
            "corporate_action_version": request.corporate_action_version,
            "position_fingerprints": [
                {
                    "instrument_id": p.instrument_id,
                    "net_signed_quantity": str(p.net_signed_quantity),
                    "market_value_base": str(p.market_value_base),
                }
                for p in positions
            ],
            "cash_fingerprints": [
                {
                    "account_id": c.account_id,
                    "currency": c.currency,
                    "available_cash": str(c.available_cash),
                }
                for c in cash
            ],
        }

        encoded_manifest = json.dumps(manifest_payload, sort_keys=True).encode("utf-8")
        manifest_hash = hashlib.sha256(encoded_manifest).hexdigest()

        manifest = RiskRunInputManifest(
            manifest_id=manifest_id,
            portfolio_id=request.portfolio_id,
            risk_run_id=request.risk_run_id,
            created_at=now,
            snapshot_id=snap.snapshot_id,
            effective_as_of=snap.effective_as_of,
            knowledge_as_of=snap.knowledge_as_of,
            market_data_partition_id=request.market_data_partition_id,
            pricing_policy_version=request.pricing_policy_version,
            fx_rate_table_version=request.fx_rate_table_version,
            corporate_action_version=request.corporate_action_version,
            positions_count=len(positions),
            total_nav_base=snap.total_nav_base,
            manifest_hash=manifest_hash,
            manifest_payload=manifest_payload,
        )

        saved = await self.repo.create_risk_manifest(manifest)
        return RiskRunInputManifestResponse.model_validate(saved)

    async def get_risk_run_input_manifest(
        self,
        manifest_id: str,
    ) -> Optional[RiskRunInputManifestResponse]:
        manifest = await self.repo.get_risk_manifest(manifest_id)
        if not manifest:
            return None
        return RiskRunInputManifestResponse.model_validate(manifest)
