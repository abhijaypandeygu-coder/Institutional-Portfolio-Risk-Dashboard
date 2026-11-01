import re
from typing import Optional


def normalize_identifier(
    raw_identifier: str,
    case_sensitive: bool = False,
    strip_exchange_suffix: bool = False
) -> str:
    """
    Applies namespace-specific normalization rules to a raw external symbol or code.
    
    Rules:
    - Strips surrounding whitespace.
    - Preserves numeric leading zeros (e.g. BSE security code '000325').
    - Standardizes uppercase if case_sensitive is False.
    - Conditionally removes vendor-specific suffixes (e.g. '.US', '.BSE') if requested by namespace configuration.
    """
    if not raw_identifier:
        return ""

    normalized = raw_identifier.strip()
    
    if strip_exchange_suffix:
        # e.g. "AAPL.US" -> "AAPL", "RELIANCE.NS" -> "RELIANCE"
        normalized = re.sub(r"\.[A-Za-z0-9]+$", "", normalized)
        
    if not case_sensitive:
        normalized = normalized.upper()
        
    return normalized

