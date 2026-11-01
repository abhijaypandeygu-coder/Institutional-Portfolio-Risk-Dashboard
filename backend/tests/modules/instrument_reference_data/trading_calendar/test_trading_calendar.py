import pytest
import uuid
from datetime import date, datetime, time
from zoneinfo import ZoneInfo
import httpx

from backend.app.main import app
from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.modules.instrument_reference_data.trading_calendar.models import (
    CalendarStatus,
    HolidayCategory,
    TradingImpact,
    SessionType,
    ExceptionType,
    TradingDayClassification
)
from backend.app.modules.instrument_reference_data.trading_calendar.schemas import (
    ExchangeCalendarCreate,
    MarketSessionCreate,
    ExchangeHolidayCreate,
    CalendarExceptionCreate
)
from backend.app.modules.instrument_reference_data.trading_calendar.services.service import TradingCalendarService
from backend.app.modules.instrument_reference_data.trading_calendar.calculations.local_to_utc import (
    local_to_utc,
    utc_to_local,
    get_utc_offset_str
)


@pytest.fixture(autouse=True)
async def setup_database():
    await init_db()
    yield


@pytest.mark.asyncio
async def test_timezone_calculations_and_dst():
    # 1. India (Asia/Kolkata) - UTC+05:30 (No DST)
    dt_kol = datetime(2026, 6, 15, 9, 15)
    utc_kol = local_to_utc(dt_kol, "Asia/Kolkata")
    assert utc_kol.hour == 3
    assert utc_kol.minute == 45
    assert get_utc_offset_str(dt_kol, "Asia/Kolkata") == "+05:30"

    # 2. US Eastern Standard Time (EST) - Winter (e.g. 2026-01-15) -> UTC-05:00
    dt_ny_winter = datetime(2026, 1, 15, 9, 30)
    utc_ny_winter = local_to_utc(dt_ny_winter, "America/New_York")
    assert utc_ny_winter.hour == 14
    assert utc_ny_winter.minute == 30
    assert get_utc_offset_str(dt_ny_winter, "America/New_York") == "-05:00"

    # 3. US Eastern Daylight Time (EDT) - Summer (e.g. 2026-06-15) -> UTC-04:00
    dt_ny_summer = datetime(2026, 6, 15, 9, 30)
    utc_ny_summer = local_to_utc(dt_ny_summer, "America/New_York")
    assert utc_ny_summer.hour == 13
    assert utc_ny_summer.minute == 30
    assert get_utc_offset_str(dt_ny_summer, "America/New_York") == "-04:00"


