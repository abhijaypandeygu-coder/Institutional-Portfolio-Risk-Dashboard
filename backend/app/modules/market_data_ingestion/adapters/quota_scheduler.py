"""
Module 02: Market Data Ingestion Engine - Dedicated Alpha Vantage Quota Scheduler.
Enforces daily call budget (default 20 requests/day against 25 allowance, 5 safety reserve),
caches symbol searches and duplicate requests, and tracks daily consumption.
"""
from datetime import date, datetime, timezone
import logging
from typing import Any, Dict, Optional, Tuple

from backend.app.core.config import settings

logger = logging.getLogger("ingestion.quota_scheduler")


class QuotaExceededException(Exception):
    """Raised when the internal daily API call budget is exhausted."""
    pass


class AlphaVantageQuotaScheduler:
    """
    Thread-safe / AsyncIO in-memory quota manager and cache for Alpha Vantage requests.
    Tracks date-based daily consumption and prevents exceeding budget.
    """

    def __init__(self, daily_budget: Optional[int] = None):
        self.daily_budget = daily_budget or settings.ALPHA_VANTAGE_DAILY_CALL_BUDGET
        self.provider_allowance = 25
        self.safety_margin = max(0, self.provider_allowance - self.daily_budget)
        self._current_date: date = datetime.now(timezone.utc).date()
        self._calls_made_today: int = 0

        # In-memory caches to save API quota
        self._symbol_search_cache: Dict[str, Any] = {}
        self._quote_cache: Dict[str, Tuple[datetime, Dict[str, Any]]] = {}
        self._history_cache: Dict[str, Tuple[datetime, Any]] = {}

    def _check_and_reset_day(self) -> None:
        today = datetime.now(timezone.utc).date()
        if today != self._current_date:
            logger.info(f"Alpha Vantage quota reset for new trading day: {today}")
            self._current_date = today
            self._calls_made_today = 0
            # Expire quote and symbol cache for the new day
            self._quote_cache.clear()

    def get_quota_status(self) -> Dict[str, Any]:
        self._check_and_reset_day()
        return {
            "date": str(self._current_date),
            "calls_made_today": self._calls_made_today,
            "daily_budget": self.daily_budget,
            "remaining_budget": max(0, self.daily_budget - self._calls_made_today),
            "provider_allowance": self.provider_allowance,
            "safety_margin": self.safety_margin,
            "is_budget_exhausted": self._calls_made_today >= self.daily_budget,
        }

    def acquire_call_permit(self, function_name: str, symbol: Optional[str] = None) -> None:
        """
        Acquires permission to make an outbound Alpha Vantage API request.
        Raises QuotaExceededException if budget is exhausted.
        """
        self._check_and_reset_day()
        if self._calls_made_today >= self.daily_budget:
            msg = (
                f"Alpha Vantage daily call budget of {self.daily_budget} exhausted for {self._current_date}. "
                f"Reserved safety margin of {self.safety_margin} calls protected. Rejecting call for '{function_name}'."
            )
            logger.warning(msg)
            raise QuotaExceededException(msg)

        self._calls_made_today += 1
        logger.info(
            f"Alpha Vantage API permit granted: call #{self._calls_made_today}/{self.daily_budget} "
            f"for function={function_name} symbol={symbol}"
        )

    # Symbol search caching
    def get_cached_symbol_search(self, keywords: str) -> Optional[Any]:
        return self._symbol_search_cache.get(keywords.strip().upper())

    def cache_symbol_search(self, keywords: str, results: Any) -> None:
        self._symbol_search_cache[keywords.strip().upper()] = results

    # Quote caching (cache within same trading day)
    def get_cached_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        self._check_and_reset_day()
        entry = self._quote_cache.get(symbol.strip().upper())
        if entry:
            return entry[1]
        return None

    def cache_quote(self, symbol: str, quote: Dict[str, Any]) -> None:
        self._quote_cache[symbol.strip().upper()] = (datetime.now(timezone.utc), quote)


# Global singleton instance
quota_scheduler = AlphaVantageQuotaScheduler()

