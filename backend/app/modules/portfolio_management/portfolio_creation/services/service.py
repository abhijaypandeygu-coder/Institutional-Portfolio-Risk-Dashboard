"""Service layer for M05.01 - Portfolio Creation."""
import json
import uuid
from datetime import date, datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.portfolio_management.portfolio_creation.models import (
    Portfolio,
    PortfolioTypeEnum,
    PortfolioLifecycleStatus,
    CreationSourceEnum,
    MarketScopeEnum,
    PortfolioStrategy,
    PortfolioStrategyAssignment,
    PortfolioMandate,
    PortfolioMandateAssignment,
    PortfolioBenchmark,
    PortfolioOwnership,
    PortfolioHierarchy,
    PortfolioValuationSettings,
    PortfolioAccountingSettings,
    PortfolioLimit,
    PortfolioConfigurationVersion,
    PortfolioLifecycleEvent,
    PortfolioAuditEvent,
)
from backend.app.modules.portfolio_management.portfolio_creation.schemas import (
    PortfolioCreateRequest,
    PortfolioUpdateRequest,
    BaseCurrencyChangeRequest,
    PortfolioStrategyCreateRequest,
    PortfolioStrategyAssignRequest,
    PortfolioMandateCreateRequest,
    PortfolioMandateAssignRequest,
    PortfolioBenchmarkAssignRequest,
    PortfolioOwnershipAssignRequest,
    PortfolioHierarchyAssignRequest,
    PortfolioValuationSettingsRequest,
    PortfolioAccountingSettingsRequest,
    PortfolioLimitCreateRequest,
    LifecycleTransitionRequest,
)
from backend.app.modules.portfolio_management.portfolio_creation.repositories.repository import PortfolioRepository
from backend.app.modules.portfolio_management.portfolio_creation.state_machine.transitions import validate_lifecycle_transition


class PortfolioCreationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = PortfolioRepository(session)

    # -----------------------------------------------------------------------
    # PORTFOLIO REGISTRATION
    # -----------------------------------------------------------------------
    async def create_portfolio(self, req: PortfolioCreateRequest, actor_id: str = "SYSTEM") -> Portfolio:
        # Check uniqueness of portfolio_code
        existing = await self.repo.get_by_code(req.portfolio_code)
        if existing:
            raise ValueError(f"Portfolio code '{req.portfolio_code}' already exists.")

        portfolio_id = f"PF_{uuid.uuid4().hex[:12].upper()}"
        effective_from = req.effective_from or date.today()

        portfolio = Portfolio(
            portfolio_id=portfolio_id,
            portfolio_code=req.portfolio_code,
            portfolio_name=req.portfolio_name,
            short_name=req.short_name,
            description=req.description,
            portfolio_type=req.portfolio_type,
            lifecycle_status=PortfolioLifecycleStatus.DRAFT,
            creation_source=req.creation_source,
            base_currency=req.base_currency.upper(),
            market_scope=req.market_scope,
            asset_class_scope=req.asset_class_scope,
            current_configuration_version=1,
            effective_from=effective_from,
            created_by=actor_id,
        )

        portfolio = await self.repo.create_portfolio(portfolio)

        # Initialize default valuation and accounting settings
        val_settings = PortfolioValuationSettings(
            portfolio_id=portfolio_id,
            valuation_calendar_id="DEFAULT_DAILY_CALENDAR",
            effective_from=effective_from,
            configuration_version=1,
        )
        await self.repo.set_valuation_settings(val_settings)

        acc_settings = PortfolioAccountingSettings(
            portfolio_id=portfolio_id,
            effective_from=effective_from,
            policy_version=1,
        )
        await self.repo.set_accounting_settings(acc_settings)

        # Record Initial Snapshot
        await self._create_snapshot(portfolio, actor_id, "Initial portfolio creation")

        # Audit
        await self.repo.record_audit_event(
            PortfolioAuditEvent(
                audit_id=f"AUD_{uuid.uuid4().hex[:8].upper()}",
                portfolio_id=portfolio_id,
                action_type="CREATE",
                entity_type="PORTFOLIO",
                entity_id=portfolio_id,
                new_state=json.dumps({"code": req.portfolio_code, "name": req.portfolio_name, "currency": req.base_currency}),
                actor_id=actor_id,
                reason="Initial registration",
            )
        )

        await self.session.commit()
        await self.session.refresh(portfolio)
        return portfolio

    async def update_portfolio(self, portfolio_id: str, req: PortfolioUpdateRequest, actor_id: str = "SYSTEM") -> Portfolio:
        portfolio = await self.repo.get_by_id(portfolio_id)
        if not portfolio:
            raise ValueError(f"Portfolio '{portfolio_id}' not found.")

        if req.portfolio_name:
            portfolio.portfolio_name = req.portfolio_name
        if req.short_name:
            portfolio.short_name = req.short_name
        if req.description is not None:
            portfolio.description = req.description
        if req.market_scope:
            portfolio.market_scope = req.market_scope
        if req.asset_class_scope:
            portfolio.asset_class_scope = req.asset_class_scope

        portfolio.current_configuration_version += 1
        await self._create_snapshot(portfolio, actor_id, "Metadata update")

        await self.repo.record_audit_event(
            PortfolioAuditEvent(
                audit_id=f"AUD_{uuid.uuid4().hex[:8].upper()}",
                portfolio_id=portfolio_id,
                action_type="UPDATE_METADATA",
                entity_type="PORTFOLIO",
                entity_id=portfolio_id,
                actor_id=actor_id,
                reason="Metadata updated",
            )
        )

        await self.session.commit()
        await self.session.refresh(portfolio)
        return portfolio

    async def change_base_currency(self, portfolio_id: str, req: BaseCurrencyChangeRequest, actor_id: str = "SYSTEM") -> Portfolio:
        portfolio = await self.repo.get_by_id(portfolio_id)
        if not portfolio:
            raise ValueError(f"Portfolio '{portfolio_id}' not found.")

        old_curr = portfolio.base_currency
        new_curr = req.new_base_currency.upper()
        if old_curr == new_curr:
            return portfolio

        portfolio.base_currency = new_curr
        portfolio.current_configuration_version += 1

        # Update currency conversion policy reference in valuation settings
        val_settings = PortfolioValuationSettings(
            portfolio_id=portfolio_id,
            valuation_calendar_id="DEFAULT_DAILY_CALENDAR",
            currency_conversion_policy_id=req.fx_policy_reference or "DAILY_OFFICIAL_FX",
            effective_from=req.effective_date,
            configuration_version=portfolio.current_configuration_version,
        )
        await self.repo.set_valuation_settings(val_settings)

        await self._create_snapshot(
            portfolio,
            actor_id,
            f"Base currency changed from {old_curr} to {new_curr}: {req.change_reason}",
        )

        await self.repo.record_audit_event(
            PortfolioAuditEvent(
                audit_id=f"AUD_{uuid.uuid4().hex[:8].upper()}",
                portfolio_id=portfolio_id,
                action_type="BASE_CURRENCY_CHANGE",
                entity_type="PORTFOLIO",
                entity_id=portfolio_id,
                previous_state=old_curr,
                new_state=new_curr,
                actor_id=actor_id,
                reason=req.change_reason,
            )
        )

        await self.session.commit()
        await self.session.refresh(portfolio)
        return portfolio

    # -----------------------------------------------------------------------
    # STRATEGY & MANDATE
    # -----------------------------------------------------------------------
    async def create_strategy(self, req: PortfolioStrategyCreateRequest) -> PortfolioStrategy:
        existing = await self.repo.get_strategy_by_code(req.strategy_code)
        if existing:
            raise ValueError(f"Strategy '{req.strategy_code}' already exists.")

        strategy = PortfolioStrategy(
            strategy_code=req.strategy_code,
            strategy_name=req.strategy_name,
            strategy_family=req.strategy_family,
            description=req.description,
            supported_asset_classes=req.supported_asset_classes,
            supported_markets=req.supported_markets,
        )
        strategy = await self.repo.create_strategy(strategy)
        await self.session.commit()
        await self.session.refresh(strategy)
        return strategy

    async def assign_strategy(self, portfolio_id: str, req: PortfolioStrategyAssignRequest, actor_id: str = "SYSTEM") -> PortfolioStrategyAssignment:
        portfolio = await self.repo.get_by_id(portfolio_id)
        if not portfolio:
            raise ValueError(f"Portfolio '{portfolio_id}' not found.")

        strategy = await self.repo.get_strategy_by_code(req.strategy_code)
        if not strategy:
            raise ValueError(f"Strategy '{req.strategy_code}' not found.")

        assignment = PortfolioStrategyAssignment(
            portfolio_id=portfolio_id,
            strategy_code=req.strategy_code,
            is_primary=req.is_primary,
            assignment_reason=req.assignment_reason,
            effective_from=req.effective_from or date.today(),
        )
        assignment = await self.repo.assign_strategy(assignment)

        portfolio.current_configuration_version += 1
        await self._create_snapshot(portfolio, actor_id, f"Assigned strategy {req.strategy_code}")

        await self.session.commit()
        await self.session.refresh(assignment)
        return assignment

    async def create_mandate(self, req: PortfolioMandateCreateRequest, actor_id: str = "SYSTEM") -> PortfolioMandate:
        existing = await self.repo.get_mandate_by_code(req.mandate_code)
        if existing:
            raise ValueError(f"Mandate '{req.mandate_code}' already exists.")

        mandate = PortfolioMandate(
            mandate_code=req.mandate_code,
            mandate_name=req.mandate_name,
            mandate_type=req.mandate_type,
            investment_objective=req.investment_objective,
            permitted_markets=req.permitted_markets,
            permitted_asset_classes=req.permitted_asset_classes,
            short_selling_permitted=req.short_selling_permitted,
            leverage_permitted=req.leverage_permitted,
            configuration_json=req.configuration_json,
            created_by=actor_id,
        )
        mandate = await self.repo.create_mandate(mandate)
        await self.session.commit()
        await self.session.refresh(mandate)
        return mandate

    async def assign_mandate(self, portfolio_id: str, req: PortfolioMandateAssignRequest, actor_id: str = "SYSTEM") -> PortfolioMandateAssignment:
        portfolio = await self.repo.get_by_id(portfolio_id)
        if not portfolio:
            raise ValueError(f"Portfolio '{portfolio_id}' not found.")

        mandate = await self.repo.get_mandate_by_code(req.mandate_code)
        if not mandate:
            raise ValueError(f"Mandate '{req.mandate_code}' not found.")

        assignment = PortfolioMandateAssignment(
            portfolio_id=portfolio_id,
            mandate_code=req.mandate_code,
            effective_from=req.effective_from or date.today(),
            assigned_by=actor_id,
        )
        assignment = await self.repo.assign_mandate(assignment)

        portfolio.current_configuration_version += 1
        await self._create_snapshot(portfolio, actor_id, f"Assigned mandate {req.mandate_code}")

        await self.session.commit()
        await self.session.refresh(assignment)
        return assignment

    # -----------------------------------------------------------------------
    # BENCHMARKS
    # -----------------------------------------------------------------------
    async def assign_benchmark(self, portfolio_id: str, req: PortfolioBenchmarkAssignRequest, actor_id: str = "SYSTEM") -> PortfolioBenchmark:
        portfolio = await self.repo.get_by_id(portfolio_id)
        if not portfolio:
            raise ValueError(f"Portfolio '{portfolio_id}' not found.")

        assoc_id = f"BM_{uuid.uuid4().hex[:8].upper()}"
        benchmark = PortfolioBenchmark(
            association_id=assoc_id,
            portfolio_id=portfolio_id,
            benchmark_reference_id=req.benchmark_reference_id,
            benchmark_name=req.benchmark_name,
            benchmark_type=req.benchmark_type,
            benchmark_currency=req.benchmark_currency.upper(),
            is_primary=req.is_primary,
            benchmark_weight=req.benchmark_weight,
            effective_from=req.effective_from or date.today(),
            source_reference=req.source_reference,
        )
        benchmark = await self.repo.add_benchmark(benchmark)

        portfolio.current_configuration_version += 1
        await self._create_snapshot(portfolio, actor_id, f"Assigned benchmark {req.benchmark_reference_id}")

        await self.session.commit()
        await self.session.refresh(benchmark)
        return benchmark

    # -----------------------------------------------------------------------
    # OWNERSHIP
    # -----------------------------------------------------------------------
    async def assign_ownership(self, portfolio_id: str, req: PortfolioOwnershipAssignRequest, actor_id: str = "SYSTEM") -> PortfolioOwnership:
        portfolio = await self.repo.get_by_id(portfolio_id)
        if not portfolio:
            raise ValueError(f"Portfolio '{portfolio_id}' not found.")

        own_id = f"OWN_{uuid.uuid4().hex[:8].upper()}"
        ownership = PortfolioOwnership(
            ownership_id=own_id,
            portfolio_id=portfolio_id,
            ownership_type=req.ownership_type,
            owner_entity_id=req.owner_entity_id,
            owner_name=req.owner_name,
            ownership_role=req.ownership_role,
            is_primary_owner=req.is_primary_owner,
            effective_from=req.effective_from or date.today(),
            assigned_by=actor_id,
        )
        ownership = await self.repo.add_ownership(ownership)

        portfolio.current_configuration_version += 1
        await self._create_snapshot(portfolio, actor_id, f"Assigned ownership {req.owner_name}")

        await self.session.commit()
        await self.session.refresh(ownership)
        return ownership

    # -----------------------------------------------------------------------
    # HIERARCHY & CYCLE DETECTION
    # -----------------------------------------------------------------------
    async def assign_hierarchy(self, parent_portfolio_id: str, req: PortfolioHierarchyAssignRequest, actor_id: str = "SYSTEM") -> PortfolioHierarchy:
        parent = await self.repo.get_by_id(parent_portfolio_id)
        if not parent:
            raise ValueError(f"Parent portfolio '{parent_portfolio_id}' not found.")

        child = await self.repo.get_by_id(req.child_portfolio_id)
        if not child:
            raise ValueError(f"Child portfolio '{req.child_portfolio_id}' not found.")

        # Check for circular hierarchy or self-parenting
        if parent_portfolio_id == req.child_portfolio_id:
            raise ValueError("A portfolio cannot be its own parent.")

        is_cycle = await self.repo.check_cycle(parent_portfolio_id, req.child_portfolio_id)
        if is_cycle:
            raise ValueError(f"Circular hierarchy detected: '{parent_portfolio_id}' is already a descendant of '{req.child_portfolio_id}'.")

        rel_id = f"HIER_{uuid.uuid4().hex[:8].upper()}"
        rel = PortfolioHierarchy(
            relationship_id=rel_id,
            parent_portfolio_id=parent_portfolio_id,
            child_portfolio_id=req.child_portfolio_id,
            relationship_type=req.relationship_type,
            allocation_weight=req.allocation_weight,
            aggregation_method=req.aggregation_method,
            effective_from=req.effective_from or date.today(),
            created_by=actor_id,
        )
        rel = await self.repo.add_hierarchy_relationship(rel)

        parent.current_configuration_version += 1
        await self._create_snapshot(parent, actor_id, f"Added child portfolio {req.child_portfolio_id}")

        await self.session.commit()
        await self.session.refresh(rel)
        return rel

    # -----------------------------------------------------------------------
    # VALUATION & ACCOUNTING SETTINGS
    # -----------------------------------------------------------------------
    async def update_valuation_settings(
        self, portfolio_id: str, req: PortfolioValuationSettingsRequest, actor_id: str = "SYSTEM"
    ) -> PortfolioValuationSettings:
        portfolio = await self.repo.get_by_id(portfolio_id)
        if not portfolio:
            raise ValueError(f"Portfolio '{portfolio_id}' not found.")

        portfolio.current_configuration_version += 1
        val_settings = PortfolioValuationSettings(
            portfolio_id=portfolio_id,
            valuation_calendar_id=req.valuation_calendar_id,
            valuation_frequency=req.valuation_frequency,
            cutoff_time=req.cutoff_time,
            cutoff_timezone=req.cutoff_timezone,
            price_selection_policy_id=req.price_selection_policy_id,
            currency_conversion_policy_id=req.currency_conversion_policy_id,
            effective_from=req.effective_from or date.today(),
            configuration_version=portfolio.current_configuration_version,
        )
        val_settings = await self.repo.set_valuation_settings(val_settings)

        await self._create_snapshot(portfolio, actor_id, "Updated valuation settings")
        await self.session.commit()
        await self.session.refresh(val_settings)
        return val_settings

    async def update_accounting_settings(
        self, portfolio_id: str, req: PortfolioAccountingSettingsRequest, actor_id: str = "SYSTEM"
    ) -> PortfolioAccountingSettings:
        portfolio = await self.repo.get_by_id(portfolio_id)
        if not portfolio:
            raise ValueError(f"Portfolio '{portfolio_id}' not found.")

        portfolio.current_configuration_version += 1
        acc_settings = PortfolioAccountingSettings(
            portfolio_id=portfolio_id,
            trade_accounting_basis=req.trade_accounting_basis,
            cost_basis_method=req.cost_basis_method,
            dividend_accrual_method=req.dividend_accrual_method,
            corporate_action_policy_id=req.corporate_action_policy_id,
            rounding_precision_places=req.rounding_precision_places,
            effective_from=req.effective_from or date.today(),
            policy_version=portfolio.current_configuration_version,
        )
        acc_settings = await self.repo.set_accounting_settings(acc_settings)

        await self._create_snapshot(portfolio, actor_id, "Updated accounting settings")
        await self.session.commit()
        await self.session.refresh(acc_settings)
        return acc_settings

    # -----------------------------------------------------------------------
    # LIMITS
    # -----------------------------------------------------------------------
    async def create_limit(self, portfolio_id: str, req: PortfolioLimitCreateRequest, actor_id: str = "SYSTEM") -> PortfolioLimit:
        portfolio = await self.repo.get_by_id(portfolio_id)
        if not portfolio:
            raise ValueError(f"Portfolio '{portfolio_id}' not found.")

        limit_id = f"LIM_{uuid.uuid4().hex[:8].upper()}"
        portfolio.current_configuration_version += 1

        limit_obj = PortfolioLimit(
            limit_id=limit_id,
            portfolio_id=portfolio_id,
            limit_code=req.limit_code,
            limit_name=req.limit_name,
            limit_category=req.limit_category,
            limit_scope=req.limit_scope,
            scope_reference=req.scope_reference,
            comparison_operator=req.comparison_operator,
            threshold_value=req.threshold_value,
            threshold_unit=req.threshold_unit,
            currency=req.currency,
            warning_threshold=req.warning_threshold,
            hard_threshold=req.hard_threshold,
            effective_from=req.effective_from or date.today(),
            policy_version=portfolio.current_configuration_version,
            created_by=actor_id,
        )
        limit_obj = await self.repo.add_limit(limit_obj)

        await self._create_snapshot(portfolio, actor_id, f"Added limit {req.limit_code}")
        await self.session.commit()
        await self.session.refresh(limit_obj)
        return limit_obj

    # -----------------------------------------------------------------------
    # LIFECYCLE MANAGEMENT
    # -----------------------------------------------------------------------
    async def transition_lifecycle(
        self,
        portfolio_id: str,
        target_status: PortfolioLifecycleStatus,
        req: Optional[LifecycleTransitionRequest] = None,
        actor_id: str = "SYSTEM"
    ) -> Portfolio:
        portfolio = await self.repo.get_by_id(portfolio_id)
        if not portfolio:
            raise ValueError(f"Portfolio '{portfolio_id}' not found.")

        current = portfolio.lifecycle_status
        if current == target_status:
            return portfolio

        # Validate transition against state machine
        if not validate_lifecycle_transition(current, target_status):
            raise ValueError(f"Invalid lifecycle transition from '{current.value}' to '{target_status.value}'.")

        # Activation gate checks
        if target_status == PortfolioLifecycleStatus.ACTIVE:
            self._validate_activation_readiness(portfolio)

        event_id = f"EVT_{uuid.uuid4().hex[:8].upper()}"
        eff_date = req.effective_date if req and req.effective_date else date.today()
        reason = req.reason if req else None
        appr_ref = req.approval_reference if req else None

        portfolio.lifecycle_status = target_status
        if target_status == PortfolioLifecycleStatus.APPROVED and actor_id != "SYSTEM":
            portfolio.approved_by = actor_id

        evt = PortfolioLifecycleEvent(
            event_id=event_id,
            portfolio_id=portfolio_id,
            previous_status=current,
            new_status=target_status,
            effective_date=eff_date,
            actor_id=actor_id,
            reason=reason,
            approval_reference=appr_ref,
        )
        await self.repo.record_lifecycle_event(evt)

        portfolio.current_configuration_version += 1
        await self._create_snapshot(portfolio, actor_id, f"Status changed to {target_status.value}: {reason}")

        await self.session.commit()
        await self.session.refresh(portfolio)
        return portfolio

    def _validate_activation_readiness(self, portfolio: Portfolio):
        """Validates that mandatory fields and settings are configured before activation."""
        if not portfolio.base_currency:
            raise ValueError("Activation requires a valid base currency.")
        if not portfolio.portfolio_code:
            raise ValueError("Activation requires a portfolio code.")

    # -----------------------------------------------------------------------
    # SNAPSHOTS & HISTORY
    # -----------------------------------------------------------------------
    async def _create_snapshot(self, portfolio: Portfolio, actor_id: str, reason: str):
        val_settings = await self.repo.get_valuation_settings(portfolio.portfolio_id)
        acc_settings = await self.repo.get_accounting_settings(portfolio.portfolio_id)
        benchmarks = await self.repo.list_benchmarks(portfolio.portfolio_id)
        strategies = await self.repo.list_strategy_assignments(portfolio.portfolio_id)

        snapshot_data = {
            "portfolio_id": portfolio.portfolio_id,
            "portfolio_code": portfolio.portfolio_code,
            "portfolio_name": portfolio.portfolio_name,
            "base_currency": portfolio.base_currency,
            "market_scope": portfolio.market_scope.value if hasattr(portfolio.market_scope, 'value') else str(portfolio.market_scope),
            "lifecycle_status": portfolio.lifecycle_status.value if hasattr(portfolio.lifecycle_status, 'value') else str(portfolio.lifecycle_status),
            "valuation_calendar_id": val_settings.valuation_calendar_id if val_settings else "DEFAULT_DAILY_CALENDAR",
            "accounting_basis": acc_settings.trade_accounting_basis.value if acc_settings and hasattr(acc_settings.trade_accounting_basis, 'value') else "TRADE_DATE",
            "benchmarks": [bm.benchmark_reference_id for bm in benchmarks],
            "strategies": [st.strategy_code for st in strategies],
        }

        ver = PortfolioConfigurationVersion(
            portfolio_id=portfolio.portfolio_id,
            version_number=portfolio.current_configuration_version,
            snapshot_json=json.dumps(snapshot_data),
            valid_from=portfolio.effective_from,
            created_by=actor_id,
            change_reason=reason,
        )
        await self.repo.save_configuration_version(ver)

