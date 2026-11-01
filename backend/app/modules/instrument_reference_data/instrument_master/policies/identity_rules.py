"""
M04.01 Instrument Master - Policies and Validators.
Includes ISIN format/checksum validation, lifecycle states, and identification policies.
"""
import re
from enum import Enum
from typing import Optional


class InstrumentType(str, Enum):
    COMMON_STOCK = "COMMON_STOCK"
    PREFERRED_STOCK = "PREFERRED_STOCK"
    ETF = "ETF"
    DEPOSITARY_RECEIPT = "DEPOSITARY_RECEIPT"
    REIT = "REIT"
    OTHER_EQUITY = "OTHER_EQUITY"


class LifecycleStatus(str, Enum):
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    INACTIVE = "INACTIVE"
    DELISTED = "DELISTED"
    RETIRED = "RETIRED"
    SUPERSEDED = "SUPERSEDED"
    UNKNOWN = "UNKNOWN"


class ListingStatus(str, Enum):
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    INACTIVE = "INACTIVE"
    DELISTED = "DELISTED"
    EXPIRED = "EXPIRED"
    UNKNOWN = "UNKNOWN"


class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    PENDING_REVIEW = "PENDING_REVIEW"
    CONFLICTED = "CONFLICTED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"


class ImportStatus(str, Enum):
    RECEIVED = "RECEIVED"
    PARSING = "PARSING"
    VALIDATING = "VALIDATING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    APPROVED = "APPROVED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class MatchClassification(str, Enum):
    EXACT_MATCH = "EXACT_MATCH"
    STRONG_MATCH = "STRONG_MATCH"
    POSSIBLE_MATCH = "POSSIBLE_MATCH"
    CONFLICT = "CONFLICT"
    NO_MATCH = "NO_MATCH"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


ISIN_REGEX = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")


def validate_isin_checksum(isin: str) -> bool:
    """
    Validates ISIN structure and Luhn checksum (ISO 6166).
    12 characters: 2-letter country code, 9 alphanumeric security identifier, 1 check digit.
    """
    if not isin or not ISIN_REGEX.match(isin):
        return False

    # Convert letters to digits: A=10, B=11, ..., Z=35
    digits_str = ""
    for char in isin[:-1]:
        if char.isdigit():
            digits_str += char
        else:
            digits_str += str(ord(char) - ord('A') + 10)

    # Luhn algorithm: double every second digit from right to left
    total = 0
    double = True
    for digit in reversed(digits_str):
        d = int(digit)
        if double:
            d *= 2
            if d > 9:
                d = (d // 10) + (d % 10)
        total += d
        double = not double

    check_digit = (10 - (total % 10)) % 10
    return check_digit == int(isin[-1])
