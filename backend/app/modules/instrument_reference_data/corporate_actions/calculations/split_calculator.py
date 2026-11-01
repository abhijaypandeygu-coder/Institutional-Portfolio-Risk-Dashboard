from decimal import Decimal, ROUND_HALF_EVEN

def compute_split_factors(numerator: int, denominator: int) -> dict:
    """
    Computes price and quantity adjustment factors for stock splits and reverse splits.
    
    Ratio convention:
        r = numerator / denominator  (e.g., 2:1 split -> numerator=2, denominator=1; r = 2.0)
        Quantity adjustment factor (F_Q): r = numerator / denominator
        Price adjustment factor (F_P): 1 / r = denominator / numerator
    
    Reverse split example:
        1:10 reverse split -> numerator=1, denominator=10; r = 0.1
        Quantity adjustment factor (F_Q): 0.1 (shares decrease)
        Price adjustment factor (F_P): 10.0 (price increases)
    
    Invariant:
        F_P * F_Q == 1.0 (Exact mathematical reciprocity)
    """
    if numerator <= 0 or denominator <= 0:
        raise ValueError(f"Split ratio terms must be strictly positive integers. Got {numerator}:{denominator}")
    
    num_dec = Decimal(numerator)
    den_dec = Decimal(denominator)
    
    quantity_factor = (num_dec / den_dec).quantize(Decimal("0.000000000001"), rounding=ROUND_HALF_EVEN)
    price_factor = (den_dec / num_dec).quantize(Decimal("0.000000000001"), rounding=ROUND_HALF_EVEN)
    
    return {
        "ratio": quantity_factor,
        "quantity_factor": quantity_factor,
        "price_factor": price_factor,
        "numerator": numerator,
        "denominator": denominator,
        "ratio_repr": f"{numerator}:{denominator}"
    }

