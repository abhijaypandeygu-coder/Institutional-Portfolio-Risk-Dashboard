from decimal import Decimal, ROUND_HALF_EVEN

def compute_bonus_factors(additional_shares: int, existing_shares: int) -> dict:
    """
    Computes price and quantity adjustment factors for bonus issues.
    
    Formula convention:
        b = additional_shares
        a = existing_shares
        Shareholders receive b new shares for every a shares held.
        Total shares held after bonus: a + b
        
        Quantity adjustment factor (F_Q): (a + b) / a = 1 + (b / a)
        Price adjustment factor (F_P): a / (a + b) = 1 / (1 + b/a)
        
    Invariant:
        F_P * F_Q == 1.0 (Exact mathematical reciprocity)
    """
    if additional_shares <= 0 or existing_shares <= 0:
        raise ValueError(f"Bonus terms must be strictly positive integers. Got {additional_shares} for {existing_shares}")
    
    b = Decimal(additional_shares)
    a = Decimal(existing_shares)
    
    quantity_factor = ((a + b) / a).quantize(Decimal("0.000000000001"), rounding=ROUND_HALF_EVEN)
    price_factor = (a / (a + b)).quantize(Decimal("0.000000000001"), rounding=ROUND_HALF_EVEN)
    
    return {
        "additional_shares": additional_shares,
        "existing_shares": existing_shares,
        "quantity_factor": quantity_factor,
        "price_factor": price_factor,
        "bonus_ratio_repr": f"{additional_shares}-for-{existing_shares}"
    }
