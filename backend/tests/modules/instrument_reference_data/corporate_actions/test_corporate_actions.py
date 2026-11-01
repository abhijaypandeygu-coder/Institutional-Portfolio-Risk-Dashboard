import pytest
import uuid
from decimal import Decimal
from datetime import date, datetime
import httpx

from backend.app.main import app
from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.modules.instrument_reference_data.instrument_master.services.service import InstrumentMasterService
from backend.app.modules.instrument_reference_data.instrument_master.schemas import InstrumentCreateRequest
from backend.app.modules.instrument_reference_data.corporate_actions.models import (
    CorporateActionType,
    LifecycleStatus,
    ConsiderationType,
    GrossNetBasis
)
from backend.app.modules.instrument_reference_data.corporate_actions.schemas import (
    CorporateActionCreate,
    CorporateActionUpdate,
    DividendDetailCreate,
    RatioDetailCreate,
    MergerDetailCreate,
    CalculateAdjustmentRequest
)
from backend.app.modules.instrument_reference_data.corporate_actions.services.service import CorporateActionService
from backend.app.modules.instrument_reference_data.corporate_actions.calculations.split_calculator import compute_split_factors
from backend.app.modules.instrument_reference_data.corporate_actions.calculations.bonus_calculator import compute_bonus_factors
from backend.app.modules.instrument_reference_data.corporate_actions.calculations.dividend_calculator import compute_cash_dividend_factor
from backend.app.modules.instrument_reference_data.corporate_actions.calculations.cumulative_calculator import compound_factors


@pytest.fixture(autouse=True)
async def setup_database():
    await init_db()
    yield


@pytest.fixture
async def sample_instrument():
    async with AsyncSessionLocal() as session:
        rand_id = uuid.uuid4().hex[:6].upper()
        inst = await InstrumentMasterService.create_instrument(
            session,
            InstrumentCreateRequest(
                canonical_name=f"Corporate Action Test Asset {rand_id}",
                short_name=f"TEST_CA_{rand_id}",
                instrument_type="COMMON_STOCK",
                asset_class="EQUITY",
                issue_currency="USD"
            ),
            actor_id="admin"
        )
        return inst


@pytest.mark.asyncio
async def test_pure_calculators_mathematical_reciprocity():
    # 1. Split 2:1
    res_split = compute_split_factors(numerator=2, denominator=1)
    assert res_split["quantity_factor"] == Decimal("2.000000000000")
    assert res_split["price_factor"] == Decimal("0.500000000000")
    assert res_split["quantity_factor"] * res_split["price_factor"] == Decimal("1.000000000000")

    # 2. Reverse split 1:10
    res_rev = compute_split_factors(numerator=1, denominator=10)
    assert res_rev["quantity_factor"] == Decimal("0.100000000000")
    assert res_rev["price_factor"] == Decimal("10.000000000000")
    assert res_rev["quantity_factor"] * res_rev["price_factor"] == Decimal("1.000000000000")

    # 3. Bonus 1-for-4
    res_bonus = compute_bonus_factors(additional_shares=1, existing_shares=4)
    # F_Q = (4+1)/4 = 1.25, F_P = 4/(4+1) = 0.8
    assert res_bonus["quantity_factor"] == Decimal("1.250000000000")
    assert res_bonus["price_factor"] == Decimal("0.800000000000")
    assert res_bonus["quantity_factor"] * res_bonus["price_factor"] == Decimal("1.000000000000")

    # 4. Cash dividend
    res_div = compute_cash_dividend_factor(
        pre_event_price=Decimal("100.00"),
        dividend_amount=Decimal("5.00"),
        use_net_basis=False
    )
    # F_P = (100 - 5) / 100 = 0.95
    assert res_div["price_factor"] == Decimal("0.950000000000")
    assert res_div["quantity_factor"] == Decimal("1.000000000000")


