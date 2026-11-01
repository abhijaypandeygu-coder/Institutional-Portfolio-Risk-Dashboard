from datetime import date, datetime, time, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from zoneinfo import ZoneInfo

from backend.app.modules.instrument_reference_data.trading_calendar.models import (
    ExchangeCalendar,
    MarketSessionDefinition,
    ExchangeHoliday,
    CalendarException,
    TradingDayClassification,
    SessionType,
    TradingImpact,
    ExceptionType,
    CalendarStatus
)
from backend.app.modules.instrument_reference_data.trading_calendar.schemas import (
    ExchangeCalendarCreate,
    MarketSessionCreate,
    ExchangeHolidayCreate,
    CalendarExceptionCreate,
    DayScheduleResponse,
    SessionOccurrence,
    SessionResolutionResponse
)
from backend.app.modules.instrument_reference_data.trading_calendar.repositories.repository import TradingCalendarRepository
from backend.app.modules.instrument_reference_data.trading_calendar.calculations.local_to_utc import (
    local_to_utc,
    utc_to_local,
    get_utc_offset_str
)


class TradingCalendarService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = TradingCalendarRepository(session)

    async def create_calendar(self, payload: ExchangeCalendarCreate) -> ExchangeCalendar:
        # Validate timezone name
        try:
            ZoneInfo(payload.timezone_name)
        except Exception:
            raise ValueError(f"Invalid IANA timezone name: '{payload.timezone_name}'")

        existing = await self.repo.get_calendar_by_id(payload.calendar_id)
        if existing:
            raise ValueError(f"Calendar with ID '{payload.calendar_id}' already exists.")

        calendar = ExchangeCalendar(
            calendar_id=payload.calendar_id,
            exchange_code=payload.exchange_code.upper(),
            exchange_name=payload.exchange_name,
            market_country=payload.market_country.upper(),
            timezone_name=payload.timezone_name,
            market_segment=payload.market_segment.upper(),
            effective_from=payload.effective_from,
            effective_to=payload.effective_to
        )
        await self.repo.add_calendar(calendar)
        await self.session.commit()
        await self.session.refresh(calendar)
        return calendar

    async def add_session(self, payload: MarketSessionCreate) -> MarketSessionDefinition:
        calendar = await self.repo.get_calendar_by_id(payload.calendar_id)
        if not calendar:
            raise ValueError(f"Calendar '{payload.calendar_id}' not found.")

        session_def = MarketSessionDefinition(
            session_id=payload.session_id,
            calendar_id=payload.calendar_id,
            session_code=payload.session_code,
            session_name=payload.session_name,
            session_type=payload.session_type,
            local_start_time=payload.local_start_time,
            local_end_time=payload.local_end_time,
            start_inclusive=payload.start_inclusive,
            end_inclusive=payload.end_inclusive,
            session_sequence=payload.session_sequence,
            order_entry_permitted=payload.order_entry_permitted,
            trade_matching_permitted=payload.trade_matching_permitted,
            data_capture_expected=payload.data_capture_expected,
            weekdays=payload.weekdays
        )
        await self.repo.add_session(session_def)
        await self.session.commit()
        await self.session.refresh(session_def)
        return session_def

    async def add_holiday(self, payload: ExchangeHolidayCreate) -> ExchangeHoliday:
        calendar = await self.repo.get_calendar_by_id(payload.calendar_id)
        if not calendar:
            raise ValueError(f"Calendar '{payload.calendar_id}' not found.")

        holiday = ExchangeHoliday(
            holiday_id=payload.holiday_id,
            calendar_id=payload.calendar_id,
            holiday_date=payload.holiday_date,
            holiday_name=payload.holiday_name,
            holiday_category=payload.holiday_category,
            trading_impact=payload.trading_impact,
            source_reference=payload.source_reference
        )
        await self.repo.add_holiday(holiday)
        await self.session.commit()
        await self.session.refresh(holiday)
        return holiday

    async def add_exception(self, payload: CalendarExceptionCreate) -> CalendarException:
        calendar = await self.repo.get_calendar_by_id(payload.calendar_id)
        if not calendar:
            raise ValueError(f"Calendar '{payload.calendar_id}' not found.")

        exception = CalendarException(
            exception_id=payload.exception_id,
            calendar_id=payload.calendar_id,
            exception_date=payload.exception_date,
            exception_type=payload.exception_type,
            affected_session_type=payload.affected_session_type,
            replacement_start_time=payload.replacement_start_time,
            replacement_end_time=payload.replacement_end_time,
            trading_impact=payload.trading_impact,
            reason=payload.reason,
            source_reference=payload.source_reference
        )
        await self.repo.add_exception(exception)
        await self.session.commit()
        await self.session.refresh(exception)
        return exception

    async def get_day_schedule(
        self,
        exchange_code: str,
        target_date: date,
        segment: str = "EQUITY_CASH"
    ) -> DayScheduleResponse:
        calendar = await self.repo.get_calendar_by_exchange(exchange_code, segment)
        if not calendar:
            raise ValueError(f"No active calendar found for exchange '{exchange_code}' segment '{segment}'.")

        weekday_idx = target_date.weekday() # 0 = Monday, 6 = Sunday
        exceptions = await self.repo.get_exceptions(calendar.calendar_id, target_date)
        holiday = await self.repo.get_holiday(calendar.calendar_id, target_date)

        # Precedence 1: Emergency closure
        emergency = next((e for e in exceptions if e.exception_type == ExceptionType.EMERGENCY_SCHEDULE_CHANGE and e.trading_impact == TradingImpact.FULL_MARKET_CLOSURE), None)
        if emergency:
            return DayScheduleResponse(
                exchange_code=calendar.exchange_code,
                calendar_id=calendar.calendar_id,
                trading_date=target_date,
                classification=TradingDayClassification.EMERGENCY_CLOSURE,
                is_trading_day=False,
                timezone_name=calendar.timezone_name,
                exceptions_applied=[f"EMERGENCY: {emergency.reason}"]
            )

        # Precedence 2: Special trading session (e.g. Muhurat trading on a weekend/holiday)
        special_session_exc = next((e for e in exceptions if e.exception_type == ExceptionType.SPECIAL_TRADING_SESSION), None)

        # Precedence 3: Holiday
        if holiday and holiday.trading_impact == TradingImpact.FULL_MARKET_CLOSURE and not special_session_exc:
            return DayScheduleResponse(
                exchange_code=calendar.exchange_code,
                calendar_id=calendar.calendar_id,
                trading_date=target_date,
                classification=TradingDayClassification.HOLIDAY,
                is_trading_day=False,
                timezone_name=calendar.timezone_name,
                holiday_name=holiday.holiday_name
            )

        # Precedence 4: Weekend check
        if weekday_idx >= 5 and not special_session_exc:
            return DayScheduleResponse(
                exchange_code=calendar.exchange_code,
                calendar_id=calendar.calendar_id,
                trading_date=target_date,
                classification=TradingDayClassification.NON_TRADING_DAY,
                is_trading_day=False,
                timezone_name=calendar.timezone_name
            )

        # Build sessions
        raw_sessions = await self.repo.get_sessions(calendar.calendar_id)
        day_sessions: List[SessionOccurrence] = []
        applied_excs = []
        is_partial = False

        if special_session_exc:
            applied_excs.append(f"SPECIAL_SESSION: {special_session_exc.reason}")
            # Construct special session
            s_time = special_session_exc.replacement_start_time or time(18, 15)
            e_time = special_session_exc.replacement_end_time or time(19, 15)
            loc_s = datetime.combine(target_date, s_time)
            loc_e = datetime.combine(target_date, e_time)
            utc_s = local_to_utc(loc_s, calendar.timezone_name)
            utc_e = local_to_utc(loc_e, calendar.timezone_name)
            day_sessions.append(SessionOccurrence(
                session_code="SPECIAL",
                session_name="Special Trading Session",
                session_type=SessionType.SPECIAL_SESSION,
                local_start=loc_s,
                local_end=loc_e,
                utc_start=utc_s,
                utc_end=utc_e,
                utc_offset=get_utc_offset_str(loc_s, calendar.timezone_name),
                order_entry_permitted=True,
                trade_matching_permitted=True,
                data_capture_expected=True
            ))
            return DayScheduleResponse(
                exchange_code=calendar.exchange_code,
                calendar_id=calendar.calendar_id,
                trading_date=target_date,
                classification=TradingDayClassification.SPECIAL_TRADING_DAY,
                is_trading_day=True,
                timezone_name=calendar.timezone_name,
                exceptions_applied=applied_excs,
                sessions=day_sessions
            )

        for s_def in raw_sessions:
            allowed_days = [int(x.strip()) for x in s_def.weekdays.split(",") if x.strip()]
            if weekday_idx not in allowed_days:
                continue

            start_t = s_def.local_start_time
            end_t = s_def.local_end_time

            # Check exceptions modifying this session
            early_close = next((e for e in exceptions if e.exception_type == ExceptionType.EARLY_CLOSE and (e.affected_session_type is None or e.affected_session_type == s_def.session_type)), None)
            late_open = next((e for e in exceptions if e.exception_type == ExceptionType.LATE_OPEN and (e.affected_session_type is None or e.affected_session_type == s_def.session_type)), None)

            if early_close and early_close.replacement_end_time and s_def.session_type == SessionType.REGULAR_TRADING:
                end_t = early_close.replacement_end_time
                applied_excs.append(f"EARLY_CLOSE: {early_close.reason}")
                is_partial = True

            if late_open and late_open.replacement_start_time and s_def.session_type == SessionType.REGULAR_TRADING:
                start_t = late_open.replacement_start_time
                applied_excs.append(f"LATE_OPEN: {late_open.reason}")
                is_partial = True

            loc_s = datetime.combine(target_date, start_t)
            loc_e = datetime.combine(target_date, end_t)
            utc_s = local_to_utc(loc_s, calendar.timezone_name)
            utc_e = local_to_utc(loc_e, calendar.timezone_name)
            offset_str = get_utc_offset_str(loc_s, calendar.timezone_name)

            day_sessions.append(SessionOccurrence(
                session_code=s_def.session_code,
                session_name=s_def.session_name,
                session_type=s_def.session_type,
                local_start=loc_s,
                local_end=loc_e,
                utc_start=utc_s,
                utc_end=utc_e,
                utc_offset=offset_str,
                order_entry_permitted=s_def.order_entry_permitted,
                trade_matching_permitted=s_def.trade_matching_permitted,
                data_capture_expected=s_def.data_capture_expected
            ))

        classification = TradingDayClassification.PARTIAL_TRADING_DAY if is_partial else TradingDayClassification.REGULAR_TRADING_DAY

        return DayScheduleResponse(
            exchange_code=calendar.exchange_code,
            calendar_id=calendar.calendar_id,
            trading_date=target_date,
            classification=classification,
            is_trading_day=len(day_sessions) > 0,
            timezone_name=calendar.timezone_name,
            exceptions_applied=applied_excs,
            sessions=day_sessions
        )

    async def resolve_session(
        self,
        exchange_code: str,
        query_time: datetime,
        segment: str = "EQUITY_CASH"
    ) -> SessionResolutionResponse:
        calendar = await self.repo.get_calendar_by_exchange(exchange_code, segment)
        if not calendar:
            raise ValueError(f"No active calendar found for exchange '{exchange_code}'.")

        # Convert to local time
        if query_time.tzinfo is not None:
            loc_dt = utc_to_local(query_time, calendar.timezone_name).replace(tzinfo=None)
            utc_dt = query_time if query_time.tzinfo == ZoneInfo("UTC") else query_time.astimezone(ZoneInfo("UTC"))
        else:
            loc_dt = query_time
            utc_dt = local_to_utc(loc_dt, calendar.timezone_name)

        target_date = loc_dt.date()
        day_sched = await self.get_day_schedule(exchange_code, target_date, segment)

        if not day_sched.is_trading_day:
            return SessionResolutionResponse(
                exchange_code=exchange_code,
                calendar_id=calendar.calendar_id,
                resolved_trading_date=target_date,
                local_datetime=loc_dt,
                utc_datetime=utc_dt,
                utc_offset=get_utc_offset_str(loc_dt, calendar.timezone_name),
                is_trading_day=False,
                session_classification=SessionType.CLOSED,
                scheduled_trading_permitted=False,
                reason=f"Date is {day_sched.classification.value}"
            )

        # Match active session
        active_sess: Optional[SessionOccurrence] = None
        for s in day_sched.sessions:
            if s.local_start <= loc_dt < s.local_end:
                active_sess = s
                break

        if active_sess:
            return SessionResolutionResponse(
                exchange_code=exchange_code,
                calendar_id=calendar.calendar_id,
                resolved_trading_date=target_date,
                local_datetime=loc_dt,
                utc_datetime=utc_dt,
                utc_offset=active_sess.utc_offset,
                is_trading_day=True,
                session_classification=active_sess.session_type,
                active_session=active_sess,
                scheduled_trading_permitted=active_sess.trade_matching_permitted
            )

        return SessionResolutionResponse(
            exchange_code=exchange_code,
            calendar_id=calendar.calendar_id,
            resolved_trading_date=target_date,
            local_datetime=loc_dt,
            utc_datetime=utc_dt,
            utc_offset=get_utc_offset_str(loc_dt, calendar.timezone_name),
            is_trading_day=True,
            session_classification=SessionType.CLOSED,
            scheduled_trading_permitted=False,
            reason="Timestamp falls outside configured active market sessions."
        )

    async def get_next_trading_day(
        self,
        exchange_code: str,
        start_date: date,
        segment: str = "EQUITY_CASH",
        max_lookahead_days: int = 30
    ) -> date:
        curr = start_date + timedelta(days=1)
        for _ in range(max_lookahead_days):
            sched = await self.get_day_schedule(exchange_code, curr, segment)
            if sched.is_trading_day:
                return curr
            curr += timedelta(days=1)
        raise ValueError(f"No trading day found within {max_lookahead_days} days after {start_date}")

    async def get_previous_trading_day(
        self,
        exchange_code: str,
        start_date: date,
        segment: str = "EQUITY_CASH",
        max_lookback_days: int = 30
    ) -> date:
        curr = start_date - timedelta(days=1)
        for _ in range(max_lookback_days):
            sched = await self.get_day_schedule(exchange_code, curr, segment)
            if sched.is_trading_day:
                return curr
            curr -= timedelta(days=1)
        raise ValueError(f"No trading day found within {max_lookback_days} days before {start_date}")
