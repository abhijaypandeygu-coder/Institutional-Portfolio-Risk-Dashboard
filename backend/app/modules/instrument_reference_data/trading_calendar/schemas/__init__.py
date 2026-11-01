from datetime import date, datetime, time
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from backend.app.modules.instrument_reference_data.trading_calendar.models import (
    CalendarStatus,
    HolidayCategory,
    TradingImpact,
    SessionType,
    ExceptionType,
    ExceptionStatus,
    TradingDayClassification
)


class ExchangeCalendarCreate(BaseModel):
    calendar_id: str = Field(..., min_length=3, max_length=64)
    exchange_code: str = Field(..., min_length=2, max_length=32)
    exchange_name: str = Field(..., min_length=2, max_length=128)
    market_country: str = Field(..., min_length=2, max_length=3)
    timezone_name: str = Field(..., min_length=3, max_length=64)
    market_segment: str = "EQUITY_CASH"
    effective_from: date
    effective_to: Optional[date] = None


class ExchangeCalendarResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    calendar_id: str
    exchange_code: str
    exchange_name: str
    market_country: str
    timezone_name: str
    market_segment: str
    calendar_status: CalendarStatus
    current_version: int
    effective_from: date
    effective_to: Optional[date] = None
    created_at: datetime
    updated_at: datetime


class MarketSessionCreate(BaseModel):
    session_id: str = Field(..., min_length=3, max_length=64)
    calendar_id: str
    session_code: str
    session_name: str
    session_type: SessionType
    local_start_time: time
    local_end_time: time
    start_inclusive: bool = True
    end_inclusive: bool = False
    session_sequence: int = 1
    order_entry_permitted: bool = True
    trade_matching_permitted: bool = True
    data_capture_expected: bool = True
    weekdays: str = "0,1,2,3,4"


class MarketSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: str
    calendar_id: str
    session_code: str
    session_name: str
    session_type: SessionType
    local_start_time: time
    local_end_time: time
    start_inclusive: bool
    end_inclusive: bool
    session_sequence: int
    order_entry_permitted: bool
    trade_matching_permitted: bool
    data_capture_expected: bool
    weekdays: str
    active_status: bool


class ExchangeHolidayCreate(BaseModel):
    holiday_id: str = Field(..., min_length=3, max_length=64)
    calendar_id: str
    holiday_date: date
    holiday_name: str
    holiday_category: HolidayCategory = HolidayCategory.EXCHANGE_HOLIDAY
    trading_impact: TradingImpact = TradingImpact.FULL_MARKET_CLOSURE
    source_reference: str = "OFFICIAL_CIRCULAR"


class ExchangeHolidayResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    holiday_id: str
    calendar_id: str
    holiday_date: date
    holiday_name: str
    holiday_category: HolidayCategory
    trading_impact: TradingImpact
    source_reference: str
    verified: bool


class CalendarExceptionCreate(BaseModel):
    exception_id: str = Field(..., min_length=3, max_length=64)
    calendar_id: str
    exception_date: date
    exception_type: ExceptionType
    affected_session_type: Optional[SessionType] = None
    replacement_start_time: Optional[time] = None
    replacement_end_time: Optional[time] = None
    trading_impact: TradingImpact = TradingImpact.SESSION_MODIFICATION
    reason: str
    source_reference: str = "OFFICIAL_CIRCULAR"


class CalendarExceptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    exception_id: str
    calendar_id: str
    exception_date: date
    exception_type: ExceptionType
    exception_status: ExceptionStatus
    affected_session_type: Optional[SessionType] = None
    replacement_start_time: Optional[time] = None
    replacement_end_time: Optional[time] = None
    trading_impact: TradingImpact
    reason: str
    source_reference: str


class SessionOccurrence(BaseModel):
    session_code: str
    session_name: str
    session_type: SessionType
    local_start: datetime
    local_end: datetime
    utc_start: datetime
    utc_end: datetime
    utc_offset: str
    order_entry_permitted: bool
    trade_matching_permitted: bool
    data_capture_expected: bool


class DayScheduleResponse(BaseModel):
    exchange_code: str
    calendar_id: str
    trading_date: date
    classification: TradingDayClassification
    is_trading_day: bool
    timezone_name: str
    holiday_name: Optional[str] = None
    exceptions_applied: List[str] = []
    sessions: List[SessionOccurrence] = []


class SessionResolutionResponse(BaseModel):
    exchange_code: str
    calendar_id: str
    resolved_trading_date: date
    local_datetime: datetime
    utc_datetime: datetime
    utc_offset: str
    is_trading_day: bool
    session_classification: SessionType
    active_session: Optional[SessionOccurrence] = None
    scheduled_trading_permitted: bool
    reason: Optional[str] = None
