import pytest
import uuid
from decimal import Decimal
from datetime import date, datetime, time
import httpx

from backend.app.main import app
from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.modules.instrument_reference_data.instrument_master.services.service import InstrumentMasterService
from backend.app.modules.instrument_reference_data.instrument_master.schemas import InstrumentCreateRequest
from backend.app.modules.instrument_reference_data.trading_calendar.services.service import TradingCalendarService
from backend.app.modules.instrument_reference_data.trading_calendar.schemas import (
    ExchangeCalendarCreate,
    MarketSessionCreate,
    ExchangeHolidayCreate
)
from backend.app.modules.instrument_reference_data.trading_calendar.models import SessionType
from backend.app.modules.instrument_reference_data.price_reference.models import (
    PriceReferenceType,
    PriceOrigin,
    PriceBasis,
    CurrencyBasis,
    VerificationStatus,
    ResolutionStatus
)
from backend.app.modules.instrument_reference_data.price_reference.schemas import (
    PriceReferenceObservationCreate,
    ResolvePreviousCloseRequest,
    RegisterCurrencyConversionRequest
)
from backend.app.modules.instrument_reference_data.price_reference.services.service import PriceReferenceService
from backend.app.modules.instrument_reference_data.price_reference.calculations.currency_conversion import convert_currency_price


@pytest.fixture(autouse=True)
async def setup_database():
    await init_db()
    yield


@pytest.fixture
async def sample_instrument_and_calendar():
    async with AsyncSessionLocal() as session:
        rand_id = uuid.uuid4().hex[:6].upper()
        
        # 1. Create canonical instrument
        inst = await InstrumentMasterService.create_instrument(
            session,
            InstrumentCreateRequest(
                canonical_name=f"Price Ref Test Instrument {rand_id}",
                short_name=f"TEST_PR_{rand_id}",
                instrument_type="COMMON_STOCK",
                asset_class="EQUITY",
                issue_currency="USD"
            ),
            actor_id="admin"
        )

        # 2. Create exchange calendar
        cal_service = TradingCalendarService(session)
        cal_id = f"CAL_PR_{rand_id}"
        exch_code = f"EX_{rand_id}"
        cal = await cal_service.create_calendar(
            ExchangeCalendarCreate(
                calendar_id=cal_id,
                exchange_code=exch_code,
                exchange_name="Price Ref Test Exchange",
                market_country="USA",
                timezone_name="America/New_York",
                effective_from=date(2026, 1, 1)
            )
        )

        # Add regular session
        await cal_service.add_session(
            MarketSessionCreate(
                session_id=f"SESS_PR_{rand_id}",
                calendar_id=cal_id,
                session_code="REGULAR",
                session_name="Regular Hours",
                session_type=SessionType.REGULAR_TRADING,
                local_start_time=time(9, 30),
                local_end_time=time(16, 0)
            )
        )

        return inst, cal


@pytest.mark.asyncio
async def test_currency_conversion_pure_calculator():
    # 1. Direct rate conversion: USD to INR @ 83.50
    p_usd = Decimal("100.00")
    fx_rate = Decimal("83.50")
    p_inr = convert_currency_price(p_usd, fx_rate, direction="SOURCE_TO_TARGET")
    assert p_inr == Decimal("8350.000000")

    # 2. Reverse conversion: INR to USD @ 83.50
    p_back = convert_currency_price(p_inr, fx_rate, direction="TARGET_TO_SOURCE")
    assert p_back == Decimal("100.000000")


@pytest.mark.asyncio
async def test_official_close_registration(sample_instrument_and_calendar):
    inst, cal = sample_instrument_and_calendar
    async with AsyncSessionLocal() as session:
        service = PriceReferenceService(session)
        obs_id = f"OBS_CLOSE_{uuid.uuid4().hex[:6].upper()}"

        obs = await service.register_observation(
            PriceReferenceObservationCreate(
                price_reference_id=obs_id,
                instrument_id=inst.instrument_id,
                exchange_code=cal.exchange_code,
                trading_date=date(2026, 7, 1),
                reference_type=PriceReferenceType.OFFICIAL_CLOSE,
                price_value=Decimal("150.250000"),
                currency="USD",
                price_basis=PriceBasis.RAW,
                currency_basis=CurrencyBasis.NATIVE_CURRENCY,
                price_origin=PriceOrigin.EXCHANGE_OFFICIAL,
                verification_status=VerificationStatus.VERIFIED
            )
        )
        assert obs.price_reference_id == obs_id
        assert obs.price_value == Decimal("150.250000")
        assert obs.currency == "USD"
        assert obs.price_basis == PriceBasis.RAW
        assert obs.currency_basis == CurrencyBasis.NATIVE_CURRENCY


