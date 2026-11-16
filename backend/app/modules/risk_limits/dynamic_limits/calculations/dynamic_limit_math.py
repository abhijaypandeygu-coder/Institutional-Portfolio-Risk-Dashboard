"""
Mathematical specifications and calculation engine for M11.05 — Dynamic Limits.

Implements institutional dynamic risk boundary adjustments:
1. Dynamic Limit Policy & Versioning.
2. Condition-Based Adjustment Rules:
   - Metric comparison operators (GREATER_THAN, GREATER_EQUAL, LESS_THAN, LESS_EQUAL, EQUAL, BETWEEN).
   - Hysteresis band evaluation (entry threshold vs exit threshold) to prevent boundary thrashing.
   - Persistence duration checks (condition must remain met for minimum duration).
   - Composite rules (AND / OR logic across multiple metrics: Volatility M07, Liquidity M09, Market Regime, Drawdown).
3. Adjustment Transformations:
   - Multiplicative scaling: L_adj = L_base * multiplier
   - Additive adjustment: L_adj = L_base + delta
   - Absolute replacement: L_adj = absolute_value
   - Restrictive-Only convention:
     * For Caps (max position weight, max VaR, max drawdown, max liquidation cost/days):
       L_eff = min(L_base, L_adj)
     * For Floors (min liquidity score, min ADV, min depth):
       L_eff = max(L_base, L_adj)
   - Adjustment Bounds clamping: clamp(L_eff, min_allowed, max_allowed).
4. Time-Based Risk Profiles (Session-aware):
   - Market session mapping (Pre-market, Open, Regular, Close, Post-market) across IST (Asia/Kolkata) and EST (America/New_York).
   - Session transition boundary handling.
5. Maker-Checker Manual Overrides:
   - Override application with strict validation (maker != checker, time-bounded, reason code required).
   - Bounds validation: override cannot exceed hard regulatory or mandate ceilings.
6. Deterministic Conflict Resolution Precedence:
   - HARD_CONSTRAINT > RESTRICTIVE_EMERGENCY > CONDITION_ADJUSTMENT > SCHEDULE_ADJUSTMENT > APPROVED_OVERRIDE > BASE_LIMIT.
7. Snapshot Lineage & Cryptographic Hash Generation:
   - Complete trace of baseline, conditions fired, active schedule, applied overrides, and mathematical transformations.
"""

from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, time, date
from typing import Dict, Any, List, Optional, Tuple, Union
import zoneinfo
import hashlib
import json


# Comparison operators
OP_GREATER_THAN = "GREATER_THAN"
OP_GREATER_EQUAL = "GREATER_EQUAL"
OP_LESS_THAN = "LESS_THAN"
OP_LESS_EQUAL = "LESS_EQUAL"
OP_EQUAL = "EQUAL"
OP_BETWEEN = "BETWEEN"

# Adjustment types
ADJ_MULTIPLICATIVE = "MULTIPLICATIVE"
ADJ_ADDITIVE = "ADDITIVE"
ADJ_ABSOLUTE_REPLACEMENT = "ABSOLUTE_REPLACEMENT"
ADJ_PROFILE_SWITCH = "PROFILE_SWITCH"

# Limit nature
LIMIT_NATURE_CAP = "CAP"        # e.g., max VaR, max weight, max drawdown
LIMIT_NATURE_FLOOR = "FLOOR"    # e.g., min liquidity score, min ADV, min depth

# Precedence levels (lower number = higher precedence)
PRECEDENCE_HARD_CONSTRAINT = 1
PRECEDENCE_RESTRICTIVE_EMERGENCY = 2
PRECEDENCE_CONDITION_ADJUSTMENT = 3
PRECEDENCE_SCHEDULE_ADJUSTMENT = 4
PRECEDENCE_APPROVED_OVERRIDE = 5
PRECEDENCE_BASE_LIMIT = 6


def to_decimal(val: Any) -> Decimal:
    """Converts a numeric value to Decimal safely."""
    if val is None:
        return Decimal("0")
    if isinstance(val, Decimal):
        return val
    return Decimal(str(val))


