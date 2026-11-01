"""
M05.08 Multi-Portfolio Management Service.
Core engine for portfolio group lifecycle, membership resolution with historical bitemporality,
cross-portfolio holding aggregation, gross/net analytical exposure, cash consolidation,
shared setting inheritance, and snapshot generation.
"""

import hashlib
import json
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple, Set
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.portfolio_management.multi_portfolio_management.models import (
    PortfolioGroup,
    PortfolioGroupMembership,
    PortfolioGroupMembershipEvent,
    PortfolioGroupPolicy,
    PortfolioGroupSettingOverride,
    PortfolioGroupConsolidationRun,
    PortfolioGroupConsolidatedHolding,
    PortfolioGroupHoldingContributor,
    PortfolioGroupCashSummary,
    PortfolioGroupSnapshot,
    PortfolioGroupAuditEvent,
    GroupStatus,
    MembershipStatus,
    ConsolidationStatus,
)
from backend.app.modules.portfolio_management.multi_portfolio_management.schemas import (
    PortfolioGroupCreateRequest,
    PortfolioGroupUpdateRequest,
    PortfolioGroupResponse,
    PortfolioGroupMembershipAddRequest,
    PortfolioGroupMembershipUpdateRequest,
    PortfolioGroupMembershipResponse,
    PortfolioGroupMembershipEventResponse,
    PortfolioGroupPolicyCreateRequest,
    PortfolioGroupPolicyResponse,
    PortfolioGroupOverrideCreateRequest,
    PortfolioGroupOverrideResponse,
    ResolvedGroupSettingResponse,
    ConsolidationRunExecuteRequest,
    ConsolidationRunResponse,
    ConsolidatedHoldingResponse,
    HoldingContributorResponse,
    ConsolidatedCashSummaryResponse,
    GroupExposureSummaryResponse,
    PortfolioGroupSnapshotResponse,
    GroupComparisonResponse,
)
from backend.app.modules.portfolio_management.multi_portfolio_management.repositories.repository import (
    MultiPortfolioRepository,
)
from backend.app.modules.portfolio_management.position_management.repositories.repository import (
    PositionRepository,
)
from backend.app.modules.portfolio_management.position_valuation.repositories.repository import (
    ValuationRepository,
)
from backend.app.modules.portfolio_management.cash_management.services.service import (
    CashManagementService,
)


