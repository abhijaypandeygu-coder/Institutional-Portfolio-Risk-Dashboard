from decimal import Decimal, ROUND_HALF_EVEN
from typing import Optional

def compute_cash_dividend_factor(
    pre_event_price: Decimal,
    dividend_amount: Decimal,
    withholding_tax_rate: Optional[Decimal] = None,
    use_net_basis: bool = False
) -> dict:
    """
    Computes standard institutional cash dividend price adjustment factor.
    
    Formula:
        Effective Dividend (D_eff) = dividend_amount * (1 - withholding_tax_rate) if use_net_basis else dividend_amount
        Price factor (F_P) = (pre_event_price - D_eff) / pre_event_price
        
    Quantity factor:
        For pure cash dividends, quantity factor is 1.0 (share count remains unchanged).
    """
    if pre_event_price <= Decimal("0"):
        raise ValueError(f"Pre-event price must be strictly positive. Got {pre_event_price}")
    if dividend_amount < Decimal("0"):
        raise ValueError(f"Dividend amount cannot be negative. Got {dividend_amount}")
        
    tax_rate = withholding_tax_rate if (withholding_tax_rate is not None and use_net_basis) else Decimal("0")
    effective_dividend = dividend_amount * (Decimal("1") - tax_rate)
    
    if effective_dividend >= pre_event_price:
        raise ValueError(f"Effective dividend {effective_dividend} exceeds or equals pre-event price {pre_event_price}")
        
    price_factor = ((pre_event_price - effective_dividend) / pre_event_price).quantize(
        Decimal("0.000000000001"), rounding=ROUND_HALF_EVEN
    )
    quantity_factor = Decimal("1.000000000000")
    
    return {
        "pre_event_price": pre_event_price,
        "gross_dividend": dividend_amount,
        "effective_dividend": effective_dividend,
        "price_factor": price_factor,
        "quantity_factor": quantity_factor,
        "withholding_tax_rate": tax_rate,
        "use_net_basis": use_net_basis
    }
