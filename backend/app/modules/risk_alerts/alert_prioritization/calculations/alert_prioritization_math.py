"""
Mathematical, statistical, and canonical logic functions for M12.05 — Alert Prioritization.

Functions:
1. `normalize_score(value, min_val, max_val)`: Constrains value to [0.0, 100.0].
2. `calculate_deterioration_velocity(x_t, x_prev, dt_seconds)`: Calculates rate of change per minute/hour.
3. `calculate_time_to_action(urgency, severity, velocity, deadline_remaining_seconds)`: Heuristic recommendation window.
4. `calculate_financial_impact_score(affected_value, nav, base_currency)`: Computes percentage of NAV and maps to 0-100 score.
5. `calculate_risk_impact_score(limit_utilization_pct, var_increase_pct, es_increase_pct, stress_loss_pct_nav)`: Aggregates risk dimensions.
6. `calculate_breadth_impact_score(affected_instruments, total_instruments, affected_portfolios, affected_sectors)`: Multi-entity breadth score.
7. `calculate_composite_impact(financial_score, risk_score, breadth_score, weights)`: Combines F, R, B dimensions.
8. `calculate_persistence_score(occurrences_count, first_seen_at, last_seen_at, now)`: Computes repeat/duration score.
9. `calculate_priority_score(severity_score, urgency_score, impact_score, persistence_score, weights, priority_floor)`: Computes composite 0-100 score and applies floors.
10. `assign_priority_band(priority_score, emergency_floor_active)`: Maps score to P1..P5.
11. `build_canonical_dedupe_key(source_module, category, event_type, portfolio_scope, entity_scope, condition_id)`: Deterministic SHA256 key.
"""

from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from typing import Optional, Dict, Any, Tuple


def to_decimal(val: Any) -> Optional[Decimal]:
    if val is None:
        return None
    if isinstance(val, Decimal):
        return val
    try:
        return Decimal(str(val))
    except Exception:
        return None


def normalize_score(val: float, min_val: float = 0.0, max_val: float = 100.0) -> float:
    if val is None or min_val >= max_val:
        return 0.0
    scaled = (float(val) - min_val) / (max_val - min_val) * 100.0
    return max(0.0, min(100.0, round(scaled, 2)))


def calculate_deterioration_velocity(
    x_t: Decimal,
    x_prev: Decimal,
    dt_seconds: float,
    adverse_direction: str = "INCREASING",  # INCREASING or DECREASING
) -> float:
    """
    Computes Velocity = (x_t - x_prev) / dt.
    Normalized to units per minute (dt_seconds / 60.0).
    Positive velocity denotes worsening/adverse deterioration.
    """
    if dt_seconds <= 0:
        return 0.0
    
    delta = float(x_t - x_prev)
    if adverse_direction == "DECREASING":
        delta = -delta  # If decreasing is adverse (e.g., liquidity or NAV drop), negate so delta > 0 is adverse
    
    per_minute = delta / (dt_seconds / 60.0)
    return round(per_minute, 4)


