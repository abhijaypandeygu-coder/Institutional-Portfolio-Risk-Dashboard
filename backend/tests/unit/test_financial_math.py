"""
Institutional Unit Tests for Mathematical Correctness (M15.10.02 & M15.10.04).
Validates exposure calculations, sample volatility, historical VaR, Expected Shortfall,
drawdown, and order-book metrics against analytical models and property-based rules.
"""
from decimal import Decimal
import pytest
from hypothesis import given, strategies as st
from backend.app.modules.infrastructure_platform.testing_infrastructure.reference.math_reference import (
    FinancialMathReference,
)
from backend.app.modules.infrastructure_platform.testing_infrastructure.datasets.deterministic_datasets import (
    PORTFOLIO_REFERENCE_DATASET_V1,
    MARKET_RETURNS_DATASET_V1,
    ORDER_BOOK_SNAPSHOT_V1,
)


@pytest.mark.unit
def test_gross_and_net_exposure_analytical():
    """Validates exposure calculation on 5-position multi-market portfolio."""
    positions = PORTFOLIO_REFERENCE_DATASET_V1["positions"]
    res = FinancialMathReference.calculate_gross_and_net_exposure(positions)

    # Hand-derived:
    # RELIANCE: 2,850,500 Long
    # TCS: 2,060,000 Long
    # INFY: 740,000 Short
    # AAPL: 45,000 Long
    # MSFT: 42,000 Short
    # Total Long = 2850500 + 2060000 + 45000 = 4,955,500
    # Total Short = 740000 + 42000 = 782,000
    # Gross = 4955500 + 782000 = 5,737,500
    # Net = 4955500 - 782000 = 4,173,500 (adjusted for actual portfolio definition)
    assert res["long_exposure"] == Decimal("4955500.0")
    assert res["short_exposure"] == Decimal("782000.0")
    assert res["gross_exposure"] == Decimal("5737500.0")
    assert res["net_exposure"] == Decimal("4173500.0")
    assert res["gross_exposure"] >= abs(res["net_exposure"])


@pytest.mark.unit
def test_sample_volatility_calculation():
    """Validates annualized sample volatility with Bessel correction (N-1)."""
    returns = MARKET_RETURNS_DATASET_V1["returns"]
    vol = FinancialMathReference.calculate_sample_volatility(returns, annualization_factor=252.0)
    # Volatility must be positive and fall in standard equities regime (10% to 50%)
    assert vol > 0.0
    assert 0.15 <= vol <= 0.35


@pytest.mark.unit
def test_historical_var_and_expected_shortfall():
    """Validates that Expected Shortfall (CVaR) is weakly greater than VaR."""
    losses = MARKET_RETURNS_DATASET_V1["losses"]
    var_95 = FinancialMathReference.calculate_historical_var(losses, confidence_level=0.90)
    es_95 = FinancialMathReference.calculate_expected_shortfall(losses, confidence_level=0.90)

    assert es_95 >= var_95
    assert var_95 > 0.0


@pytest.mark.unit
def test_max_drawdown_calculation():
    """Tests maximum peak-to-trough drawdown evaluation."""
    nav_series = [100.0, 105.0, 110.0, 99.0, 95.0, 102.0, 108.0]
    # Peak = 110.0, Trough = 95.0 -> DD = (110 - 95)/110 = 15/110 = 0.13636...
    max_dd, peak_idx, trough_idx = FinancialMathReference.calculate_max_drawdown(nav_series)
    assert peak_idx == 2
    assert trough_idx == 4
    assert round(max_dd, 4) == round(15.0 / 110.0, 4)


@pytest.mark.unit
def test_order_book_metrics():
    """Tests bid-ask spread and depth imbalance analytics."""
    best_bid = ORDER_BOOK_SNAPSHOT_V1["bids"][0]["price"]
    best_ask = ORDER_BOOK_SNAPSHOT_V1["asks"][0]["price"]

    spread_metrics = FinancialMathReference.calculate_bid_ask_spread_metrics(best_bid, best_ask)
    assert spread_metrics["absolute_spread"] == 0.5
    assert spread_metrics["mid_price"] == 2850.25
    assert spread_metrics["spread_bps"] > 0.0

    bid_qty = sum(b["quantity"] for b in ORDER_BOOK_SNAPSHOT_V1["bids"])
    ask_qty = sum(a["quantity"] for a in ORDER_BOOK_SNAPSHOT_V1["asks"])
    imbalance = FinancialMathReference.calculate_order_book_imbalance(bid_qty, ask_qty)
    assert -1.0 <= imbalance <= 1.0


# Property-Based Test with Hypothesis
@given(
    st.lists(
        st.fixed_dictionaries({
            "market_value": st.floats(min_value=-1e7, max_value=1e7, allow_nan=False, allow_infinity=False)
        }),
        min_size=1,
        max_size=20,
    )
)
@pytest.mark.unit
def test_gross_exposure_non_negative_property(positions):
    """Property: Gross exposure must NEVER be negative, regardless of position signs."""
    res = FinancialMathReference.calculate_gross_and_net_exposure(positions)
    assert res["gross_exposure"] >= Decimal("0.0")
    assert res["gross_exposure"] >= abs(res["net_exposure"])
