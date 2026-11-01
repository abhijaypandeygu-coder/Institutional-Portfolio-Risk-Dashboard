from datetime import date
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.modules.instrument_reference_data.trading_calendar.models import (
    ExchangeCalendar,
    MarketSessionDefinition,
    ExchangeHoliday,
    CalendarException,
    ExceptionStatus
)


class TradingCalendarRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_calendar_by_id(self, calendar_id: str) -> Optional[ExchangeCalendar]:
        stmt = select(ExchangeCalendar).where(ExchangeCalendar.calendar_id == calendar_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_calendar_by_exchange(self, exchange_code: str, segment: str = "EQUITY_CASH") -> Optional[ExchangeCalendar]:
        stmt = (
            select(ExchangeCalendar)
            .where(
                ExchangeCalendar.exchange_code == exchange_code.upper(),
                ExchangeCalendar.market_segment == segment.upper()
            )
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_calendars(self) -> List[ExchangeCalendar]:
        stmt = select(ExchangeCalendar).order_by(ExchangeCalendar.exchange_code.asc())
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def add_calendar(self, calendar: ExchangeCalendar) -> ExchangeCalendar:
        self.session.add(calendar)
        await self.session.flush()
        return calendar

    async def get_sessions(self, calendar_id: str) -> List[MarketSessionDefinition]:
        stmt = (
            select(MarketSessionDefinition)
            .where(
                MarketSessionDefinition.calendar_id == calendar_id,
                MarketSessionDefinition.active_status == True
            )
            .order_by(MarketSessionDefinition.session_sequence.asc())
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def add_session(self, session_def: MarketSessionDefinition) -> MarketSessionDefinition:
        self.session.add(session_def)
        await self.session.flush()
        return session_def

    async def get_holiday(self, calendar_id: str, holiday_date: date) -> Optional[ExchangeHoliday]:
        stmt = (
            select(ExchangeHoliday)
            .where(
                ExchangeHoliday.calendar_id == calendar_id,
                ExchangeHoliday.holiday_date == holiday_date
            )
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def add_holiday(self, holiday: ExchangeHoliday) -> ExchangeHoliday:
        self.session.add(holiday)
        await self.session.flush()
        return holiday

    async def get_exceptions(self, calendar_id: str, target_date: date) -> List[CalendarException]:
        stmt = (
            select(CalendarException)
            .where(
                CalendarException.calendar_id == calendar_id,
                CalendarException.exception_date == target_date,
                CalendarException.exception_status == ExceptionStatus.APPROVED
            )
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def add_exception(self, exception: CalendarException) -> CalendarException:
        self.session.add(exception)
        await self.session.flush()
        return exception