@pytest.mark.asyncio
async def test_cash_dividend_lifecycle(sample_instrument):
    async with AsyncSessionLocal() as session:
        service = CorporateActionService(session)
        event_id = f"CA_DIV_{uuid.uuid4().hex[:6].upper()}"

        action = await service.create_corporate_action(
            CorporateActionCreate(
                event_id=event_id,
                corporate_action_type=CorporateActionType.CASH_DIVIDEND,
                lifecycle_status=LifecycleStatus.CONFIRMED,
                primary_instrument_id=sample_instrument.instrument_id,
                declaration_date=date(2026, 1, 15),
                ex_date=date(2026, 2, 1),
                record_date=date(2026, 2, 2),
                payment_date=date(2026, 2, 15),
                effective_date=date(2026, 2, 1),
                dividend_detail=DividendDetailCreate(
                    gross_amount=Decimal("2.50"),
                    currency="USD",
                    gross_net_basis=GrossNetBasis.GROSS
                )
            )
        )
        assert action.event_id == event_id
        assert action.current_version == 1

        # Calculate adjustment for observation before ex-date
        adj_res = await service.calculate_adjustments(
            CalculateAdjustmentRequest(
                instrument_id=sample_instrument.instrument_id,
                unadjusted_price=Decimal("100.00"),
                unadjusted_quantity=Decimal("1000.00"),
                as_of_date=date(2026, 1, 20)
            )
        )
        assert adj_res.total_events_applied == 1
        # Adjusted price: 100 * ((100 - 2.50)/100) = 97.50
        assert adj_res.final_adjusted_price == Decimal("97.500000")
        assert adj_res.final_adjusted_quantity == Decimal("1000.0000")
        assert len(adj_res.lineage) == 1
        assert adj_res.lineage[0].step_price_factor == Decimal("0.975000000000")


@pytest.mark.asyncio
async def test_stock_split_and_reverse_split_lifecycle(sample_instrument):
    async with AsyncSessionLocal() as session:
        service = CorporateActionService(session)
        split_id = f"CA_SPLIT_{uuid.uuid4().hex[:6].upper()}"

        action = await service.create_corporate_action(
            CorporateActionCreate(
                event_id=split_id,
                corporate_action_type=CorporateActionType.STOCK_SPLIT,
                lifecycle_status=LifecycleStatus.EFFECTIVE,
                primary_instrument_id=sample_instrument.instrument_id,
                ex_date=date(2026, 3, 1),
                effective_date=date(2026, 3, 1),
                ratio_detail=RatioDetailCreate(numerator=4, denominator=1)  # 4-for-1 split
            )
        )
        assert action.event_id == split_id

        # Calculate adjustments for observation before split
        adj_res = await service.calculate_adjustments(
            CalculateAdjustmentRequest(
                instrument_id=sample_instrument.instrument_id,
                unadjusted_price=Decimal("200.00"),
                unadjusted_quantity=Decimal("50.00"),
                as_of_date=date(2026, 2, 28)
            )
        )
        assert adj_res.total_events_applied == 1
        # 4:1 split -> price / 4 = 50.00, shares * 4 = 200.00
        assert adj_res.final_adjusted_price == Decimal("50.000000")
        assert adj_res.final_adjusted_quantity == Decimal("200.0000")
        # Invariant check: Market value preserved
        orig_val = Decimal("200.00") * Decimal("50.00")
        adj_val = adj_res.final_adjusted_price * adj_res.final_adjusted_quantity
        assert orig_val == adj_val


