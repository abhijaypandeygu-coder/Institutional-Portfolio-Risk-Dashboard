from decimal import Decimal, ROUND_HALF_EVEN
from typing import List, Dict, Any

def compound_factors(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compounds a series of sequential corporate action factors in chronological order.
    
    Formula:
        F_cumulative_price = Product(F_P_i)
        G_cumulative_quantity = Product(F_Q_i)
        
    All intermediate and terminal factors maintain Decimal(18, 12) precision.
    """
    cumulative_price_factor = Decimal("1.000000000000")
    cumulative_quantity_factor = Decimal("1.000000000000")
    lineage_steps = []
    
    for event in events:
        p_factor = Decimal(str(event.get("price_factor", 1)))
        q_factor = Decimal(str(event.get("quantity_factor", 1)))
        
        cumulative_price_factor = (cumulative_price_factor * p_factor).quantize(
            Decimal("0.000000000001"), rounding=ROUND_HALF_EVEN
        )
        cumulative_quantity_factor = (cumulative_quantity_factor * q_factor).quantize(
            Decimal("0.000000000001"), rounding=ROUND_HALF_EVEN
        )
        
        lineage_steps.append({
            "event_id": event.get("event_id"),
            "event_type": event.get("event_type"),
            "effective_date": event.get("effective_date"),
            "step_price_factor": p_factor,
            "step_quantity_factor": q_factor,
            "running_cumulative_price_factor": cumulative_price_factor,
            "running_cumulative_quantity_factor": cumulative_quantity_factor
        })
        
    return {
        "cumulative_price_factor": cumulative_price_factor,
        "cumulative_quantity_factor": cumulative_quantity_factor,
        "step_count": len(events),
        "steps": lineage_steps
    }
