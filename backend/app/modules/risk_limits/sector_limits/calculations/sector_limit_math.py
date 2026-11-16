"""
Financial calculations and mathematical specifications for M11.03 — Sector Limits.

Implements:
1. Sector & Industry exposure aggregation:
   - Gross Exposure: GrossMV_s = sum_{i in s} |MV_i|
   - Net Exposure: NetMV_s = sum_{i in s} MV_i
   - Long Exposure: LongMV_s = sum_{i in s} max(MV_i, 0)
   - Short Exposure: ShortMV_s = sum_{i in s} max(-MV_i, 0)
   - Sector Weight: SectorWeight_s = (GrossMV_s / NAV_p) * 100
   - Industry Weight: IndustryWeight_g = (GrossMV_g / NAV_p) * 100
2. Benchmark-Relative Active Weight calculations:
   - Benchmark Sector Weight: BW_s = sum_{j in s} b_j
   - Active Sector Weight: ActiveWeight_s = PW_s - BW_s
   - Overweight Breach: max(0, ActiveWeight_s - UpperLimit_s)
   - Underweight Breach: max(0, LowerLimit_s - ActiveWeight_s)
   - Symmetric Band Breach: max(0, |ActiveWeight_s| - BandLimit_s)
3. Classification Coverage:
   - Coverage % = (ClassifiedExposure / TotalEligibleExposure) * 100
   - Unclassified Exposure = sum_{i not in classified} |MV_i|
   - Unclassified Weight % = (UnclassifiedExposure / NAV_p) * 100
4. Limit Utilization & Headroom:
   - Utilization = (ActualExposure / Limit) * 100
   - Remaining Capacity = Limit - ActualExposure
   - Breach Amount = max(0, ActualExposure - Limit)
5. Proposed-order simulation for affected sector/industry.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, List, Optional, Tuple


def calculate_sector_utilization(
    actual_exposure: Decimal,
    warning_threshold: Decimal,
    hard_threshold: Decimal,
    comparison_operator: str = "GREATER_THAN_OR_EQUAL"
) -> Dict[str, Any]:
    """
    Evaluates observed sector or industry exposure against warning and hard limits.
    """
    if hard_threshold <= Decimal("0") or warning_threshold <= Decimal("0"):
        raise ValueError("Warning and hard thresholds must be strictly positive.")

    if hard_threshold < warning_threshold:
        raise ValueError("Hard threshold cannot be less restrictive than warning threshold.")

    u_hard = (actual_exposure / hard_threshold * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    u_warn = (actual_exposure / warning_threshold * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    capacity = (hard_threshold - actual_exposure).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    breach = max(Decimal("0.0000"), actual_exposure - hard_threshold).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    if comparison_operator in ("GREATER_THAN_OR_EQUAL", "GREATER_THAN"):
        if actual_exposure >= hard_threshold:
            status = "HARD_LIMIT_EXCEEDED"
        elif actual_exposure >= warning_threshold:
            status = "WARNING"
        else:
            status = "WITHIN_LIMIT"
    else:
        if actual_exposure <= hard_threshold:
            status = "HARD_LIMIT_EXCEEDED"
        elif actual_exposure <= warning_threshold:
            status = "WARNING"
        else:
            status = "WITHIN_LIMIT"

    return {
        "actual_exposure": actual_exposure,
        "warning_threshold": warning_threshold,
        "hard_threshold": hard_threshold,
        "warning_utilization_pct": u_warn,
        "hard_utilization_pct": u_hard,
        "remaining_capacity": capacity,
        "breach_amount": breach,
        "evaluation_status": status,
    }


def evaluate_active_weight_limit(
    portfolio_weight_pct: Decimal,
    benchmark_weight_pct: Decimal,
    upper_overweight_limit_pct: Optional[Decimal] = None,
    lower_underweight_limit_pct: Optional[Decimal] = None, # e.g. -5.0%
    warning_buffer_pct: Decimal = Decimal("1.0")
) -> Dict[str, Any]:
    """
    Evaluates benchmark-relative active weight:
    ActiveWeight = PortfolioWeight - BenchmarkWeight
    If ActiveWeight > upper_overweight_limit: Overweight breach!
    If ActiveWeight < lower_underweight_limit: Underweight breach!
    """
    active_weight = (portfolio_weight_pct - benchmark_weight_pct).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    status = "WITHIN_LIMIT"
    breach_amount = Decimal("0.0000")
    limit_breached = None

    if upper_overweight_limit_pct is not None:
        if active_weight > upper_overweight_limit_pct:
            status = "HARD_LIMIT_EXCEEDED"
            breach_amount = (active_weight - upper_overweight_limit_pct).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
            limit_breached = "OVERWEIGHT"
        elif active_weight >= (upper_overweight_limit_pct - warning_buffer_pct):
            status = "WARNING"

    if lower_underweight_limit_pct is not None and status != "HARD_LIMIT_EXCEEDED":
        if active_weight < lower_underweight_limit_pct:
            status = "HARD_LIMIT_EXCEEDED"
            breach_amount = (lower_underweight_limit_pct - active_weight).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
            limit_breached = "UNDERWEIGHT"
        elif active_weight <= (lower_underweight_limit_pct + warning_buffer_pct):
            status = "WARNING"

    return {
        "portfolio_weight_pct": portfolio_weight_pct,
        "benchmark_weight_pct": benchmark_weight_pct,
        "active_weight_pct": active_weight,
        "upper_limit_pct": upper_overweight_limit_pct,
        "lower_limit_pct": lower_underweight_limit_pct,
        "breach_amount": breach_amount,
        "breach_type": limit_breached,
        "evaluation_status": status,
    }


def aggregate_sector_and_industry_exposures(
    positions: List[Dict[str, Any]],
    portfolio_nav: Decimal
) -> Dict[str, Any]:
    """
    Aggregates positions across sectors and industries:
    Tracks Gross, Net, Long, and Short exposures.
    Tracks Classified vs Unclassified exposure and coverage %.
    """
    if portfolio_nav is None or portfolio_nav <= Decimal("0"):
        raise ValueError("Portfolio NAV must be strictly positive.")

    total_gross = Decimal("0.0000")
    classified_gross = Decimal("0.0000")
    unclassified_gross = Decimal("0.0000")

    sectors: Dict[str, Dict[str, Any]] = {}
    industries: Dict[str, Dict[str, Any]] = {}
    unmapped_positions: List[Dict[str, Any]] = []

    for pos in positions:
        mv = Decimal(str(pos.get("market_value", 0)))
        abs_mv = abs(mv)
        total_gross += abs_mv

        sec_id = pos.get("sector_id")
        ind_id = pos.get("industry_id")

        if not sec_id or sec_id.upper() in ("UNMAPPED", "UNCLASSIFIED", "NONE"):
            unclassified_gross += abs_mv
            unmapped_positions.append(pos)
            continue

        classified_gross += abs_mv

        # Aggregate Sector
        if sec_id not in sectors:
            sectors[sec_id] = {
                "sector_id": sec_id,
                "sector_name": pos.get("sector_name", sec_id),
                "gross_exposure": Decimal("0.0000"),
                "net_exposure": Decimal("0.0000"),
                "long_exposure": Decimal("0.0000"),
                "short_exposure": Decimal("0.0000"),
                "constituent_count": 0,
            }
        sectors[sec_id]["gross_exposure"] += abs_mv
        sectors[sec_id]["net_exposure"] += mv
        sectors[sec_id]["long_exposure"] += max(mv, Decimal("0.0000"))
        sectors[sec_id]["short_exposure"] += max(-mv, Decimal("0.0000"))
        sectors[sec_id]["constituent_count"] += 1

        # Aggregate Industry
        if ind_id and ind_id.upper() not in ("UNMAPPED", "NONE"):
            if ind_id not in industries:
                industries[ind_id] = {
                    "industry_id": ind_id,
                    "industry_name": pos.get("industry_name", ind_id),
                    "sector_id": sec_id,
                    "gross_exposure": Decimal("0.0000"),
                    "net_exposure": Decimal("0.0000"),
                    "long_exposure": Decimal("0.0000"),
                    "short_exposure": Decimal("0.0000"),
                    "constituent_count": 0,
                }
            industries[ind_id]["gross_exposure"] += abs_mv
            industries[ind_id]["net_exposure"] += mv
            industries[ind_id]["long_exposure"] += max(mv, Decimal("0.0000"))
            industries[ind_id]["short_exposure"] += max(-mv, Decimal("0.0000"))
            industries[ind_id]["constituent_count"] += 1

    # Compute weights
    for s in sectors.values():
        s["gross_weight_pct"] = (s["gross_exposure"] / portfolio_nav * Decimal("100")).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        s["net_weight_pct"] = (s["net_exposure"] / portfolio_nav * Decimal("100")).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    for ind in industries.values():
        ind["gross_weight_pct"] = (ind["gross_exposure"] / portfolio_nav * Decimal("100")).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        ind["net_weight_pct"] = (ind["net_exposure"] / portfolio_nav * Decimal("100")).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    coverage_pct = Decimal("100.0000")
    if total_gross > Decimal("0"):
        coverage_pct = (classified_gross / total_gross * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    unclassified_weight_pct = Decimal("0.0000")
    if portfolio_nav > Decimal("0"):
        unclassified_weight_pct = (unclassified_gross / portfolio_nav * Decimal("100")).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    return {
        "total_gross_exposure": total_gross,
        "classified_gross_exposure": classified_gross,
        "unclassified_gross_exposure": unclassified_gross,
        "classification_coverage_pct": coverage_pct,
        "unclassified_weight_pct": unclassified_weight_pct,
        "sectors": list(sectors.values()),
        "industries": list(industries.values()),
        "unmapped_positions": unmapped_positions,
    }

