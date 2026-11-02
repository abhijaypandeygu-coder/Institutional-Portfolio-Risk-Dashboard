"""
M08.01 Factor Definition Templates and Hash Utilities.
Defines canonical initial recipes for:
1. Market (MKT / MKT_RF): NIFTY 50 / S&P 500 total and excess return specifications
2. Size (SMB): Small minus Big market capitalization breakpoints and cap-weighting
3. Value (HML): High minus Low book-to-market with point-in-time publication lag
4. Momentum (MOM): 12-1 formation and skip period cumulative return ranking
5. Quality (QMJ): Profitability, financial safety, and earnings quality composite
Also generates deterministic SHA-256 cryptographic recipe hashes.
"""
import hashlib
import json
from decimal import Decimal
from typing import Dict, Any, List

from backend.app.modules.factor_risk.factor_definition.models import (
    FactorFamily,
    FactorType,
    ConstructionType,
    CharacteristicDirection,
    StandardizationMethod,
    WeightingMethodology,
    RebalancingFrequency,
    MarketScope,
)


def compute_deterministic_hash(data: Dict[str, Any]) -> str:
    """
    Produce a deterministic SHA-256 hash of a dictionary by sorting keys
    and normalizing numeric/string representations.
    """
    def _normalize(val: Any) -> Any:
        if isinstance(val, dict):
            return {k: _normalize(v) for k, v in sorted(val.items())}
        elif isinstance(val, list):
            return [_normalize(x) for x in val]
        elif isinstance(val, (Decimal, float)):
            return round(float(val), 8)
        return val

    normalized = _normalize(data)
    serialized = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


# ============================================================================
# CANONICAL FACTOR DEFINITION RECIPES
# ============================================================================

def get_canonical_market_recipe(
    market: MarketScope = MarketScope.INDIA,
    excess_return: bool = True,
) -> Dict[str, Any]:
    """
    Canonical Market Factor Specification:
    India: NIFTY 50 Total Return Index (or NIFTY 500) minus 91-Day T-Bill (M07.07).
    US: S&P 500 Total Return Index minus 4-Week US T-Bill.
    """
    benchmark_id = "IND_NIFTY_50_TRI" if market == MarketScope.INDIA else "US_SP500_TRI"
    currency = "INR" if market == MarketScope.INDIA else "USD"
    rf_code = "IN_91D_TBILL" if market == MarketScope.INDIA else "US_4W_TBILL"

    spec = {
        "benchmark_id": benchmark_id,
        "benchmark_name": "NIFTY 50 Total Return Index" if market == MarketScope.INDIA else "S&P 500 Total Return Index",
        "benchmark_provider": "NSE" if market == MarketScope.INDIA else "S&P_DOW_JONES",
        "return_basis": "EXCESS_RETURN" if excess_return else "TOTAL_RETURN",
        "price_basis": "OFFICIAL_CLOSE",
        "risk_free_rate_code": rf_code if excess_return else None,
        "market_scope": market.value,
        "currency": currency,
        "frequency": "DAILY",
        "return_type": "LOGARITHMIC",
        "calendar_id": "NSE_TRADING_CALENDAR" if market == MarketScope.INDIA else "NYSE_TRADING_CALENDAR",
    }
    return spec


def get_canonical_size_recipe(
    market: MarketScope = MarketScope.INDIA,
) -> Dict[str, Any]:
    """
    Canonical Size Factor (SMB) Specification:
    Small minus Big market capitalization ranking.
    Breakpoints: Top 30% (Big), Bottom 30% (Small), Middle 40% (Neutral).
    Weighting: Free-Float Market Cap Weighted.
    Rebalancing: Annual / Semi-Annual.
    """
    currency = "INR" if market == MarketScope.INDIA else "USD"
    return {
        "characteristic": "FREE_FLOAT_MARKET_CAP",
        "source_field": "m05_position_valuations.market_value_base",
        "universe_filter": "EXCLUDE_PENNY_AND_ILLIQUID",
        "breakpoint_type": "PERCENTILE",
        "small_breakpoint_upper_pct": 30.0,
        "big_breakpoint_lower_pct": 70.0,
        "long_leg": "SMALL_CAP",
        "short_leg": "BIG_CAP",
        "return_direction": "LONG_MINUS_SHORT",
        "weighting_methodology": WeightingMethodology.FREE_FLOAT_MARKET_CAP_WEIGHTED.value,
        "rebalancing_frequency": RebalancingFrequency.ANNUALLY.value,
        "market_scope": market.value,
        "currency": currency,
        "frequency": "DAILY",
        "return_type": "LOGARITHMIC",
    }


def get_canonical_value_recipe(
    market: MarketScope = MarketScope.INDIA,
) -> Dict[str, Any]:
    """
    Canonical Value Factor (HML) Specification:
    High minus Low Book-to-Market ratio.
    Breakpoints: Top 30% (High/Value), Bottom 30% (Low/Growth).
    Point-in-time publication lag: minimum 60 days after fiscal quarter end.
    Negative book equity policy: Exclude from universe.
    """
    currency = "INR" if market == MarketScope.INDIA else "USD"
    return {
        "characteristic": "BOOK_TO_MARKET",
        "book_equity_source": "m04_financial_statements.common_equity",
        "market_equity_source": "m05_position_valuations.market_value_base",
        "publication_lag_days": 60,
        "negative_equity_policy": "EXCLUDE_FROM_PORTFOLIO",
        "breakpoint_type": "PERCENTILE",
        "high_value_breakpoint_lower_pct": 70.0,
        "low_value_breakpoint_upper_pct": 30.0,
        "long_leg": "HIGH_BOOK_TO_MARKET",
        "short_leg": "LOW_BOOK_TO_MARKET",
        "return_direction": "LONG_MINUS_SHORT",
        "weighting_methodology": WeightingMethodology.FREE_FLOAT_MARKET_CAP_WEIGHTED.value,
        "rebalancing_frequency": RebalancingFrequency.ANNUALLY.value,
        "neutralization": "SECTOR_NEUTRAL",
        "market_scope": market.value,
        "currency": currency,
        "frequency": "DAILY",
        "return_type": "LOGARITHMIC",
    }