@pytest.mark.asyncio
async def test_nse_calendar_sessions_and_holiday():
    async with AsyncSessionLocal() as session:
        service = TradingCalendarService(session)
        cal_id = f"CAL_NSE_{uuid.uuid4().hex[:6].upper()}"

        # Create NSE calendar
        cal = await service.create_calendar(
            ExchangeCalendarCreate(
                calendar_id=cal_id,
                exchange_code=f"NSE_{uuid.uuid4().hex[:4].upper()}",
                exchange_name="National Stock Exchange of India",
                market_country="IND",
                timezone_name="Asia/Kolkata",
                effective_from=date(2026, 1, 1)
            )
        )

        # Add Pre-open session (09:00 - 09:15)
        await service.add_session(
            MarketSessionCreate(
                session_id=f"SESS_PRE_{uuid.uuid4().hex[:6].upper()}",
                calendar_id=cal.calendar_id,
                session_code="PRE_OPEN",
                session_name="NSE Pre-Open",
                session_type=SessionType.PRE_OPEN,
                local_start_time=time(9, 0),
                local_end_time=time(9, 15),
                session_sequence=1
            )
        )

        # Add Regular session (09:15 - 15:30)
        await service.add_session(
            MarketSessionCreate(
                session_id=f"SESS_REG_{uuid.uuid4().hex[:6].upper()}",
                calendar_id=cal.calendar_id,
                session_code="REGULAR",
                session_name="NSE Regular Trading",
                session_type=SessionType.REGULAR_TRADING,
                local_start_time=time(9, 15),
                local_end_time=time(15, 30),
                session_sequence=2
            )
        )

        # Add Republic Day Holiday (2026-01-26, Monday)
        await service.add_holiday(
            ExchangeHolidayCreate(
                holiday_id=f"HOL_{uuid.uuid4().hex[:6].upper()}",
                calendar_id=cal.calendar_id,
                holiday_date=date(2026, 1, 26),
                holiday_name="Republic Day",
                trading_impact=TradingImpact.FULL_MARKET_CLOSURE
            )
        )

        # Query regular trading day (2026-01-27, Tuesday)
        reg_sched = await service.get_day_schedule(cal.exchange_code, date(2026, 1, 27))
        assert reg_sched.is_trading_day is True
        assert reg_sched.classification == TradingDayClassification.REGULAR_TRADING_DAY
        assert len(reg_sched.sessions) == 2

        # Query holiday (2026-01-26, Monday)
        hol_sched = await service.get_day_schedule(cal.exchange_code, date(2026, 1, 26))
        assert hol_sched.is_trading_day is False
        assert hol_sched.classification == TradingDayClassification.HOLIDAY
        assert hol_sched.holiday_name == "Republic Day"

        # Resolve timestamp during regular session (11:00 IST)
        t_query = datetime(2026, 1, 27, 11, 0)
        res = await service.resolve_session(cal.exchange_code, t_query)
        assert res.is_trading_day is True
        assert res.session_classification == SessionType.REGULAR_TRADING
        assert res.scheduled_trading_permitted is True


@pytest.mark.asyncio
async def test_nyse_early_close_and_emergency_closure():
    async with AsyncSessionLocal() as session:
        service = TradingCalendarService(session)
        cal_id = f"CAL_NYSE_{uuid.uuid4().hex[:6].upper()}"

        cal = await service.create_calendar(
            ExchangeCalendarCreate(
                calendar_id=cal_id,
                exchange_code=f"NYSE_{uuid.uuid4().hex[:4].upper()}",
                exchange_name="New York Stock Exchange",
                market_country="USA",
                timezone_name="America/New_York",
                effective_from=date(2026, 1, 1)
            )
        )

        # Regular trading (09:30 - 16:00)
        await service.add_session(
            MarketSessionCreate(
                session_id=f"SESS_NYSE_{uuid.uuid4().hex[:6].upper()}",
                calendar_id=cal.calendar_id,
                session_code="REGULAR",
                session_name="NYSE Regular Hours",
                session_type=SessionType.REGULAR_TRADING,
                local_start_time=time(9, 30),
                local_end_time=time(16, 0),
                session_sequence=1
            )
        )

        # 1. Early close on Black Friday (2026-11-27) at 13:00
        await service.add_exception(
            CalendarExceptionCreate(
                exception_id=f"EXC_EARLY_{uuid.uuid4().hex[:6].upper()}",
                calendar_id=cal.calendar_id,
                exception_date=date(2026, 11, 27),
                exception_type=ExceptionType.EARLY_CLOSE,
                affected_session_type=SessionType.REGULAR_TRADING,
                replacement_end_time=time(13, 0),
                reason="Day after Thanksgiving early close"
            )
        )

        sched_early = await service.get_day_schedule(cal.exchange_code, date(2026, 11, 27))
        assert sched_early.classification == TradingDayClassification.PARTIAL_TRADING_DAY
        assert sched_early.sessions[0].local_end.time() == time(13, 0)

        # 2. Emergency market closure (2026-12-01)
        await service.add_exception(
            CalendarExceptionCreate(
                exception_id=f"EXC_EMERG_{uuid.uuid4().hex[:6].upper()}",
                calendar_id=cal.calendar_id,
                exception_date=date(2026, 12, 1),
                exception_type=ExceptionType.EMERGENCY_SCHEDULE_CHANGE,
                trading_impact=TradingImpact.FULL_MARKET_CLOSURE,
                reason="Severe hurricane emergency shutdown"
            )
        )

        sched_emerg = await service.get_day_schedule(cal.exchange_code, date(2026, 12, 1))
        assert sched_emerg.is_trading_day is False
        assert sched_emerg.classification == TradingDayClassification.EMERGENCY_CLOSURE