class MultiPortfolioService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = MultiPortfolioRepository(session)
        self.pos_repo = PositionRepository(session)
        self.val_repo = ValuationRepository(session)
        self.cash_svc = CashManagementService(session)

    # ==========================================
    # Group Management & Lifecycle
    # ==========================================

    async def create_group(self, request: PortfolioGroupCreateRequest) -> PortfolioGroupResponse:
        existing = await self.repo.get_group_by_code(request.group_code)
        if existing:
            raise ValueError(f"Portfolio group with code '{request.group_code}' already exists")

        # Validate parent hierarchy if supplied
        if request.parent_group_id:
            parent = await self.repo.get_group_by_id(request.parent_group_id)
            if not parent:
                raise ValueError(f"Parent group '{request.parent_group_id}' does not exist")

        group_id = f"GRP-{uuid.uuid4().hex[:12].upper()}"
        group = PortfolioGroup(
            id=group_id,
            group_code=request.group_code,
            group_name=request.group_name,
            description=request.description,
            group_type=request.group_type.value,
            parent_group_id=request.parent_group_id,
            owner_reference=request.owner_reference,
            organization_reference=request.organization_reference,
            reporting_currency=request.reporting_currency,
            primary_benchmark_reference=request.primary_benchmark_reference,
            shared_risk_convention=request.shared_risk_convention,
            status=GroupStatus.ACTIVE.value,
            current_version=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        saved = await self.repo.create_group(group)

        # Record initial policy
        policy = PortfolioGroupPolicy(
            id=f"POL-{uuid.uuid4().hex[:12].upper()}",
            group_id=group_id,
            policy_name="DEFAULT_GROUP_POLICY",
            reporting_currency=request.reporting_currency,
            benchmark_reference=request.primary_benchmark_reference,
            risk_convention_reference=request.shared_risk_convention,
            exposure_aggregation_policy="CANONICAL_INSTRUMENT",
            effective_from=datetime.utcnow(),
            policy_version=1,
            approval_status="APPROVED",
            created_at=datetime.utcnow(),
        )
        await self.repo.create_policy(policy)

        # Audit
        await self.repo.add_audit_event(
            PortfolioGroupAuditEvent(
                id=f"AUD-{uuid.uuid4().hex[:12].upper()}",
                group_id=group_id,
                actor_id=request.owner_reference,
                action_type="CREATE_GROUP",
                entity_type="PORTFOLIO_GROUP",
                entity_id=group_id,
                new_state={"group_code": request.group_code, "group_name": request.group_name},
                effective_at=datetime.utcnow(),
                recorded_at=datetime.utcnow(),
            )
        )

        return PortfolioGroupResponse.model_validate(saved)

    async def get_group(self, group_id: str) -> Optional[PortfolioGroupResponse]:
        group = await self.repo.get_group_by_id(group_id)
        if not group:
            return None
        return PortfolioGroupResponse.model_validate(group)

    async def update_group_status(self, group_id: str, new_status: GroupStatus, actor_id: str) -> PortfolioGroupResponse:
        group = await self.repo.get_group_by_id(group_id)
        if not group:
            raise ValueError(f"Portfolio group '{group_id}' not found")

        prev_status = group.status
        group.status = new_status.value
        group.current_version = int(group.current_version) + 1
        group.updated_at = datetime.utcnow()
        await self.session.flush()

        await self.repo.add_audit_event(
            PortfolioGroupAuditEvent(
                id=f"AUD-{uuid.uuid4().hex[:12].upper()}",
                group_id=group_id,
                actor_id=actor_id,
                action_type="STATUS_CHANGE",
                entity_type="PORTFOLIO_GROUP",
                entity_id=group_id,
                previous_state={"status": prev_status},
                new_state={"status": new_status.value},
                effective_at=datetime.utcnow(),
                recorded_at=datetime.utcnow(),
            )
        )
        return PortfolioGroupResponse.model_validate(group)

    # ==========================================
    # Membership Management
    # ==========================================

    async def add_portfolio_to_group(
        self,
        group_id: str,
        request: PortfolioGroupMembershipAddRequest,
        actor_id: str = "SYSTEM_ADMIN",
    ) -> PortfolioGroupMembershipResponse:
        group = await self.repo.get_group_by_id(group_id)
        if not group:
            raise ValueError(f"Portfolio group '{group_id}' not found")
        if group.status in (GroupStatus.CLOSED.value, GroupStatus.ARCHIVED.value):
            raise ValueError(f"Cannot add portfolio to group in {group.status} state")

        now = datetime.utcnow()
        eff_from = request.effective_from or now

        # Check existing active membership
        existing = await self.repo.get_membership(group_id, request.portfolio_id)
        if existing and existing.membership_status == MembershipStatus.ACTIVE.value:
            raise ValueError(f"Portfolio '{request.portfolio_id}' is already an active member of group '{group_id}'")

        membership_id = f"MEM-{uuid.uuid4().hex[:12].upper()}"
        mem_ver = (int(existing.membership_version) + 1) if existing else 1

        membership = PortfolioGroupMembership(
            id=membership_id,
            group_id=group_id,
            portfolio_id=request.portfolio_id,
            membership_role=request.membership_role.value,
            membership_status=MembershipStatus.ACTIVE.value,
            include_in_positions=request.include_in_positions,
            include_in_valuation=request.include_in_valuation,
            include_in_cash=request.include_in_cash,
            include_in_contribution=request.include_in_contribution,
            include_in_risk_inputs=request.include_in_risk_inputs,
            reporting_weight=request.reporting_weight,
            effective_from=eff_from,
            effective_to=None,
            recorded_from=now,
            membership_version=mem_ver,
            approval_reference=request.approval_reference,
            created_at=now,
            updated_at=now,
        )
        saved = await self.repo.add_membership(membership)

        # Record immutable event
        await self.repo.add_membership_event(
            PortfolioGroupMembershipEvent(
                id=f"MEV-{uuid.uuid4().hex[:12].upper()}",
                group_id=group_id,
                portfolio_id=request.portfolio_id,
                membership_id=membership_id,
                event_type="ADD_PORTFOLIO",
                previous_status=existing.membership_status if existing else None,
                new_status=MembershipStatus.ACTIVE.value,
                effective_at=eff_from,
                recorded_at=now,
                actor_id=actor_id,
                reason="Added to group",
                membership_version=mem_ver,
                created_at=now,
            )
        )

        return PortfolioGroupMembershipResponse.model_validate(saved)

    async def remove_portfolio_from_group(
        self,
        group_id: str,
        portfolio_id: str,
        effective_to: Optional[datetime] = None,
        actor_id: str = "SYSTEM_ADMIN",
    ) -> PortfolioGroupMembershipResponse:
        membership = await self.repo.get_membership(group_id, portfolio_id)
        if not membership or membership.membership_status != MembershipStatus.ACTIVE.value:
            raise ValueError(f"Portfolio '{portfolio_id}' is not an active member of group '{group_id}'")

        now = datetime.utcnow()
        eff_end = effective_to or now

        membership.membership_status = MembershipStatus.REMOVED.value
        membership.effective_to = eff_end
        membership.recorded_to = now
        membership.membership_version = int(membership.membership_version) + 1
        membership.updated_at = now
        await self.session.flush()

        await self.repo.add_membership_event(
            PortfolioGroupMembershipEvent(
                id=f"MEV-{uuid.uuid4().hex[:12].upper()}",
                group_id=group_id,
                portfolio_id=portfolio_id,
                membership_id=membership.id,
                event_type="REMOVE_PORTFOLIO",
                previous_status=MembershipStatus.ACTIVE.value,
                new_status=MembershipStatus.REMOVED.value,
                effective_at=eff_end,
                recorded_at=now,
                actor_id=actor_id,
                reason="Removed from group",
                membership_version=int(membership.membership_version),
                created_at=now,
            )
        )

        return PortfolioGroupMembershipResponse.model_validate(membership)

    # ==========================================
    # Hierarchy Resolution & Deduplication
    # ==========================================

    async def resolve_group_portfolios(
        self,
        group_id: str,
        as_of: datetime,
        include_descendants: bool = True,
    ) -> Tuple[List[str], Dict[str, PortfolioGroupMembership]]:
        """
        Recursively resolves all descendant portfolios if hierarchy is enabled,
        preventing circular loops and strictly deduplicating portfolios.
        """
        visited_groups: Set[str] = set()
        resolved_portfolios: Set[str] = set()
        portfolio_memberships: Dict[str, PortfolioGroupMembership] = {}

        async def _traverse(current_group_id: str):
            if current_group_id in visited_groups:
                return
            visited_groups.add(current_group_id)

            mems = await self.repo.get_active_memberships_as_of(current_group_id, as_of)
            for m in mems:
                if m.portfolio_id not in resolved_portfolios:
                    resolved_portfolios.add(m.portfolio_id)
                    portfolio_memberships[m.portfolio_id] = m

            if include_descendants:
                children = await self.repo.get_child_groups(current_group_id)
                for c in children:
                    await _traverse(c.id)

        await _traverse(group_id)
        return sorted(list(resolved_portfolios)), portfolio_memberships

    # ==========================================
    # Shared Setting Inheritance & Overrides
    # ==========================================

    async def resolve_setting(
        self,
        group_id: str,
        setting_key: str,
        portfolio_id: Optional[str] = None,
        as_of: Optional[datetime] = None,
    ) -> ResolvedGroupSettingResponse:
        as_of_time = as_of or datetime.utcnow()

        # 1. Check portfolio-specific override in group context
        if portfolio_id:
            override = await self.repo.get_portfolio_override(group_id, portfolio_id, setting_key, as_of_time)
            if override:
                return ResolvedGroupSettingResponse(
                    group_id=group_id,
                    portfolio_id=portfolio_id,
                    setting_key=setting_key,
                    effective_value=override.override_value or override.override_reference,
                    source_level="PORTFOLIO_OVERRIDE",
                    policy_version=int(override.override_version),
                    is_override=True,
                    explanation=f"Explicit override applied for portfolio '{portfolio_id}' in group '{group_id}'.",
                )

        # 2. Check group policy
        policy = await self.repo.get_latest_group_policy(group_id)
        if policy:
            val = None
            if setting_key == "REPORTING_CURRENCY":
                val = policy.reporting_currency
            elif setting_key == "BENCHMARK":
                val = policy.benchmark_reference
            elif setting_key == "RISK_CONVENTION":
                val = policy.risk_convention_reference
            elif setting_key == "CALENDAR":
                val = policy.calendar_reference
            elif setting_key == "EXPOSURE_AGGREGATION_POLICY":
                val = policy.exposure_aggregation_policy

            if val:
                return ResolvedGroupSettingResponse(
                    group_id=group_id,
                    portfolio_id=portfolio_id,
                    setting_key=setting_key,
                    effective_value=val,
                    source_level="GROUP_POLICY",
                    policy_version=int(policy.policy_version),
                    is_override=False,
                    explanation=f"Inherited approved setting from group policy '{policy.policy_name}' (v{int(policy.policy_version)}).",
                )

        # 3. Default fallback
        default_val = "USD" if setting_key == "REPORTING_CURRENCY" else "DEFAULT_STANDARD"
        return ResolvedGroupSettingResponse(
            group_id=group_id,
            portfolio_id=portfolio_id,
            setting_key=setting_key,
            effective_value=default_val,
            source_level="SYSTEM_DEFAULT",
            policy_version=1,
            is_override=False,
            explanation=f"System platform default applied for '{setting_key}'.",
        )

    # ==========================================
    # Cross-Portfolio Consolidation Orchestration
    # ==========================================

    async def execute_consolidation(
        self,
        group_id: str,
        request: ConsolidationRunExecuteRequest,
    ) -> ConsolidationRunResponse:
        """
        Executes cross-portfolio consolidation:
        - Resolves active member portfolios with strict deduplication.
        - Retrieves authoritative positions (M05.02) and valuations (M05.03).
        - Computes gross long, gross short, net quantities and exposure values.
        - Preserves complete line-item source contributor lineage.
        - Aggregates cash (M05.04) currency by currency.
        - Emits an immutable group snapshot.
        """
        group = await self.repo.get_group_by_id(group_id)
        if not group:
            raise ValueError(f"Portfolio group '{group_id}' not found")

        now = datetime.utcnow()
        eff_as_of = request.effective_as_of or now
        know_as_of = request.knowledge_as_of or now
        rep_curr = request.reporting_currency or group.reporting_currency

        # 1. Resolve portfolios & memberships
        portfolio_ids, memberships = await self.resolve_group_portfolios(group_id, eff_as_of)
        included_portfolios = [
            pid for pid in portfolio_ids if memberships[pid].include_in_positions
        ]
        excluded_portfolios = [
            pid for pid in portfolio_ids if not memberships[pid].include_in_positions
        ]

        run_id = f"RUN-{uuid.uuid4().hex[:12].upper()}"

        # 2. Holdings aggregation containers
        # Aggregation key: instrument_id
        inst_contributors: Dict[str, List[PortfolioGroupHoldingContributor]] = {}
        inst_native_currency: Dict[str, str] = {}
        inst_listing: Dict[str, Optional[str]] = {}

        # Query source positions for each portfolio
        for pid in included_portfolios:
            # Query positions from M05.02 via list_books_by_portfolio and latest snapshot
            books = await self.pos_repo.list_books_by_portfolio(pid)
            val_recs = await self.val_repo.list_position_valuations(pid)
            for book in books:
                snap = await self.pos_repo.get_latest_snapshot(book.position_id)
                if snap:
                    inst = snap.instrument_id
                    inst_native_currency[inst] = "USD"
                    inst_listing[inst] = snap.listing_id

                    matched_val = next((v for v in val_recs if v.instrument_id == inst), None)
                    mv_native = matched_val.market_value if matched_val else Decimal("0.000000")
                    curr = matched_val.currency if matched_val else "USD"
                    inst_native_currency[inst] = curr

                    fx_rate = request.fx_rates_to_reporting.get(curr, Decimal("1.000000"))
                    mv_rep = mv_native * fx_rate
                    side = "LONG" if snap.net_signed_quantity >= 0 else "SHORT"

                    contributor = PortfolioGroupHoldingContributor(
                        id=f"CON-{uuid.uuid4().hex[:12].upper()}",
                        consolidated_holding_id="",  # Bound below
                        portfolio_id=pid,
                        account_id=snap.account_id,
                        instrument_id=inst,
                        listing_id=snap.listing_id,
                        source_position_reference=book.position_id,
                        source_valuation_reference=matched_val.id if matched_val else None,
                        position_side=side,
                        signed_quantity=snap.net_signed_quantity,
                        market_value_native=mv_native,
                        market_value_reporting_currency=mv_rep,
                        currency=curr,
                        fx_rate_applied=fx_rate,
                        source_snapshot_id=snap.snapshot_id,
                        created_at=now,
                    )

                    if inst not in inst_contributors:
                        inst_contributors[inst] = []
                    inst_contributors[inst].append(contributor)

        # Build consolidated holdings
        consolidated_holdings: List[PortfolioGroupConsolidatedHolding] = []
        tot_gross_long_mv = Decimal("0.000000")
        tot_gross_short_mv = Decimal("0.000000")

        for inst, contribs in inst_contributors.items():
            holding_id = f"HLD-{uuid.uuid4().hex[:12].upper()}"

            gross_long_qty = sum((c.signed_quantity for c in contribs if c.signed_quantity > 0), Decimal("0.000000"))
            gross_short_qty = sum((abs(c.signed_quantity) for c in contribs if c.signed_quantity < 0), Decimal("0.000000"))
            net_signed_qty = sum((c.signed_quantity for c in contribs), Decimal("0.000000"))

            gross_long_mv = sum((c.market_value_reporting_currency for c in contribs if c.market_value_reporting_currency > 0), Decimal("0.000000"))
            gross_short_mv = sum((abs(c.market_value_reporting_currency) for c in contribs if c.market_value_reporting_currency < 0), Decimal("0.000000"))
            net_mv = gross_long_mv - gross_short_mv

            tot_gross_long_mv += gross_long_mv
            tot_gross_short_mv += gross_short_mv

            distinct_ports = len(set(c.portfolio_id for c in contribs))
            distinct_accs = len(set((c.portfolio_id, c.account_id) for c in contribs))

            c_holding = PortfolioGroupConsolidatedHolding(
                id=holding_id,
                consolidation_run_id=run_id,
                group_id=group_id,
                instrument_id=inst,
                listing_id=inst_listing.get(inst),
                native_currency=inst_native_currency.get(inst, "USD"),
                gross_long_quantity=gross_long_qty,
                gross_short_quantity=gross_short_qty,
                net_signed_quantity=net_signed_qty,
                gross_long_market_value=gross_long_mv,
                gross_short_market_value=gross_short_mv,
                net_market_value=net_mv,
                reporting_currency_value=net_mv,
                contributing_portfolio_count=distinct_ports,
                contributing_account_count=distinct_accs,
                valuation_status="COMPLETE",
                created_at=now,
            )

            for c in contribs:
                c.consolidated_holding_id = holding_id
                c_holding.contributors.append(c)

            consolidated_holdings.append(c_holding)

        tot_gross_exposure = tot_gross_long_mv + tot_gross_short_mv
        tot_net_exposure = tot_gross_long_mv - tot_gross_short_mv

        # 3. Cash consolidation
        cash_summaries: List[PortfolioGroupCashSummary] = []
        cash_by_currency: Dict[str, Dict[str, Any]] = {}

        for pid in included_portfolios:
            # Query cash from M05.04
            accounts = await self.cash_svc.repo.list_cash_accounts_by_portfolio(pid)
            for acc in accounts:
                curr = acc.currency
                avail = await self.cash_svc.calculate_available_cash(pid, acc.account_id, curr)
                if curr not in cash_by_currency:
                    cash_by_currency[curr] = {
                        "settled": Decimal("0.000000"),
                        "unsettled_rec": Decimal("0.000000"),
                        "unsettled_pay": Decimal("0.000000"),
                        "reserved": Decimal("0.000000"),
                        "restricted": Decimal("0.000000"),
                        "available": Decimal("0.000000"),
                        "accounts": set(),
                    }
                cash_by_currency[curr]["settled"] += avail.settled_balance
                cash_by_currency[curr]["unsettled_rec"] += avail.eligible_unsettled_receivables
                cash_by_currency[curr]["unsettled_pay"] += avail.unreserved_payable_deductions
                cash_by_currency[curr]["reserved"] += avail.active_reservations
                cash_by_currency[curr]["restricted"] += avail.restricted_cash
                cash_by_currency[curr]["available"] += avail.final_available_cash
                cash_by_currency[curr]["accounts"].add((pid, acc.account_id))

        for curr, data in cash_by_currency.items():
            fx = request.fx_rates_to_reporting.get(curr, Decimal("1.000000"))
            c_sum = PortfolioGroupCashSummary(
                id=f"CSUM-{uuid.uuid4().hex[:12].upper()}",
                consolidation_run_id=run_id,
                group_id=group_id,
                currency=curr,
                settled_cash=data["settled"],
                unsettled_receivables=data["unsettled_rec"],
                unsettled_payables=data["unsettled_pay"],
                reserved_cash=data["reserved"],
                restricted_cash=data["restricted"],
                available_cash=data["available"],
                reporting_currency_equivalent=data["available"] * fx,
                contributing_account_count=len(data["accounts"]),
                completeness_status="COMPLETE",
                created_at=now,
            )
            cash_summaries.append(c_sum)

        # 4. Manifest hash
        manifest_payload = {
            "group_id": group_id,
            "included_portfolios": sorted(included_portfolios),
            "effective_as_of": eff_as_of.isoformat(),
            "knowledge_as_of": know_as_of.isoformat(),
            "reporting_currency": rep_curr,
            "holdings": [
                {
                    "instrument_id": h.instrument_id,
                    "net_signed_quantity": str(h.net_signed_quantity),
                    "net_market_value": str(h.net_market_value),
                }
                for h in sorted(consolidated_holdings, key=lambda x: x.instrument_id)
            ],
        }
        manifest_hash = hashlib.sha256(json.dumps(manifest_payload, sort_keys=True).encode("utf-8")).hexdigest()

        # 5. Persist Consolidation Run
        run = PortfolioGroupConsolidationRun(
            id=run_id,
            group_id=group_id,
            group_version=int(group.current_version),
            membership_version=1,
            consolidation_type="STANDARD",
            effective_as_of=eff_as_of,
            knowledge_as_of=know_as_of,
            reporting_currency=rep_curr,
            consolidation_policy_version=request.consolidation_policy_version,
            included_portfolio_count=len(included_portfolios),
            excluded_portfolio_count=len(excluded_portfolios),
            distinct_instrument_count=len(consolidated_holdings),
            total_gross_long_market_value=tot_gross_long_mv,
            total_gross_short_market_value=tot_gross_short_mv,
            total_gross_exposure=tot_gross_exposure,
            total_net_exposure=tot_net_exposure,
            run_status=ConsolidationStatus.COMPLETED.value,
            started_at=now,
            completed_at=now,
            input_manifest_hash=manifest_hash,
            created_at=now,
        )
        for h in consolidated_holdings:
            run.holdings.append(h)
        for c in cash_summaries:
            run.cash_summaries.append(c)

        saved_run = await self.repo.create_consolidation_run(run)

        # 6. Capture Immutable Group Snapshot
        snapshot = PortfolioGroupSnapshot(
            id=f"GSNAP-{uuid.uuid4().hex[:12].upper()}",
            group_id=group_id,
            consolidation_run_id=run_id,
            group_version=int(group.current_version),
            membership_version=1,
            effective_as_of=eff_as_of,
            knowledge_as_of=know_as_of,
            reporting_currency=rep_curr,
            source_snapshot_references={"included_portfolios": included_portfolios},
            policy_version_manifest={"consolidation_policy_version": request.consolidation_policy_version},
            snapshot_status="FINAL",
            snapshot_hash=manifest_hash,
            created_at=now,
        )
        await self.repo.create_snapshot(snapshot)

        # Construct response directly from in-memory objects to prevent async lazyload issues
        h_resp = [
            ConsolidatedHoldingResponse(
                id=h.id,
                group_id=h.group_id,
                instrument_id=h.instrument_id,
                listing_id=h.listing_id,
                native_currency=h.native_currency,
                gross_long_quantity=h.gross_long_quantity,
                gross_short_quantity=h.gross_short_quantity,
                net_signed_quantity=h.net_signed_quantity,
                gross_long_market_value=h.gross_long_market_value,
                gross_short_market_value=h.gross_short_market_value,
                net_market_value=h.net_market_value,
                reporting_currency_value=h.reporting_currency_value,
                contributing_portfolio_count=int(h.contributing_portfolio_count),
                contributing_account_count=int(h.contributing_account_count),
                valuation_status=h.valuation_status,
                contributors=[
                    HoldingContributorResponse(
                        id=c.id,
                        portfolio_id=c.portfolio_id,
                        account_id=c.account_id,
                        instrument_id=c.instrument_id,
                        listing_id=c.listing_id,
                        position_side=c.position_side,
                        signed_quantity=c.signed_quantity,
                        market_value_native=c.market_value_native,
                        market_value_reporting_currency=c.market_value_reporting_currency,
                        currency=c.currency,
                        fx_rate_applied=c.fx_rate_applied,
                        source_snapshot_id=c.source_snapshot_id,
                    )
                    for c in h.contributors
                ],
            )
            for h in consolidated_holdings
        ]

        c_resp = [
            ConsolidatedCashSummaryResponse(
                id=c.id,
                group_id=c.group_id,
                currency=c.currency,
                settled_cash=c.settled_cash,
                unsettled_receivables=c.unsettled_receivables,
                unsettled_payables=c.unsettled_payables,
                reserved_cash=c.reserved_cash,
                restricted_cash=c.restricted_cash,
                available_cash=c.available_cash,
                reporting_currency_equivalent=c.reporting_currency_equivalent,
                contributing_account_count=int(c.contributing_account_count),
                completeness_status=c.completeness_status,
            )
            for c in cash_summaries
        ]

        return ConsolidationRunResponse(
            id=saved_run.id,
            group_id=saved_run.group_id,
            group_version=int(saved_run.group_version),
            membership_version=int(saved_run.membership_version),
            consolidation_type=saved_run.consolidation_type,
            effective_as_of=saved_run.effective_as_of,
            knowledge_as_of=saved_run.knowledge_as_of,
            reporting_currency=saved_run.reporting_currency,
            consolidation_policy_version=saved_run.consolidation_policy_version,
            included_portfolio_count=int(saved_run.included_portfolio_count),
            excluded_portfolio_count=int(saved_run.excluded_portfolio_count),
            distinct_instrument_count=int(saved_run.distinct_instrument_count),
            total_gross_long_market_value=saved_run.total_gross_long_market_value,
            total_gross_short_market_value=saved_run.total_gross_short_market_value,
            total_gross_exposure=saved_run.total_gross_exposure,
            total_net_exposure=saved_run.total_net_exposure,
            run_status=saved_run.run_status,
            started_at=saved_run.started_at,
            completed_at=saved_run.completed_at,
            input_manifest_hash=saved_run.input_manifest_hash,
            created_at=saved_run.created_at,
            holdings=h_resp,
            cash_summaries=c_resp,
        )

    # ==========================================
    # Exposure Summaries & Group Comparisons
    # ==========================================

    async def get_group_exposure(self, group_id: str) -> GroupExposureSummaryResponse:
        runs = await self.repo.list_consolidation_runs(group_id, limit=1)
        if not runs:
            # Auto-run standard consolidation
            res = await self.execute_consolidation(group_id, ConsolidationRunExecuteRequest())
            runs = [await self.repo.get_consolidation_run(res.id)]

        latest = runs[0]
        holdings = await self.repo.get_run_holdings(latest.id)

        net_qty_by_inst: Dict[str, Decimal] = {}
        port_contribs: Dict[str, Decimal] = {}

        for h in holdings:
            net_qty_by_inst[h.instrument_id] = h.net_signed_quantity
            contribs = await self.repo.get_holding_contributors(h.id)
            for c in contribs:
                port_contribs[c.portfolio_id] = port_contribs.get(c.portfolio_id, Decimal("0.000000")) + c.market_value_reporting_currency

        return GroupExposureSummaryResponse(
            group_id=group_id,
            reporting_currency=latest.reporting_currency,
            effective_as_of=latest.effective_as_of,
            total_gross_long_market_value=latest.total_gross_long_market_value,
            total_gross_short_market_value=latest.total_gross_short_market_value,
            total_gross_exposure=latest.total_gross_exposure,
            total_net_exposure=latest.total_net_exposure,
            total_net_quantity_by_instrument=net_qty_by_inst,
            portfolio_contributions=port_contribs,
        )

    async def compare_groups(self, group_id_1: str, group_id_2: str) -> GroupComparisonResponse:
        exp1 = await self.get_group_exposure(group_id_1)
        exp2 = await self.get_group_exposure(group_id_2)

        ports1, _ = await self.resolve_group_portfolios(group_id_1, exp1.effective_as_of)
        ports2, _ = await self.resolve_group_portfolios(group_id_2, exp2.effective_as_of)

        overlapping = sorted(list(set(ports1).intersection(set(ports2))))
        distinct_1 = sorted(list(set(ports1) - set(ports2)))
        distinct_2 = sorted(list(set(ports2) - set(ports1)))

        return GroupComparisonResponse(
            target_group_id_1=group_id_1,
            target_group_id_2=group_id_2,
            reporting_currency=exp1.reporting_currency,
            comparison_timestamp=datetime.utcnow(),
            group_1_net_exposure=exp1.total_net_exposure,
            group_2_net_exposure=exp2.total_net_exposure,
            net_exposure_difference=abs(exp1.total_net_exposure - exp2.total_net_exposure),
            overlapping_portfolios=overlapping,
            distinct_portfolios_group_1=distinct_1,
            distinct_portfolios_group_2=distinct_2,
        )