def evaluate_condition_operator(
    current_value: Decimal,
    operator: str,
    threshold_low: Decimal,
    threshold_high: Optional[Decimal] = None
) -> bool:
    """
    Evaluates a single metric value against configured thresholds using standard operators.
    """
    op = operator.upper()
    if op == OP_GREATER_THAN:
        return current_value > threshold_low
    elif op == OP_GREATER_EQUAL:
        return current_value >= threshold_low
    elif op == OP_LESS_THAN:
        return current_value < threshold_low
    elif op == OP_LESS_EQUAL:
        return current_value <= threshold_low
    elif op == OP_EQUAL:
        return current_value == threshold_low
    elif op == OP_BETWEEN:
        high = threshold_high if threshold_high is not None else threshold_low
        return threshold_low <= current_value <= high
    else:
        raise ValueError(f"Unsupported operator: {operator}")


def evaluate_hysteresis_state(
    current_value: Decimal,
    currently_active: bool,
    entry_threshold: Decimal,
    exit_threshold: Decimal,
    direction: str = "UP"  # "UP": triggers when rising above entry, exits when falling below exit
) -> bool:
    """
    Evaluates condition state under a hysteresis band to prevent rapid on/off toggling (thrashing).
    
    If direction == "UP" (e.g. Volatility spike):
      - Entry: current_value >= entry_threshold (e.g., VIX >= 25.0) -> becomes active
      - Exit: current_value < exit_threshold (e.g., VIX < 20.0) -> becomes inactive
      - Deadband (20 <= VIX < 25): retains currently_active state.
      
    If direction == "DOWN" (e.g. Liquidity dry-up):
      - Entry: current_value <= entry_threshold (e.g., Depth <= 1,000,000) -> becomes active
      - Exit: current_value > exit_threshold (e.g., Depth > 1,500,000) -> becomes inactive
      - Deadband (1,000,000 < Depth <= 1,500,000): retains currently_active state.
    """
    dir_clean = direction.upper()
    if dir_clean == "UP":
        if currently_active:
            # Remains active until dropping strictly below exit_threshold
            return current_value >= exit_threshold
        else:
            # Enters active state only when reaching or exceeding entry_threshold
            return current_value >= entry_threshold
    elif dir_clean == "DOWN":
        if currently_active:
            # Remains active until rising strictly above exit_threshold
            return current_value <= exit_threshold
        else:
            # Enters active state only when dropping to or below entry_threshold
            return current_value <= exit_threshold
    else:
        raise ValueError(f"Unsupported hysteresis direction: {direction}. Use 'UP' or 'DOWN'.")


def evaluate_composite_conditions(
    condition_results: List[bool],
    logical_operator: str = "AND"
) -> bool:
    """
    Combines individual condition evaluations with AND or OR logic.
    """
    if not condition_results:
        return False
    
    op = logical_operator.upper()
    if op == "AND":
        return all(condition_results)
    elif op == "OR":
        return any(condition_results)
    else:
        raise ValueError(f"Unsupported logical operator: {logical_operator}. Use 'AND' or 'OR'.")


