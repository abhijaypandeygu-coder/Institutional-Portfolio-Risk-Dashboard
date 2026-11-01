from decimal import Decimal, ROUND_HALF_EVEN

def convert_currency_price(
    source_price: Decimal,
    fx_rate: Decimal,
    direction: str = "SOURCE_TO_TARGET", # or "TARGET_TO_SOURCE"
    decimal_places: int = 6
) -> Decimal:
    """
    Converts a reference price from source currency to target currency using an explicit FX rate.
    
    Formula:
        If direction == "SOURCE_TO_TARGET":
            P_target = P_source * FX_rate
        If direction == "TARGET_TO_SOURCE":
            P_target = P_source / FX_rate
            
    Uses Python Decimal with ROUND_HALF_EVEN.
    """
    if source_price < Decimal("0"):
        raise ValueError(f"Price cannot be negative. Got {source_price}")
    if fx_rate <= Decimal("0"):
        raise ValueError(f"FX rate must be strictly positive. Got {fx_rate}")

    if direction.upper() == "SOURCE_TO_TARGET":
        converted = source_price * fx_rate
    elif direction.upper() == "TARGET_TO_SOURCE":
        converted = source_price / fx_rate
    else:
        raise ValueError(f"Invalid conversion direction: {direction}")

    quantize_format = Decimal("10") ** -decimal_places
    return converted.quantize(quantize_format, rounding=ROUND_HALF_EVEN)