def get_canonical_momentum_recipe(
    market: MarketScope = MarketScope.INDIA,
) -> Dict[str, Any]:
    """
    Canonical Momentum Factor (MOM / WML) Specification:
    Winners minus Losers: 12-1 Momentum (12 month formation window, skip latest 1 month).
    Formula: Cumulative return over months [t-12, t-2].
    Breakpoints: Top 30% (Winners), Bottom 30% (Losers).
    Rebalancing: Monthly.
    """
    currency = "INR" if market == MarketScope.INDIA else "USD"
    return {
        "formation_window_days": 252,
        "skip_window_days": 21,
        "formation_score": "12_1_CUMULATIVE_RETURN",
        "ranking_method": "CROSS_SECTIONAL_PERCENTILE",
        "winner_breakpoint_lower_pct": 70.0,
        "loser_breakpoint_upper_pct": 30.0,
        "long_leg": "WINNERS",
        "short_leg": "LOSERS",
        "return_direction": "LONG_MINUS_SHORT",
        "weighting_methodology": WeightingMethodology.EQUAL_WEIGHTED.value,
        "rebalancing_frequency": RebalancingFrequency.MONTHLY.value,
        "market_scope": market.value,
        "currency": currency,
        "frequency": "DAILY",
        "return_type": "LOGARITHMIC",
    }


def get_canonical_quality_recipe(
    market: MarketScope = MarketScope.INDIA,
) -> Dict[str, Any]:
    """
    Canonical Quality Factor (QMJ) Specification:
    Composite Score = 0.40 * Profitability (ROE) + 0.30 * Safety (Inverse Leverage) + 0.30 * Earnings Quality (Accruals).
    Standardization: Cross-sectional Winsorized (1%) Z-score.
    Breakpoints: Top 30% (High Quality), Bottom 30% (Low Quality).
    Rebalancing: Semi-Annually.
    """
    currency = "INR" if market == MarketScope.INDIA else "USD"
    characteristics: List[Dict[str, Any]] = [
        {
            "characteristic_code": "PROFITABILITY_ROE",
            "characteristic_name": "Return on Equity (ROE)",
            "source_field_reference": "m04_financial_statements.net_income / common_equity",
            "formula_specification": "NET_INCOME / BOOK_EQUITY",
            "characteristic_direction": CharacteristicDirection.HIGHER_IS_BETTER.value,
            "standardization_method": StandardizationMethod.CROSS_SECTIONAL_Z_SCORE.value,
            "winsorization_pct": 0.01,
            "component_weight": 0.40,
        },
        {
            "characteristic_code": "FINANCIAL_SAFETY_LEVERAGE",
            "characteristic_name": "Financial Leverage (Debt-to-Equity)",
            "source_field_reference": "m04_financial_statements.total_debt / common_equity",
            "formula_specification": "TOTAL_DEBT / BOOK_EQUITY",
            "characteristic_direction": CharacteristicDirection.LOWER_IS_BETTER.value,  # Lower debt is safer!
            "standardization_method": StandardizationMethod.CROSS_SECTIONAL_Z_SCORE.value,
            "winsorization_pct": 0.01,
            "component_weight": 0.30,
        },
        {
            "characteristic_code": "EARNINGS_QUALITY_ACCRUALS",
            "characteristic_name": "Accounting Accruals Ratio",
            "source_field_reference": "m04_financial_statements.operating_cash_flow / net_income",
            "formula_specification": "(NET_INCOME - OPERATING_CASH_FLOW) / TOTAL_ASSETS",
            "characteristic_direction": CharacteristicDirection.LOWER_IS_BETTER.value,  # Lower accruals is higher quality!
            "standardization_method": StandardizationMethod.CROSS_SECTIONAL_Z_SCORE.value,
            "winsorization_pct": 0.01,
            "component_weight": 0.30,
        },
    ]

    return {
        "composite_method": "WEIGHTED_Z_SCORE_SUM",
        "characteristics": characteristics,
        "breakpoint_type": "PERCENTILE",
        "high_quality_breakpoint_lower_pct": 70.0,
        "low_quality_breakpoint_upper_pct": 30.0,
        "long_leg": "HIGH_QUALITY",
        "short_leg": "LOW_QUALITY",
        "return_direction": "LONG_MINUS_SHORT",
        "weighting_methodology": WeightingMethodology.FREE_FLOAT_MARKET_CAP_WEIGHTED.value,
        "rebalancing_frequency": RebalancingFrequency.QUARTERLY.value,
        "market_scope": market.value,
        "currency": currency,
        "frequency": "DAILY",
        "return_type": "LOGARITHMIC",
    }