@pytest.mark.asyncio
async def test_next_and_previous_trading_day_lookup():
    async with AsyncSessionLocal() as session:
        service = TradingCalendarService(session)
        cal_id = f"CAL_LOOKUP_{uuid.uuid4().hex[:6].upper()}"

        cal = await service.create_calendar(
            ExchangeCalendarCreate(
                calendar_id=cal_id,
                exchange_code=f"EXCH_{uuid.uuid4().hex[:4].upper()}",
                exchange_name="Lookup Test Exchange",
                market_country="IND",
                timezone_name="Asia/Kolkata",
                effective_from=date(2026, 1, 1)
            )
        )

        await service.add_session(
            MarketSessionCreate(
                session_id=f"SESS_LOOKUP_{uuid.uuid4().hex[:6].upper()}",
                calendar_id=cal.calendar_id,
                session_code="REGULAR",
                session_name="Regular Hours",
                session_type=SessionType.REGULAR_TRADING,
                local_start_time=time(9, 15),
                local_end_time=time(15, 30)
            )
        )

        # Friday: 2026-05-01, Weekend: 05-02 & 05-03, Holiday: 2026-05-04 (Monday)
        await service.add_holiday(
            ExchangeHolidayCreate(
                holiday_id=f"HOL_LOOKUP_{uuid.uuid4().hex[:6].upper()}",
                calendar_id=cal.calendar_id,
                holiday_date=date(2026, 5, 4),
                holiday_name="Special Bank Holiday"
            )
        )

        # Next trading day from Friday (2026-05-01) should skip Sat, Sun, Mon and return Tuesday (2026-05-05)
        next_day = await service.get_next_trading_day(cal.exchange_code, date(2026, 5, 1))
        assert next_day == date(2026, 5, 5)

        # Previous trading day from Tuesday (2026-05-05) should skip Mon, Sun, Sat and return Friday (2026-05-01)
        prev_day = await service.get_previous_trading_day(cal.exchange_code, date(2026, 5, 5))
        assert prev_day == date(2026, 5, 1)


@pytest.mark.asyncio
async def test_rest_api_lifecycle():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        rand_id = uuid.uuid4().hex[:6].upper()
        cal_id = f"API_CAL_{rand_id}"
        exch_code = f"API_EX_{rand_id}"

        # 1. Create Calendar
        cal_payload = {
            "calendar_id": cal_id,
            "exchange_code": exch_code,
            "exchange_name": "API Test Exchange",
            "market_country": "USA",
            "timezone_name": "America/New_York",
            "effective_from": "2026-01-01"
        }
        res_cal = await client.post("/api/v1/trading-calendars", json=cal_payload)
        assert res_cal.status_code == 201

        # 2. Add Session
        sess_payload = {
            "session_id": f"API_SESS_{rand_id}",
            "calendar_id": cal_id,
            "session_code": "REG",
            "session_name": "Regular",
            "session_type": "REGULAR_TRADING",
            "local_start_time": "09:30:00",
            "local_end_time": "16:00:00"
        }
        res_sess = await client.post("/api/v1/trading-calendars/sessions", json=sess_payload)
        assert res_sess.status_code == 201

        # 3. Lookup day schedule
        res_day = await client.get(f"/api/v1/trading-calendars/lookup/day?exchange_code={exch_code}&target_date=2026-07-15")
        assert res_day.status_code == 200
        data_day = res_day.json()
        assert data_day["is_trading_day"] is True
        assert len(data_day["sessions"]) == 1
        assert data_day["timezone_name"] == "America/New_York"

        # 4. Resolve session
        res_res = await client.get(f"/api/v1/trading-calendars/lookup/session?exchange_code={exch_code}&query_time=2026-07-15T10:30:00")
        assert res_res.status_code == 200
        data_res = res_res.json()
        assert data_res["session_classification"] == "REGULAR_TRADING"
        assert data_res["scheduled_trading_permitted"] is True