def calculate_adjusted_limit(
    base_limit: Decimal,
    adjustment_type: str,
    adjustment_value: Decimal,
    nature: str = LIMIT_NATURE_CAP,
    restrictive_only: bool = True,
    min_bound: Optional[Decimal] = None,
    max_bound: Optional[Decimal] = None
) -> Tuple[Decimal, Decimal]:
    """
    Calculates the dynamically adjusted limit and applies restrictive-only and bounds constraints.
    
    Returns:
        (raw_adjusted_limit, final_effective_limit)
    """
    adj_type = adjustment_type.upper()
    nature_clean = nature.upper()
    
    if adj_type == ADJ_MULTIPLICATIVE:
        raw_adj = base_limit * adjustment_value
    elif adj_type == ADJ_ADDITIVE:
        raw_adj = base_limit + adjustment_value
    elif adj_type == ADJ_ABSOLUTE_REPLACEMENT:
        raw_adj = adjustment_value
    elif adj_type == ADJ_PROFILE_SWITCH:
        raw_adj = adjustment_value
    else:
        raise ValueError(f"Unsupported adjustment type: {adjustment_type}")
    
    # Restrictive-only enforcement
    effective = raw_adj
    if restrictive_only:
        if nature_clean == LIMIT_NATURE_CAP:
            # Caps cannot be relaxed dynamically: eff = min(base, adj)
            effective = min(base_limit, raw_adj)
        elif nature_clean == LIMIT_NATURE_FLOOR:
            # Floors cannot be weakened dynamically: eff = max(base, adj)
            effective = max(base_limit, raw_adj)
            
    # Apply hard allowed bounds if configured
    if min_bound is not None:
        effective = max(effective, min_bound)
    if max_bound is not None:
        effective = min(effective, max_bound)
        
    return (raw_adj.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
            effective.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def resolve_market_session(
    as_of_time: datetime,
    market: str = "IN"  # "IN" (NSE/BSE) or "US" (NYSE/NASDAQ)
) -> str:
    """
    Maps a timestamp to its trading session in the native exchange timezone.
    
    IN (NSE/BSE) - Asia/Kolkata:
      - 09:00 - 09:15: PRE_MARKET
      - 09:15 - 09:30: MARKET_OPEN
      - 09:30 - 15:00: REGULAR_TRADING
      - 15:00 - 15:30: MARKET_CLOSE
      - 15:30 - 16:00: POST_MARKET
      - Otherwise: CLOSED
      
    US (NYSE/NASDAQ) - America/New_York:
      - 04:00 - 09:30: PRE_MARKET
      - 09:30 - 10:00: MARKET_OPEN
      - 10:00 - 15:30: REGULAR_TRADING
      - 15:30 - 16:00: MARKET_CLOSE
      - 16:00 - 20:00: POST_MARKET
      - Otherwise: CLOSED
    """
    mkt = market.upper()
    if mkt in ("IN", "NSE", "BSE"):
        tz = zoneinfo.ZoneInfo("Asia/Kolkata")
        local_dt = as_of_time.astimezone(tz) if as_of_time.tzinfo else as_of_time.replace(tzinfo=tz)
        t = local_dt.time()
        
        # Check weekday (0 = Mon, 6 = Sun)
        if local_dt.weekday() >= 5:
            return "CLOSED"
            
        if time(9, 0) <= t < time(9, 15):
            return "PRE_MARKET"
        elif time(9, 15) <= t < time(9, 30):
            return "MARKET_OPEN"
        elif time(9, 30) <= t < time(15, 0):
            return "REGULAR_TRADING"
        elif time(15, 0) <= t < time(15, 30):
            return "MARKET_CLOSE"
        elif time(15, 30) <= t <= time(16, 0):
            return "POST_MARKET"
        else:
            return "CLOSED"
            
    elif mkt in ("US", "NYSE", "NASDAQ"):
        tz = zoneinfo.ZoneInfo("America/New_York")
        local_dt = as_of_time.astimezone(tz) if as_of_time.tzinfo else as_of_time.replace(tzinfo=tz)
        t = local_dt.time()
        
        if local_dt.weekday() >= 5:
            return "CLOSED"
            
        if time(4, 0) <= t < time(9, 30):
            return "PRE_MARKET"
        elif time(9, 30) <= t < time(10, 0):
            return "MARKET_OPEN"
        elif time(10, 0) <= t < time(15, 30):
            return "REGULAR_TRADING"
        elif time(15, 30) <= t < time(16, 0):
            return "MARKET_CLOSE"
        elif time(16, 0) <= t <= time(20, 0):
            return "POST_MARKET"
        else:
            return "CLOSED"
            
    else:
        raise ValueError(f"Unsupported market for session resolution: {market}")


def generate_lineage_hash(lineage_data: Dict[str, Any]) -> str:
    """
    Generates a deterministic SHA-256 hash of calculation inputs, policies, conditions, and outputs.
    """
    serialized = json.dumps(lineage_data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
