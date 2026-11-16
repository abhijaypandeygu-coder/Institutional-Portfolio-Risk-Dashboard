"""
Mathematical formulations and portfolio simulation for M11.09 Pre-trade Risk Checks.

Formulations:
1. Signed Order Quantity:
   Delta_Q = +Q for BUY, -Q for SELL (where Q > 0)
2. Projected Position Quantity:
   Q_1 = Q_0 + Delta_Q
   Direction: FLAT if Q_1 == 0, LONG if Q_1 > 0, SHORT if Q_1 < 0.
   Transitions:
   - Long increased (Q_0 > 0, Delta_Q > 0)
   - Long reduced (Q_0 > 0, Delta_Q < 0, Q_1 > 0)
   - Long closed (Q_0 > 0, Q_1 == 0)
   - Long reversed to short (Q_0 > 0, Q_1 < 0)
   - Short increased (Q_0 < 0, Delta_Q < 0)
   - Short reduced (Q_0 < 0, Delta_Q > 0, Q_1 < 0)
   - Short closed (Q_0 < 0, Q_1 == 0)
   - Short reversed to long (Q_0 < 0, Q_1 > 0)
   - New long (Q_0 == 0, Delta_Q > 0)
   - New short (Q_0 == 0, Delta_Q < 0)
3. Projected Instrument Exposure:
   E_i,1 = Q_i,1 * P_i * FX_i
4. Projected Portfolio Gross & Net Exposure:
   G_1 = Sum_i |E_i,1|
   N_1 = Sum_i E_i,1
   Gross weight G_w = G_1 / NAV_1
   Net weight N_w = N_1 / NAV_1
5. Position Weight:
   W_i,1 = |E_i,1| / NAV_1
6. Sector Exposure:
   S_k,1 = Sum_{i in k} E_i,1
7. Parametric VaR incremental impact:
   sigma_p = sqrt(w^T Sigma w)
   VaR = NAV * z_alpha * sigma_p
   Delta_VaR = VaR_projected - VaR_current
8. Participation rate:
   ParticipationRate = OrderQuantity / ExpectedMarketVolume
"""

from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
import numpy as np


def to_decimal(val: Any) -> Decimal:
    if val is None:
        return Decimal("0.00")
    if isinstance(val, Decimal):
        return val
    return Decimal(str(val))


def calculate_projected_position(
    current_qty: Decimal,
    order_side: str,
    order_qty: Decimal,
) -> Tuple[Decimal, str, str]:
    """
    Simulates projected position and transition type.
    order_side: 'BUY' or 'SELL'.
    order_qty: positive Decimal.
    Returns: (projected_qty, direction, transition_type)
    """
    q0 = to_decimal(current_qty)
    q = to_decimal(order_qty)
    delta_q = q if order_side.upper() == "BUY" else -q
    q1 = q0 + delta_q

    # Direction
    if q1 == Decimal("0"):
        direction = "FLAT"
    elif q1 > Decimal("0"):
        direction = "LONG"
    else:
        direction = "SHORT"

    # Transition type
    if q0 == Decimal("0"):
        transition = "NEW_LONG" if delta_q > 0 else "NEW_SHORT"
    elif q0 > Decimal("0"):
        if delta_q > 0:
            transition = "LONG_INCREASED"
        elif q1 > 0:
            transition = "LONG_REDUCED"
        elif q1 == 0:
            transition = "LONG_CLOSED"
        else:
            transition = "LONG_REVERSED_TO_SHORT"
    else:  # q0 < 0
        if delta_q < 0:
            transition = "SHORT_INCREASED"
        elif q1 < 0:
            transition = "SHORT_REDUCED"
        elif q1 == 0:
            transition = "SHORT_CLOSED"
        else:
            transition = "SHORT_REVERSED_TO_LONG"

    return q1, direction, transition


def calculate_exposures(
    positions_signed_values: Dict[str, Decimal],
    portfolio_nav: Decimal,
) -> Dict[str, Decimal]:
    """
    Calculates gross, net, long, short exposures and weights.
    positions_signed_values: dict of symbol -> signed exposure notional (E_i).
    """
    nav = to_decimal(portfolio_nav)
    if nav <= Decimal("0"):
        nav = Decimal("1.00")  # Safeguard against division by zero

    gross = Decimal("0.00")
    net = Decimal("0.00")
    long_exp = Decimal("0.00")
    short_exp = Decimal("0.00")

    for sym, val in positions_signed_values.items():
        v = to_decimal(val)
        net += v
        gross += abs(v)
        if v > Decimal("0"):
            long_exp += v
        else:
            short_exp += abs(v)

    gross_weight = (gross / nav).quantize(Decimal("0.0001"))
    net_weight = (net / nav).quantize(Decimal("0.0001"))
    long_weight = (long_exp / nav).quantize(Decimal("0.0001"))
    short_weight = (short_exp / nav).quantize(Decimal("0.0001"))

    return {
        "gross_exposure": gross.quantize(Decimal("0.01")),
        "net_exposure": net.quantize(Decimal("0.01")),
        "long_exposure": long_exp.quantize(Decimal("0.01")),
        "short_exposure": short_exp.quantize(Decimal("0.01")),
        "gross_weight": gross_weight,
        "net_weight": net_weight,
        "long_weight": long_weight,
        "short_weight": short_weight,
    }


def calculate_sector_exposure(
    positions_signed_values: Dict[str, Decimal],
    instrument_sectors: Dict[str, str],
    portfolio_nav: Decimal,
) -> Dict[str, Dict[str, Decimal]]:
    """
    Aggregates exposure by sector and calculates sector weight.
    Returns: dict of sector -> {"exposure": Decimal, "weight": Decimal}
    """
    nav = to_decimal(portfolio_nav)
    if nav <= Decimal("0"):
        nav = Decimal("1.00")

    sector_exposures: Dict[str, Decimal] = {}
    for sym, val in positions_signed_values.items():
        sec = instrument_sectors.get(sym, "UNCLASSIFIED")
        v = to_decimal(val)
        sector_exposures[sec] = sector_exposures.get(sec, Decimal("0.00")) + v

    results = {}
    for sec, exp in sector_exposures.items():
        wt = (exp / nav).quantize(Decimal("0.0001"))
        results[sec] = {
            "exposure": exp.quantize(Decimal("0.01")),
            "weight": wt,
        }
    return results


def calculate_parametric_var(
    weights: List[float],
    cov_matrix: List[List[float]],
    portfolio_nav: float,
    z_alpha: float = 1.644853,  # 95% 1-tail normal quantile
) -> float:
    """
    Calculates portfolio volatility and parametric VaR.
    VaR = NAV * z_alpha * sqrt(w^T * Sigma * w).
    """
    w = np.array(weights, dtype=np.float64)
    sigma = np.array(cov_matrix, dtype=np.float64)
    port_var = float(np.dot(w.T, np.dot(sigma, w)))
    port_vol = np.sqrt(max(0.0, port_var))
    var = portfolio_nav * z_alpha * port_vol
    return max(0.0, float(var))


def calculate_participation_rate(order_qty: Decimal, expected_volume: Decimal) -> Decimal:
    """
    Participation Rate (%) = (order_qty / expected_volume) * 100.
    """
    vol = to_decimal(expected_volume)
    if vol <= Decimal("0"):
        return Decimal("100.00")
    rate = (to_decimal(order_qty) / vol) * Decimal("100.00")
    return rate.quantize(Decimal("0.01"))

