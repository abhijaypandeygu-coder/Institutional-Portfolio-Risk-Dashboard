from datetime import date, datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.instrument_reference_data.trading_calendar.schemas import (
    ExchangeCalendarCreate,
    ExchangeCalendarResponse,
    MarketSessionCreate,
    MarketSessionResponse,
    ExchangeHolidayCreate,
    ExchangeHolidayResponse,
    CalendarExceptionCreate,
    CalendarExceptionResponse,
    DayScheduleResponse,
    SessionResolutionResponse
)
from backend.app.modules.instrument_reference_data.trading_calendar.services.service import TradingCalendarService

router = APIRouter(prefix="/trading-calendars", tags=["Trading Calendars"])


@router.post("", response_model=ExchangeCalendarResponse, status_code=status.HTTP_201_CREATED)
async def create_calendar(payload: ExchangeCalendarCreate, db: AsyncSession = Depends(get_db)):
    service = TradingCalendarService(db)
    try:
        return await service.create_calendar(payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=List[ExchangeCalendarResponse])
async def list_calendars(db: AsyncSession = Depends(get_db)):
    service = TradingCalendarService(db)
    return await service.repo.list_calendars()


@router.get("/{calendar_id}", response_model=ExchangeCalendarResponse)
async def get_calendar(calendar_id: str, db: AsyncSession = Depends(get_db)):
    service = TradingCalendarService(db)
    cal = await service.repo.get_calendar_by_id(calendar_id)
    if not cal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Calendar '{calendar_id}' not found.")
    return cal


@router.post("/sessions", response_model=MarketSessionResponse, status_code=status.HTTP_201_CREATED)
async def add_session(payload: MarketSessionCreate, db: AsyncSession = Depends(get_db)):
    service = TradingCalendarService(db)
    try:
        return await service.add_session(payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/holidays", response_model=ExchangeHolidayResponse, status_code=status.HTTP_201_CREATED)
async def add_holiday(payload: ExchangeHolidayCreate, db: AsyncSession = Depends(get_db)):
    service = TradingCalendarService(db)
    try:
        return await service.add_holiday(payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/exceptions", response_model=CalendarExceptionResponse, status_code=status.HTTP_201_CREATED)
async def add_exception(payload: CalendarExceptionCreate, db: AsyncSession = Depends(get_db)):
    service = TradingCalendarService(db)
    try:
        return await service.add_exception(payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/lookup/day", response_model=DayScheduleResponse)
async def get_day_schedule(
    exchange_code: str = Query(..., description="Exchange code, e.g. NSE, BSE, NYSE, NASDAQ"),
    target_date: date = Query(..., description="Target date YYYY-MM-DD"),
    segment: str = Query(default="EQUITY_CASH"),
    db: AsyncSession = Depends(get_db)
):
    service = TradingCalendarService(db)
    try:
        return await service.get_day_schedule(exchange_code, target_date, segment)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/lookup/session", response_model=SessionResolutionResponse)
async def resolve_session(
    exchange_code: str = Query(..., description="Exchange code"),
    query_time: datetime = Query(..., description="Timestamp to resolve"),
    segment: str = Query(default="EQUITY_CASH"),
    db: AsyncSession = Depends(get_db)
):
    service = TradingCalendarService(db)
    try:
        return await service.resolve_session(exchange_code, query_time, segment)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/lookup/next-trading-day")
async def get_next_trading_day(
    exchange_code: str = Query(...),
    start_date: date = Query(...),
    segment: str = Query(default="EQUITY_CASH"),
    db: AsyncSession = Depends(get_db)
):
    service = TradingCalendarService(db)
    try:
        next_day = await service.get_next_trading_day(exchange_code, start_date, segment)
        return {"exchange_code": exchange_code, "start_date": start_date, "next_trading_day": next_day}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/lookup/previous-trading-day")
async def get_previous_trading_day(
    exchange_code: str = Query(...),
    start_date: date = Query(...),
    segment: str = Query(default="EQUITY_CASH"),
    db: AsyncSession = Depends(get_db)
):
    service = TradingCalendarService(db)
    try:
        prev_day = await service.get_previous_trading_day(exchange_code, start_date, segment)
        return {"exchange_code": exchange_code, "start_date": start_date, "previous_trading_day": prev_day}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
