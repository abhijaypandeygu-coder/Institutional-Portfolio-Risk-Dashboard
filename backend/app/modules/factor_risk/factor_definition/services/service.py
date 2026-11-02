"""
M08.01 Factor Definition Service Layer.
Orchestrates:
1. Canonical Factor seeding (Market, Size, Value, Momentum, Quality for India and US)
2. Custom Factor definition and immutable version creation
3. Characteristic decomposition and formula validation
4. Factor Model composition with pinned exact factor version membership
5. Governance lifecycle state transitions (Draft -> Review -> Approved -> Active -> Deprecated)
6. Deterministic SHA-256 recipe hash generation and point-in-time consistency
"""
from datetime import datetime, date
from decimal import Decimal
import uuid
from typing import List, Dict, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.factor_risk.factor_definition.models import (
    FactorDefinition,
    FactorDefinitionVersion,
    FactorCharacteristic,
    FactorModel,
    FactorModelVersion,
    FactorModelMembership,
    FactorFamily,
    FactorType,
    ConstructionType,
    FactorLifecycleStatus,
    CharacteristicDirection,
    StandardizationMethod,
    MarketScope,
)
from backend.app.modules.factor_risk.factor_definition.schemas import (
    CreateFactorDefinitionRequest,
    CreateFactorVersionRequest,
    FactorDefinitionResponse,
    FactorDefinitionVersionResponse,
    CharacteristicItemSchema,
    GovernanceActionRequest,
    CreateFactorModelRequest,
    FactorModelResponse,
    FactorModelVersionResponse,
    FactorModelMemberSchema,
)
from backend.app.modules.factor_risk.factor_definition.repositories.repository import (
    FactorDefinitionRepository,
)
from backend.app.modules.factor_risk.factor_definition.definitions.canonical_recipes import (
    compute_deterministic_hash,
    get_canonical_market_recipe,
    get_canonical_size_recipe,
    get_canonical_value_recipe,
    get_canonical_momentum_recipe,
    get_canonical_quality_recipe,
)


class FactorDefinitionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = FactorDefinitionRepository(session)

    def _build_version_response(self, v: FactorDefinitionVersion) -> FactorDefinitionVersionResponse:
        chars = [
            CharacteristicItemSchema(
                characteristic_code=c.characteristic_code,
                characteristic_name=c.characteristic_name,
                source_field_reference=c.source_field_reference,
                formula_specification=c.formula_specification,
                unit=c.unit,
                characteristic_direction=c.characteristic_direction,
                standardization_method=c.standardization_method,
                winsorization_pct=c.winsorization_pct,
                component_weight=c.component_weight,
                missing_data_policy=c.missing_data_policy,
            )
            for c in v.characteristics
        ]
        return FactorDefinitionVersionResponse(
            version_id=v.version_id,
            factor_id=v.factor_id,
            version_number=v.version_number,
            market_scope=v.market_scope,
            currency=v.currency,
            frequency=v.frequency,
            return_type=v.return_type,
            return_direction=v.return_direction,
            construction_specification=v.construction_specification,
            source_metadata=v.source_metadata,
            definition_hash=v.definition_hash,
            approval_status=v.approval_status,
            effective_from=v.effective_from,
            effective_to=v.effective_to,
            approved_by=v.approved_by,
            approved_at=v.approved_at,
            change_rationale=v.change_rationale,
            created_at=v.created_at,
            characteristics=chars,
        )

    def _build_factor_response(self, f: FactorDefinition) -> FactorDefinitionResponse:
        latest_ver = None
        if f.versions:
            # Sort by version_number descending
            sorted_vers = sorted(f.versions, key=lambda x: x.version_number, reverse=True)
            latest_ver = self._build_version_response(sorted_vers[0])

        return FactorDefinitionResponse(
            factor_id=f.factor_id,
            factor_code=f.factor_code,
            factor_name=f.factor_name,
            factor_family=f.factor_family,
            factor_type=f.factor_type,
            description=f.description,
            economic_interpretation=f.economic_interpretation,
            construction_type=f.construction_type,
            current_version_number=f.current_version_number,
            lifecycle_status=f.lifecycle_status,
            latest_version=latest_ver,
            created_at=f.created_at,
        )

    async def create_factor(self, req: CreateFactorDefinitionRequest) -> FactorDefinitionResponse:
        """Create a new factor identity along with initial v1 definition."""
        existing = await self.repo.get_factor_by_code(req.factor_code.upper())
        if existing:
            raise ValueError(f"Factor with code {req.factor_code} already exists")

        f_id = str(uuid.uuid4())
        v_id = str(uuid.uuid4())

        # Compute deterministic hash of specification
        hash_payload = {
            "factor_code": req.factor_code.upper(),
            "market_scope": req.market_scope.value,
            "currency": req.currency,
            "frequency": req.frequency,
            "return_type": req.return_type,
            "construction_specification": req.construction_specification,
            "characteristics": [c.model_dump(mode="json") for c in req.characteristics] if req.characteristics else [],
        }
        recipe_hash = compute_deterministic_hash(hash_payload)

        direction = req.construction_specification.get("return_direction", "LONG_MINUS_SHORT")
        if req.factor_family == FactorFamily.MARKET:
            direction = req.construction_specification.get("return_basis", "EXCESS_RETURN")

        v1 = FactorDefinitionVersion(
            version_id=v_id,
            factor_id=f_id,
            version_number=1,
            market_scope=req.market_scope,
            currency=req.currency,
            frequency=req.frequency,
            return_type=req.return_type,
            return_direction=direction,
            construction_specification=req.construction_specification,
            source_metadata=req.source_metadata,
            definition_hash=recipe_hash,
            approval_status=FactorLifecycleStatus.DRAFT,
            effective_from=date.today(),
            change_rationale=req.change_rationale,
            created_at=datetime.utcnow(),
            characteristics=[],
        )

        if req.characteristics:
            for c in req.characteristics:
                char_rec = FactorCharacteristic(
                    version_id=v_id,
                    characteristic_code=c.characteristic_code,
                    characteristic_name=c.characteristic_name,
                    source_field_reference=c.source_field_reference,
                    formula_specification=c.formula_specification,
                    unit=c.unit,
                    characteristic_direction=c.characteristic_direction,
                    standardization_method=c.standardization_method,
                    winsorization_pct=c.winsorization_pct,
                    component_weight=c.component_weight,
                    missing_data_policy=c.missing_data_policy,
                )
                v1.characteristics.append(char_rec)

        factor = FactorDefinition(
            factor_id=f_id,
            factor_code=req.factor_code.upper(),
            factor_name=req.factor_name,
            factor_family=req.factor_family,
            factor_type=req.factor_type,
            description=req.description,
            economic_interpretation=req.economic_interpretation,
            construction_type=req.construction_type,
            current_version_number=1,
            lifecycle_status=FactorLifecycleStatus.DRAFT,
            created_at=datetime.utcnow(),
        )
        factor.versions.append(v1)

        saved = await self.repo.save_factor(factor)
        return self._build_factor_response(saved)

    async def create_new_version(
        self, factor_id: str, req: CreateFactorVersionRequest
    ) -> FactorDefinitionVersionResponse:
        """Create a new immutable version for an existing factor."""
        factor = await self.repo.get_factor_by_id(factor_id)
        if not factor:
            raise ValueError(f"Factor {factor_id} not found")

        new_version_num = factor.current_version_number + 1
        v_id = str(uuid.uuid4())

        hash_payload = {
            "factor_code": factor.factor_code,
            "version_number": new_version_num,
            "market_scope": req.market_scope.value,
            "currency": req.currency,
            "frequency": req.frequency,
            "return_type": req.return_type,
            "construction_specification": req.construction_specification,
            "characteristics": [c.model_dump(mode="json") for c in req.characteristics] if req.characteristics else [],
        }
        recipe_hash = compute_deterministic_hash(hash_payload)

        direction = req.construction_specification.get("return_direction", "LONG_MINUS_SHORT")
        if factor.factor_family == FactorFamily.MARKET:
            direction = req.construction_specification.get("return_basis", "EXCESS_RETURN")

        new_ver = FactorDefinitionVersion(
            version_id=v_id,
            factor_id=factor.factor_id,
            version_number=new_version_num,
            market_scope=req.market_scope,
            currency=req.currency,
            frequency=req.frequency,
            return_type=req.return_type,
            return_direction=direction,
            construction_specification=req.construction_specification,
            source_metadata=req.source_metadata,
            definition_hash=recipe_hash,
            approval_status=FactorLifecycleStatus.DRAFT,
            effective_from=date.today(),
            change_rationale=req.change_rationale,
            created_at=datetime.utcnow(),
            characteristics=[],
        )

        if req.characteristics:
            for c in req.characteristics:
                char_rec = FactorCharacteristic(
                    version_id=v_id,
                    characteristic_code=c.characteristic_code,
                    characteristic_name=c.characteristic_name,
                    source_field_reference=c.source_field_reference,
                    formula_specification=c.formula_specification,
                    unit=c.unit,
                    characteristic_direction=c.characteristic_direction,
                    standardization_method=c.standardization_method,
                    winsorization_pct=c.winsorization_pct,
                    component_weight=c.component_weight,
                    missing_data_policy=c.missing_data_policy,
                )
                new_ver.characteristics.append(char_rec)

        factor.current_version_number = new_version_num
        await self.repo.save_version(new_ver)
        await self.repo.save_factor(factor)

        return self._build_version_response(new_ver)

    async def apply_governance_action(
        self, version_id: str, req: GovernanceActionRequest
    ) -> FactorDefinitionVersionResponse:
        """Handle lifecycle transitions: SUBMIT, APPROVE, REJECT, ACTIVATE, DEPRECATE."""
        ver = await self.repo.get_version_by_id(version_id)
        if not ver:
            raise ValueError(f"Factor version {version_id} not found")

        action = req.action.upper()
        now = datetime.utcnow()

        if action == "SUBMIT":
            if ver.approval_status != FactorLifecycleStatus.DRAFT:
                raise ValueError("Only DRAFT versions can be submitted for review")
            ver.approval_status = FactorLifecycleStatus.PENDING_REVIEW

        elif action == "APPROVE":
            if ver.approval_status not in [FactorLifecycleStatus.PENDING_REVIEW, FactorLifecycleStatus.DRAFT]:
                raise ValueError("Only PENDING_REVIEW or DRAFT versions can be approved")
            ver.approval_status = FactorLifecycleStatus.APPROVED
            ver.approved_by = req.actor
            ver.approved_at = now

        elif action == "ACTIVATE":
            if ver.approval_status != FactorLifecycleStatus.APPROVED:
                raise ValueError("Only APPROVED versions can be activated into production")
            ver.approval_status = FactorLifecycleStatus.ACTIVE
            # Also update parent factor lifecycle status
            parent = await self.repo.get_factor_by_id(ver.factor_id)
            if parent:
                parent.lifecycle_status = FactorLifecycleStatus.ACTIVE
                await self.repo.save_factor(parent)

        elif action == "REJECT":
            ver.approval_status = FactorLifecycleStatus.REJECTED

        elif action == "DEPRECATE":
            ver.approval_status = FactorLifecycleStatus.DEPRECATED
        else:
            raise ValueError(f"Unknown governance action: {action}")

        if req.rationale:
            ver.change_rationale = (ver.change_rationale or "") + f" | [{action}] {req.rationale}"

        saved = await self.repo.save_version(ver)
        return self._build_version_response(saved)

    # ------------------------------------------------------------------------
    # FACTOR MODEL MANAGEMENT
    # ------------------------------------------------------------------------

    async def create_factor_model(self, req: CreateFactorModelRequest) -> FactorModelResponse:
        """Create a new factor model with exact pinned factor definition versions."""
        existing = await self.repo.get_model_by_code(req.model_code.upper())
        if existing:
            raise ValueError(f"Model with code {req.model_code} already exists")

        # Verify all factor versions exist
        pinned_members: List[FactorDefinitionVersion] = []
        for vid in req.factor_version_ids:
            v = await self.repo.get_version_by_id(vid)
            if not v:
                raise ValueError(f"Factor version {vid} not found")
            pinned_members.append(v)

        m_id = str(uuid.uuid4())
        mv_id = str(uuid.uuid4())

        # Construct deterministic hash
        hash_payload = {
            "model_code": req.model_code.upper(),
            "market_scope": req.market_scope.value,
            "currency_basis": req.currency_basis,
            "return_frequency": req.return_frequency,
            "pinned_versions": [
                {"position": idx + 1, "version_id": v.version_id, "definition_hash": v.definition_hash}
                for idx, v in enumerate(pinned_members)
            ],
        }
        model_hash = compute_deterministic_hash(hash_payload)

        mv1 = FactorModelVersion(
            model_version_id=mv_id,
            model_id=m_id,
            version_number=1,
            model_definition_hash=model_hash,
            approval_status=FactorLifecycleStatus.DRAFT,
            effective_from=date.today(),
            change_rationale=req.change_rationale,
            created_at=datetime.utcnow(),
        )

        for idx, v in enumerate(pinned_members):
            parent_f = await self.repo.get_factor_by_id(v.factor_id)
            code = parent_f.factor_code if parent_f else f"FAC_{idx+1}"
            mem = FactorModelMembership(
                model_version_id=mv_id,
                factor_id=v.factor_id,
                version_id=v.version_id,
                factor_code=code,
                factor_position=idx + 1,
            )
            mv1.memberships.append(mem)

        model = FactorModel(
            model_id=m_id,
            model_code=req.model_code.upper(),
            model_name=req.model_name,
            description=req.description,
            market_scope=req.market_scope,
            currency_basis=req.currency_basis,
            return_frequency=req.return_frequency,
            lifecycle_status=FactorLifecycleStatus.DRAFT,
            current_version_number=1,
            created_at=datetime.utcnow(),
        )
        model.model_versions.append(mv1)

        saved = await self.repo.save_model(model)
        return self._build_model_response(saved)

    def _build_model_response(self, m: FactorModel) -> FactorModelResponse:
        latest_ver = None
        if m.model_versions:
            sorted_vers = sorted(m.model_versions, key=lambda x: x.version_number, reverse=True)
            v = sorted_vers[0]
            mems = [
                FactorModelMemberSchema(
                    factor_position=mem.factor_position,
                    factor_id=mem.factor_id,
                    version_id=mem.version_id,
                    factor_code=mem.factor_code,
                )
                for mem in sorted(v.memberships, key=lambda x: x.factor_position)
            ]
            latest_ver = FactorModelVersionResponse(
                model_version_id=v.model_version_id,
                model_id=v.model_id,
                version_number=v.version_number,
                model_definition_hash=v.model_definition_hash,
                approval_status=v.approval_status,
                effective_from=v.effective_from,
                effective_to=v.effective_to,
                approved_by=v.approved_by,
                approved_at=v.approved_at,
                memberships=mems,
                created_at=v.created_at,
            )

        return FactorModelResponse(
            model_id=m.model_id,
            model_code=m.model_code,
            model_name=m.model_name,
            description=m.description,
            market_scope=m.market_scope,
            currency_basis=m.currency_basis,
            return_frequency=m.return_frequency,
            lifecycle_status=m.lifecycle_status,
            current_version_number=m.current_version_number,
            latest_version=latest_ver,
            created_at=m.created_at,
        )

    async def seed_canonical_equity_factors(self, market: MarketScope = MarketScope.INDIA) -> List[FactorDefinitionResponse]:
        """
        Seed the mandatory initial factor universe:
        Market (MKT), Size (SMB), Value (HML), Momentum (MOM), Quality (QMJ).
        """
        canonical_defs = [
            (
                f"MKT_{market.value}",
                f"{market.value.title()} Market Factor",
                FactorFamily.MARKET,
                FactorType.MARKET_RETURN_FACTOR,
                ConstructionType.INTERNALLY_CONSTRUCTED,
                f"Broad equity-market excess return for {market.value}",
                "Represents macroeconomic and systemic equity risk exposure (CAPM beta driver).",
                get_canonical_market_recipe(market, excess_return=True),
                [],
            ),
            (
                f"SMB_{market.value}",
                f"{market.value.title()} Size Factor (Small Minus Big)",
                FactorFamily.SIZE,
                FactorType.LONG_SHORT_PORTFOLIO_FACTOR,
                ConstructionType.INTERNALLY_CONSTRUCTED,
                "Return spread between small-cap and large-cap equity portfolios.",
                "Captures liquidity premium, business-cycle risk, and size anomaly.",
                get_canonical_size_recipe(market),
                [],
            ),
            (
                f"HML_{market.value}",
                f"{market.value.title()} Value Factor (High Minus Low)",
                FactorFamily.VALUE,
                FactorType.LONG_SHORT_PORTFOLIO_FACTOR,
                ConstructionType.INTERNALLY_CONSTRUCTED,
                "Return spread between high book-to-market and low book-to-market portfolios.",
                "Compensates for distress risk, operating rigidity, and mean-reverting valuation multiples.",
                get_canonical_value_recipe(market),
                [],
            ),
            (
                f"MOM_{market.value}",
                f"{market.value.title()} Momentum Factor (Winners Minus Losers)",
                FactorFamily.MOMENTUM,
                FactorType.LONG_SHORT_PORTFOLIO_FACTOR,
                ConstructionType.INTERNALLY_CONSTRUCTED,
                "12-1 momentum spread between past winner and loser equities.",
                "Captures price-trend persistence driven by investor underreaction and capital flows.",
                get_canonical_momentum_recipe(market),
                [],
            ),
            (
                f"QMJ_{market.value}",
                f"{market.value.title()} Quality Factor (Quality Minus Junk)",
                FactorFamily.QUALITY,
                FactorType.COMPOSITE_FACTOR,
                ConstructionType.INTERNALLY_CONSTRUCTED,
                "Composite factor ranking profitability (ROE), safety (leverage), and earnings quality (accruals).",
                "Compensates for superior balance-sheet strength, competitive moats, and stable cash flows.",
                get_canonical_quality_recipe(market),
                [
                    CharacteristicItemSchema(
                        characteristic_code="PROFITABILITY_ROE",
                        characteristic_name="Return on Equity",
                        source_field_reference="net_income / common_equity",
                        formula_specification="NET_INCOME / BOOK_EQUITY",
                        characteristic_direction=CharacteristicDirection.HIGHER_IS_BETTER,
                        component_weight=Decimal("0.40"),
                    ),
                    CharacteristicItemSchema(
                        characteristic_code="FINANCIAL_SAFETY_LEVERAGE",
                        characteristic_name="Debt to Equity",
                        source_field_reference="total_debt / common_equity",
                        formula_specification="TOTAL_DEBT / BOOK_EQUITY",
                        characteristic_direction=CharacteristicDirection.LOWER_IS_BETTER,
                        component_weight=Decimal("0.30"),
                    ),
                    CharacteristicItemSchema(
                        characteristic_code="EARNINGS_QUALITY_ACCRUALS",
                        characteristic_name="Accruals Ratio",
                        source_field_reference="(net_income - ocf) / total_assets",
                        formula_specification="(NET_INCOME - OCF) / ASSETS",
                        characteristic_direction=CharacteristicDirection.LOWER_IS_BETTER,
                        component_weight=Decimal("0.30"),
                    ),
                ],
            ),
        ]

        responses = []
        for code, name, family, ftype, ctype, desc, econ, spec, chars in canonical_defs:
            existing = await self.repo.get_factor_by_code(code)
            if existing:
                responses.append(self._build_factor_response(existing))
            else:
                req = CreateFactorDefinitionRequest(
                    factor_code=code,
                    factor_name=name,
                    factor_family=family,
                    factor_type=ftype,
                    description=desc,
                    economic_interpretation=econ,
                    construction_type=ctype,
                    market_scope=market,
                    currency="INR" if market == MarketScope.INDIA else "USD",
                    construction_specification=spec,
                    characteristics=chars,
                    change_rationale=f"Canonical baseline seed for {market.value}",
                )
                res = await self.create_factor(req)
                responses.append(res)

        return responses