def calculate_time_to_action(
    urgency_level: str,  # U1_IMMEDIATE, U2_HIGH, U3_NORMAL, U4_LOW
    severity_level: str,  # WARNING, CRITICAL, EMERGENCY
    velocity: float = 0.0,
    deadline_remaining_seconds: Optional[float] = None,
) -> Tuple[str, Optional[int]]:
    """
    Returns (action_window_label, recommended_minutes).
    Labels:
    - IMMEDIATE_REVIEW (< 5 mins)
    - WITHIN_5_MINUTES (5 mins)
    - WITHIN_15_MINUTES (15 mins)
    - WITHIN_1_HOUR (60 mins)
    - WITHIN_CURRENT_SESSION (240 mins)
    - WITHIN_CURRENT_DAY (480 mins)
    - NEXT_BUSINESS_DAY (1440 mins)
    - ROUTINE_REVIEW (2880 mins)
    """
    if deadline_remaining_seconds is not None:
        mins = int(deadline_remaining_seconds // 60)
        if mins <= 5:
            return ("IMMEDIATE_REVIEW", 5)
        elif mins <= 15:
            return ("WITHIN_15_MINUTES", 15)
        elif mins <= 60:
            return ("WITHIN_1_HOUR", 60)
        elif mins <= 240:
            return ("WITHIN_CURRENT_SESSION", 240)
        elif mins <= 480:
            return ("WITHIN_CURRENT_DAY", 480)
        else:
            return ("NEXT_BUSINESS_DAY", mins)

    if severity_level == "EMERGENCY" or urgency_level == "U1_IMMEDIATE" or velocity > 5.0:
        return ("IMMEDIATE_REVIEW", 5)
    elif urgency_level == "U2_HIGH" or severity_level == "CRITICAL" or velocity > 1.0:
        return ("WITHIN_15_MINUTES", 15)
    elif urgency_level == "U3_NORMAL":
        return ("WITHIN_CURRENT_SESSION", 240)
    else:
        return ("ROUTINE_REVIEW", 1440)


def calculate_financial_impact_score(
    affected_value: Optional[Decimal],
    nav: Optional[Decimal],
) -> Tuple[float, Optional[Decimal], str]:
    """
    Computes affected value as % of NAV and maps to 0-100 score.
    Returns (score, pct_nav, confidence).
    """
    if affected_value is None or nav is None or nav <= Decimal("0"):
        return (0.0, None, "UNKNOWN")
    
    pct_nav = (abs(affected_value) / nav) * Decimal("100.0")
    pct_float = float(pct_nav)
    
    # Nonlinear scaling: 0% -> 0, 1% -> 25, 5% -> 60, 10% -> 80, 20%+ -> 100
    if pct_float <= 0.0:
        score = 0.0
    elif pct_float <= 1.0:
        score = pct_float * 25.0
    elif pct_float <= 5.0:
        score = 25.0 + (pct_float - 1.0) / 4.0 * 35.0  # 25 to 60
    elif pct_float <= 10.0:
        score = 60.0 + (pct_float - 5.0) / 5.0 * 20.0  # 60 to 80
    elif pct_float <= 20.0:
        score = 80.0 + (pct_float - 10.0) / 10.0 * 20.0  # 80 to 100
    else:
        score = 100.0
        
    return (round(score, 2), pct_nav.quantize(Decimal("0.0001")), "HIGH")


def calculate_risk_impact_score(
    limit_utilization_pct: Optional[Decimal] = None,
    var_increase_pct: Optional[Decimal] = None,
    stress_loss_pct_nav: Optional[Decimal] = None,
) -> Tuple[float, str]:
    """
    Calculates 0-100 risk impact score based on available risk metrics.
    Returns (score, confidence).
    """
    scores = []
    
    if limit_utilization_pct is not None:
        util = float(limit_utilization_pct)
        # 80% utilization -> 30, 100% -> 70, 120%+ -> 100
        if util < 80.0:
            s_util = max(0.0, util * 0.375)
        elif util <= 100.0:
            s_util = 30.0 + (util - 80.0) * 2.0  # 30 to 70
        else:
            s_util = min(100.0, 70.0 + (util - 100.0) * 1.5)
        scores.append(s_util)
        
    if var_increase_pct is not None:
        var_inc = float(var_increase_pct)
        # 10% VaR increase -> 30, 25% -> 60, 50%+ -> 100
        s_var = min(100.0, max(0.0, var_inc * 2.0))
        scores.append(s_var)
        
    if stress_loss_pct_nav is not None:
        stress = float(stress_loss_pct_nav)
        # 2% stress loss -> 30, 5% -> 60, 10%+ -> 100
        s_stress = min(100.0, max(0.0, stress * 10.0))
        scores.append(s_stress)
        
    if not scores:
        return (0.0, "UNKNOWN")
    
    avg_score = max(scores) * 0.7 + (sum(scores) / len(scores)) * 0.3
    confidence = "HIGH" if len(scores) >= 2 else "MEDIUM"
    return (round(min(100.0, avg_score), 2), confidence)


def calculate_breadth_impact_score(
    affected_instruments: int = 1,
    total_instruments: int = 10,
    affected_portfolios: int = 1,
    affected_sectors: int = 1,
) -> float:
    """
    Computes 0-100 breadth score from instrument, portfolio, and sector counts.
    """
    inst_ratio = min(1.0, max(0.0, affected_instruments / max(1, total_instruments)))
    port_score = min(100.0, (affected_portfolios - 1) * 25.0)  # 1 port -> 0, 2 -> 25, 5+ -> 100
    sec_score = min(100.0, (affected_sectors - 1) * 20.0)     # 1 sec -> 0, 2 -> 20, 6+ -> 100
    
    inst_score = inst_ratio * 100.0
    breadth = inst_score * 0.5 + port_score * 0.3 + sec_score * 0.2
    return round(min(100.0, breadth), 2)


def calculate_composite_impact(
    financial_score: float,
    risk_score: float,
    breadth_score: float,
    weights: Optional[Dict[str, float]] = None,
) -> float:
    """
    I = w_F * F + w_R * R + w_B * B. Default weights: 0.45, 0.40, 0.15.
    """
    if weights is None:
        weights = {"F": 0.45, "R": 0.40, "B": 0.15}
    
    w_f = weights.get("F", 0.45)
    w_r = weights.get("R", 0.40)
    w_b = weights.get("B", 0.15)
    
    tot_w = w_f + w_r + w_b
    if tot_w <= 0:
        return 0.0
    
    score = (financial_score * w_f + risk_score * w_r + breadth_score * w_b) / tot_w
    return round(min(100.0, max(0.0, score)), 2)


def calculate_persistence_score(
    occurrences_count: int,
    first_seen_at: datetime,
    last_seen_at: datetime,
) -> float:
    """
    Calculates persistence score based on occurrence counts and condition duration.
    """
    if occurrences_count <= 1:
        return 10.0
    
    # Count component: 2 -> 20, 5 -> 50, 10+ -> 80
    cnt_score = min(80.0, 10.0 + (occurrences_count - 1) * 10.0)
    
    # Duration component in minutes
    duration_mins = max(0.0, (last_seen_at - first_seen_at).total_seconds() / 60.0)
    # 0 mins -> 0, 60 mins -> 10, 240 mins -> 20
    dur_score = min(20.0, duration_mins / 12.0)
    
    return round(min(100.0, cnt_score + dur_score), 2)


def calculate_priority_score(
    severity_score: float,
    urgency_score: float,
    impact_score: float,
    persistence_score: float,
    weights: Optional[Dict[str, float]] = None,
    priority_floor: float = 0.0,
) -> float:
    """
    PriorityScore = w_S * S + w_U * U + w_I * I + w_P * P.
    Default weights: 0.35, 0.30, 0.25, 0.10.
    Applies priority floor (e.g. for EMERGENCY or CRITICAL).
    """
    if weights is None:
        weights = {"S": 0.35, "U": 0.30, "I": 0.25, "P": 0.10}
        
    w_s = weights.get("S", 0.35)
    w_u = weights.get("U", 0.30)
    w_i = weights.get("I", 0.25)
    w_p = weights.get("P", 0.10)
    
    tot_w = w_s + w_u + w_i + w_p
    if tot_w <= 0:
        return priority_floor
        
    raw_score = (
        severity_score * w_s +
        urgency_score * w_u +
        impact_score * w_i +
        persistence_score * w_p
    ) / tot_w
    
    effective_score = max(raw_score, priority_floor)
    return round(min(100.0, max(0.0, effective_score)), 2)


def assign_priority_band(priority_score: float, is_emergency: bool = False) -> str:
    """
    Maps 0-100 score to P1..P5.
    90-100: P1_IMMEDIATE
    75-89.99: P2_VERY_HIGH
    50-74.99: P3_HIGH
    25-49.99: P4_NORMAL
    0-24.99: P5_LOW
    Emergency override safeguard: Never below P1_IMMEDIATE if is_emergency is True.
    """
    if is_emergency or priority_score >= 90.0:
        return "P1_IMMEDIATE"
    elif priority_score >= 75.0:
        return "P2_VERY_HIGH"
    elif priority_score >= 50.0:
        return "P3_HIGH"
    elif priority_score >= 25.0:
        return "P4_NORMAL"
    else:
        return "P5_LOW"


def build_canonical_dedupe_key(
    source_module: str,
    category: str,
    event_type: str,
    portfolio_scope: str,
    entity_scope: str,
    condition_id: str,
) -> str:
    """
    Generates a canonical SHA256 deduplication key.
    DedupeKey = Hash(SourceModule, Category, EventType, PortfolioScope, EntityScope, ConditionIdentity)
    """
    canonical_dict = {
        "source_module": str(source_module or "").strip().upper(),
        "category": str(category or "").strip().upper(),
        "event_type": str(event_type or "").strip().upper(),
        "portfolio_scope": str(portfolio_scope or "").strip().upper(),
        "entity_scope": str(entity_scope or "").strip().upper(),
        "condition_id": str(condition_id or "").strip().upper(),
    }
    serialized = json.dumps(canonical_dict, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