@pytest.mark.asyncio
async def test_cumulative_compounding_sequence(sample_instrument):
    async with AsyncSessionLocal() as session:
        service = CorporateActionService(session)
        rand_suffix = uuid.uuid4().hex[:4].upper()
        
        # Event 1: 2:1 Stock Split on 2026-04-01
        await service.create_corporate_action(
            CorporateActionCreate(
                event_id=f"EVT1_{rand_suffix}",
                corporate_action_type=CorporateActionType.STOCK_SPLIT,
                lifecycle_status=LifecycleStatus.EFFECTIVE,
                primary_instrument_id=sample_instrument.instrument_id,
                ex_date=date(2026, 4, 1),
                effective_date=date(2026, 4, 1),
                ratio_detail=RatioDetailCreate(numerator=2, denominator=1)
            )
        )
        
        # Event 2: Bonus Issue 1-for-4 on 2026-05-01
        await service.create_corporate_action(
            CorporateActionCreate(
                event_id=f"EVT2_{rand_suffix}",
                corporate_action_type=CorporateActionType.BONUS_ISSUE,
                lifecycle_status=LifecycleStatus.EFFECTIVE,
                primary_instrument_id=sample_instrument.instrument_id,
                ex_date=date(2026, 5, 1),
                effective_date=date(2026, 5, 1),
                ratio_detail=RatioDetailCreate(numerator=1, denominator=4, additional_shares=1, existing_shares=4)
            )
        )

        # Calculate adjustments for observation before both events (2026-03-15)
        adj_res = await service.calculate_adjustments(
            CalculateAdjustmentRequest(
                instrument_id=sample_instrument.instrument_id,
                unadjusted_price=Decimal("100.00"),
                unadjusted_quantity=Decimal("100.00"),
                as_of_date=date(2026, 3, 15)
            )
        )
        assert adj_res.total_events_applied == 2
        # After Event 1: Price=50, Shares=200
        # After Event 2: Price=50 * 0.8 = 40, Shares=200 * 1.25 = 250
        assert adj_res.final_adjusted_price == Decimal("40.000000")
        assert adj_res.final_adjusted_quantity == Decimal("250.0000")
        assert len(adj_res.lineage) == 2


@pytest.mark.asyncio
async def test_rest_api_lifecycle(sample_instrument):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        rand_id = uuid.uuid4().hex[:6].upper()
        event_id = f"API_SPLIT_{rand_id}"

        # 1. Register corporate action
        create_payload = {
            "event_id": event_id,
            "corporate_action_type": "STOCK_SPLIT",
            "lifecycle_status": "CONFIRMED",
            "primary_instrument_id": sample_instrument.instrument_id,
            "ex_date": "2026-06-01",
            "effective_date": "2026-06-01",
            "ratio_detail": {
                "numerator": 3,
                "denominator": 1
            }
        }
        res = await client.post("/api/v1/corporate-actions", json=create_payload)
        assert res.status_code == 201
        data = res.json()
        assert data["event_id"] == event_id
        assert data["current_version"] == 1

        # 2. Query event by ID
        get_res = await client.get(f"/api/v1/corporate-actions/{event_id}")
        assert get_res.status_code == 200
        assert get_res.json()["event_id"] == event_id

        # 3. Update / amend event
        update_payload = {
            "lifecycle_status": "EFFECTIVE",
            "description": "Amended status to effective after exchange approval"
        }
        put_res = await client.put(f"/api/v1/corporate-actions/{event_id}", json=update_payload)
        assert put_res.status_code == 200
        assert put_res.json()["current_version"] == 2
        assert put_res.json()["lifecycle_status"] == "EFFECTIVE"

        # 4. Calculate adjustments
        calc_payload = {
            "instrument_id": sample_instrument.instrument_id,
            "unadjusted_price": "300.00",
            "unadjusted_quantity": "100.00",
            "as_of_date": "2026-05-15"
        }
        calc_res = await client.post("/api/v1/corporate-actions/calculate-adjustments", json=calc_payload)
        assert calc_res.status_code == 200
        calc_data = calc_res.json()
        # 3:1 split -> 300 / 3 = 100.00, 100 * 3 = 300.00
        assert Decimal(calc_data["final_adjusted_price"]) == Decimal("100.000000")
        assert Decimal(calc_data["final_adjusted_quantity"]) == Decimal("300.0000")
        assert len(calc_data["lineage"]) >= 1