@pytest.mark.asyncio
async def test_calendar_aware_previous_close_resolution(sample_instrument_and_calendar):
    inst, cal = sample_instrument_and_calendar
    async with AsyncSessionLocal() as session:
        service = PriceReferenceService(session)
        cal_service = TradingCalendarService(session)

        # Register official close for Friday (2026-07-10)
        friday_obs_id = f"OBS_FRI_{uuid.uuid4().hex[:6].upper()}"
        await service.register_observation(
            PriceReferenceObservationCreate(
                price_reference_id=friday_obs_id,
                instrument_id=inst.instrument_id,
                exchange_code=cal.exchange_code,
                trading_date=date(2026, 7, 10),
                reference_type=PriceReferenceType.OFFICIAL_CLOSE,
                price_value=Decimal("180.500000"),
                currency="USD",
                price_basis=PriceBasis.RAW,
                currency_basis=CurrencyBasis.NATIVE_CURRENCY,
                price_origin=PriceOrigin.EXCHANGE_OFFICIAL,
                verification_status=VerificationStatus.VERIFIED
            )
        )

        # Add Monday (2026-07-13) as a Holiday
        await cal_service.add_holiday(
            ExchangeHolidayCreate(
                holiday_id=f"HOL_TEST_{uuid.uuid4().hex[:6].upper()}",
                calendar_id=cal.calendar_id,
                holiday_date=date(2026, 7, 13),
                holiday_name="Mid-Summer Holiday"
            )
        )

        # Resolve previous close for Tuesday (2026-07-14)
        # Should skip Monday (holiday), Sunday, Saturday and resolve to Friday (2026-07-10)
        res = await service.resolve_previous_close(
            ResolvePreviousCloseRequest(
                instrument_id=inst.instrument_id,
                exchange_code=cal.exchange_code,
                target_trading_date=date(2026, 7, 14)
            )
        )
        assert res.resolution_status == ResolutionStatus.RESOLVED
        assert res.previous_trading_date == date(2026, 7, 10)
        assert res.resolved_price_value == Decimal("180.500000")
        assert res.source_price_reference_id == friday_obs_id


@pytest.mark.asyncio
async def test_currency_conversion_lineage(sample_instrument_and_calendar):
    inst, cal = sample_instrument_and_calendar
    async with AsyncSessionLocal() as session:
        service = PriceReferenceService(session)
        orig_id = f"OBS_RAW_USD_{uuid.uuid4().hex[:6].upper()}"
        conv_id = f"OBS_CONV_INR_{uuid.uuid4().hex[:6].upper()}"

        # 1. Register raw USD close
        await service.register_observation(
            PriceReferenceObservationCreate(
                price_reference_id=orig_id,
                instrument_id=inst.instrument_id,
                exchange_code=cal.exchange_code,
                trading_date=date(2026, 8, 3),
                reference_type=PriceReferenceType.OFFICIAL_CLOSE,
                price_value=Decimal("100.000000"),
                currency="USD",
                price_basis=PriceBasis.RAW,
                currency_basis=CurrencyBasis.NATIVE_CURRENCY
            )
        )

        # 2. Convert to INR @ 83.25
        conv = await service.register_currency_conversion(
            RegisterCurrencyConversionRequest(
                converted_price_reference_id=conv_id,
                original_price_reference_id=orig_id,
                target_currency="INR",
                fx_rate=Decimal("83.25000000"),
                fx_pair="USD/INR",
                conversion_direction="SOURCE_TO_TARGET"
            )
        )
        assert conv.converted_price_reference_id == conv_id
        assert conv.original_price_reference_id == orig_id
        assert conv.source_currency == "USD"
        assert conv.target_currency == "INR"

        # Check converted observation record
        conv_obs = await service.repo.get_observation_by_id(conv_id)
        assert conv_obs is not None
        assert conv_obs.price_value == Decimal("8325.000000")
        assert conv_obs.currency == "INR"
        assert conv_obs.currency_basis == CurrencyBasis.CONVERTED_CURRENCY


@pytest.mark.asyncio
async def test_rest_api_lifecycle(sample_instrument_and_calendar):
    inst, cal = sample_instrument_and_calendar
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        rand_id = uuid.uuid4().hex[:6].upper()
        obs_id = f"API_OBS_{rand_id}"

        # 1. Register observation
        obs_payload = {
            "price_reference_id": obs_id,
            "instrument_id": inst.instrument_id,
            "exchange_code": cal.exchange_code,
            "trading_date": "2026-09-01",
            "reference_type": "OFFICIAL_CLOSE",
            "price_value": "250.75",
            "currency": "USD"
        }
        res_obs = await client.post("/api/v1/price-references/observations", json=obs_payload)
        assert res_obs.status_code == 201
        data = res_obs.json()
        assert data["price_reference_id"] == obs_id
        assert Decimal(data["price_value"]) == Decimal("250.750000")

        # 2. Get observation
        res_get = await client.get(f"/api/v1/price-references/observations/{obs_id}")
        assert res_get.status_code == 200
        assert res_get.json()["price_reference_id"] == obs_id

        # 3. List by instrument
        res_list = await client.get(f"/api/v1/price-references/instrument/{inst.instrument_id}")
        assert res_list.status_code == 200
        assert len(res_list.json()) >= 1

        # 4. Resolve previous close for 2026-09-02 (Wednesday)
        # Previous trading day is 2026-09-01 (Tuesday)
        resolve_payload = {
            "instrument_id": inst.instrument_id,
            "exchange_code": cal.exchange_code,
            "target_trading_date": "2026-09-02"
        }
        res_prev = await client.post("/api/v1/price-references/previous-close/resolve", json=resolve_payload)
        assert res_prev.status_code == 200
        data_prev = res_prev.json()
        assert data_prev["previous_trading_date"] == "2026-09-01"
        assert Decimal(data_prev["resolved_price_value"]) == Decimal("250.750000")

