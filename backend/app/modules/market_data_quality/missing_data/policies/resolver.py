"""
Module 03.01: Missing Data Detection - Expected Observation Policy Engine.
Determines whether an observation is expected based on provider capability,
market sessions, and hierarchical precedence (Instrument > Feed > Provider > Exchange > Default).
"""
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from backend.app.modules.market_data_quality.missing_data.integrations.calendar_interface import ExchangeSessionResolver
from backend.app.modules.market_data_quality.missing_data.models import (
    ExpectedObservationPolicy,
    ExpectationStatus,
)


class ExpectationPolicyResolver:
    """
    Evaluates observation expectations:
    - Protects against expecting unsupported data (e.g. intraday ticks on Alpha Vantage Free).
    - Checks calendar trading sessions and holidays.
    """

    def __init__(self, policies: Optional[List[ExpectedObservationPolicy]] = None):
        self.policies = policies or []

    def evaluate_expectation(
        self,
        provider_id: str,
        exchange: str,
        channel: str,
        frequency: str,
        event_time_utc: datetime,
        instrument_id: Optional[str] = None,
        feed_id: Optional[str] = None,
    ) -> Tuple[ExpectationStatus, str]:
        """
        Returns (ExpectationStatus, reason).
        Strictly enforces:
        1. Alpha Vantage Free: only DAILY, WEEKLY, MONTHLY, and GLOBAL_QUOTE are supported.
        2. Intraday streaming only expected when exchange is actively open.
        """
        # 1. Provider capability verification
        if provider_id.upper() in ("ALPHA_VANTAGE", "ALPHA_VANTAGE_FREE"):
            if channel in ("TICK", "ORDER_BOOK_L1", "ORDER_BOOK_L2", "TRADE"):
                return ExpectationStatus.NOT_SUPPORTED, "Alpha Vantage Free plan does not support streaming tick/order-book data."
            if frequency not in ("1d", "1w", "1M", "DAILY", "WEEKLY", "MONTHLY"):
                return ExpectationStatus.NOT_SUPPORTED, f"Alpha Vantage Free plan does not support intraday '{frequency}' candles."

        # 2. Market calendar verification
        if frequency in ("REALTIME", "1m", "5m", "15m", "30m", "60m"):
            is_open = ExchangeSessionResolver.is_market_open_at(exchange, event_time_utc)
            if not is_open:
                return ExpectationStatus.MARKET_CLOSED, f"Market for exchange '{exchange}' is closed at {event_time_utc.isoformat()}."

        # 3. Daily bar calendar check
        if frequency in ("1d", "DAILY"):
            tz = ExchangeSessionResolver.get_timezone(exchange)
            local_date = event_time_utc.astimezone(tz).date()
            if not ExchangeSessionResolver.is_trading_day(exchange, local_date):
                return ExpectationStatus.MARKET_CLOSED, f"{local_date} is a holiday or weekend for exchange '{exchange}'."

        return ExpectationStatus.EXPECTED, "Observation is expected according to exchange calendar and provider capability."
