import enum
from datetime import datetime, date, time
from typing import Optional, List
from sqlalchemy import (
    String,
    Integer,
    Boolean,
    DateTime,
    Date,
    Time,
    ForeignKey,
    Text,
    Enum as SAEnum,
    UniqueConstraint
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from backend.app.core.database import Base


class CalendarStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    DEPRECATED = "DEPRECATED"


class HolidayCategory(str, enum.Enum):
    NATIONAL_HOLIDAY = "NATIONAL_HOLIDAY"
    RELIGIOUS_HOLIDAY = "RELIGIOUS_HOLIDAY"
    EXCHANGE_HOLIDAY = "EXCHANGE_HOLIDAY"
    MARKET_HOLIDAY = "MARKET_HOLIDAY"
    SETTLEMENT_HOLIDAY = "SETTLEMENT_HOLIDAY"
    EMERGENCY_CLOSURE = "EMERGENCY_CLOSURE"
    SPECIAL_NON_TRADING_DAY = "SPECIAL_NON_TRADING_DAY"
    OTHER = "OTHER"


class TradingImpact(str, enum.Enum):
    FULL_MARKET_CLOSURE = "FULL_MARKET_CLOSURE"
    SEGMENT_CLOSURE = "SEGMENT_CLOSURE"
    PARTIAL_SESSION_CLOSURE = "PARTIAL_SESSION_CLOSURE"
    SESSION_MODIFICATION = "SESSION_MODIFICATION"
    SETTLEMENT_ONLY = "SETTLEMENT_ONLY"
    NO_TRADING_IMPACT = "NO_TRADING_IMPACT"
    UNKNOWN = "UNKNOWN"


class SessionType(str, enum.Enum):
    PRE_OPEN = "PRE_OPEN"
    ORDER_ENTRY = "ORDER_ENTRY"
    ORDER_MODIFICATION = "ORDER_MODIFICATION"
    ORDER_FREEZE = "ORDER_FREEZE"
    OPENING_AUCTION = "OPENING_AUCTION"
    REGULAR_TRADING = "REGULAR_TRADING"
    CLOSING_AUCTION = "CLOSING_AUCTION"
    POST_MARKET = "POST_MARKET"
    SPECIAL_SESSION = "SPECIAL_SESSION"
    CLOSED = "CLOSED"


class ExceptionType(str, enum.Enum):
    EARLY_CLOSE = "EARLY_CLOSE"
    LATE_OPEN = "LATE_OPEN"
    FULL_DAY_CLOSURE = "FULL_DAY_CLOSURE"
    PARTIAL_DAY_CLOSURE = "PARTIAL_DAY_CLOSURE"
    SESSION_EXTENSION = "SESSION_EXTENSION"
    SESSION_REDUCTION = "SESSION_REDUCTION"
    SPECIAL_TRADING_SESSION = "SPECIAL_TRADING_SESSION"
    EMERGENCY_SCHEDULE_CHANGE = "EMERGENCY_SCHEDULE_CHANGE"


class ExceptionStatus(str, enum.Enum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    CANCELLED = "CANCELLED"
    SUPERSEDED = "SUPERSEDED"


class TradingDayClassification(str, enum.Enum):
    REGULAR_TRADING_DAY = "REGULAR_TRADING_DAY"
    SPECIAL_TRADING_DAY = "SPECIAL_TRADING_DAY"
    HOLIDAY = "HOLIDAY"
    NON_TRADING_DAY = "NON_TRADING_DAY"
    PARTIAL_TRADING_DAY = "PARTIAL_TRADING_DAY"
    EMERGENCY_CLOSURE = "EMERGENCY_CLOSURE"
    UNKNOWN = "UNKNOWN"


class ExchangeCalendar(Base):
    """
    Authoritative registry entity for exchange calendars.
    """
    __tablename__ = "exchange_calendars"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    calendar_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    exchange_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    exchange_name: Mapped[str] = mapped_column(String(128), nullable=False)
    market_country: Mapped[str] = mapped_column(String(3), nullable=False)  # ISO 3166-1 alpha-3: USA, IND
    timezone_name: Mapped[str] = mapped_column(String(64), nullable=False)  # IANA: Asia/Kolkata, America/New_York
    market_segment: Mapped[str] = mapped_column(String(64), default="EQUITY_CASH", nullable=False)
    calendar_status: Mapped[CalendarStatus] = mapped_column(
        SAEnum(CalendarStatus, native_enum=False), default=CalendarStatus.ACTIVE, nullable=False
    )
    current_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    sessions: Mapped[List["MarketSessionDefinition"]] = relationship(
        "MarketSessionDefinition", back_populates="calendar", cascade="all, delete-orphan"
    )
    holidays: Mapped[List["ExchangeHoliday"]] = relationship(
        "ExchangeHoliday", back_populates="calendar", cascade="all, delete-orphan"
    )
    exceptions: Mapped[List["CalendarException"]] = relationship(
        "CalendarException", back_populates="calendar", cascade="all, delete-orphan"
    )


class MarketSessionDefinition(Base):
    """
    Recurring regular session schedule templates in exchange-local time.
    """
    __tablename__ = "market_session_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    calendar_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("exchange_calendars.calendar_id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_code: Mapped[str] = mapped_column(String(32), nullable=False)
    session_name: Mapped[str] = mapped_column(String(64), nullable=False)
    session_type: Mapped[SessionType] = mapped_column(
        SAEnum(SessionType, native_enum=False), nullable=False
    )
    local_start_time: Mapped[time] = mapped_column(Time, nullable=False)
    local_end_time: Mapped[time] = mapped_column(Time, nullable=False)
    
    start_inclusive: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    end_inclusive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    session_sequence: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    
    order_entry_permitted: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    trade_matching_permitted: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    data_capture_expected: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    weekdays: Mapped[str] = mapped_column(String(32), default="0,1,2,3,4", nullable=False) # 0=Mon, 4=Fri
    active_status: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    calendar: Mapped["ExchangeCalendar"] = relationship("ExchangeCalendar", back_populates="sessions")


class ExchangeHoliday(Base):
    """
    Exchange holiday records with category and specific market impact.
    """
    __tablename__ = "exchange_holidays"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    holiday_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    calendar_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("exchange_calendars.calendar_id", ondelete="CASCADE"), nullable=False, index=True
    )
    holiday_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    holiday_name: Mapped[str] = mapped_column(String(128), nullable=False)
    holiday_category: Mapped[HolidayCategory] = mapped_column(
        SAEnum(HolidayCategory, native_enum=False), default=HolidayCategory.EXCHANGE_HOLIDAY, nullable=False
    )
    trading_impact: Mapped[TradingImpact] = mapped_column(
        SAEnum(TradingImpact, native_enum=False), default=TradingImpact.FULL_MARKET_CLOSURE, nullable=False
    )
    source_reference: Mapped[str] = mapped_column(String(128), default="OFFICIAL_CIRCULAR", nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    calendar: Mapped["ExchangeCalendar"] = relationship("ExchangeCalendar", back_populates="holidays")


class CalendarException(Base):
    """
    Schedule exceptions: early closes, late opens, emergency closures, and special sessions.
    """
    __tablename__ = "calendar_exceptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exception_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    calendar_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("exchange_calendars.calendar_id", ondelete="CASCADE"), nullable=False, index=True
    )
    exception_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    exception_type: Mapped[ExceptionType] = mapped_column(
        SAEnum(ExceptionType, native_enum=False), nullable=False
    )
    exception_status: Mapped[ExceptionStatus] = mapped_column(
        SAEnum(ExceptionStatus, native_enum=False), default=ExceptionStatus.APPROVED, nullable=False
    )
    affected_session_type: Mapped[Optional[SessionType]] = mapped_column(
        SAEnum(SessionType, native_enum=False), nullable=True
    )
    replacement_start_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    replacement_end_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    
    trading_impact: Mapped[TradingImpact] = mapped_column(
        SAEnum(TradingImpact, native_enum=False), default=TradingImpact.SESSION_MODIFICATION, nullable=False
    )
    reason: Mapped[str] = mapped_column(String(256), nullable=False)
    source_reference: Mapped[str] = mapped_column(String(128), default="OFFICIAL_CIRCULAR", nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    calendar: Mapped["ExchangeCalendar"] = relationship("ExchangeCalendar", back_populates="exceptions")
