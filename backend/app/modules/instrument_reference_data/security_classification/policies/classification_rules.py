"""
Policies and rules for M04.02 Security Classification.
Defines asset categories, verification rules, source priorities, and compatibility constraints.
"""
from enum import Enum
from typing import Dict, List, Set, Any


class SchemeType(str, Enum):
    EXTERNAL_STANDARD = "EXTERNAL_STANDARD"
    VENDOR_SUPPLIED = "VENDOR_SUPPLIED"
    INTERNAL_PROPRIETARY = "INTERNAL_PROPRIETARY"
    DEVELOPMENT_SAMPLE = "DEVELOPMENT_SAMPLE"


class NodeType(str, Enum):
    SECTOR = "SECTOR"
    INDUSTRY_GROUP = "INDUSTRY_GROUP"
    INDUSTRY = "INDUSTRY"
    SUB_INDUSTRY = "SUB_INDUSTRY"


class AssetCategoryCode(str, Enum):
    COMMON_EQUITY = "COMMON_EQUITY"
    ETF = "ETF"
    PREFERRED_SECURITY = "PREFERRED_SECURITY"
    DEPOSITARY_RECEIPT = "DEPOSITARY_RECEIPT"
    REIT = "REIT"
    OTHER_SUPPORTED_EQUITY = "OTHER_SUPPORTED_EQUITY"


class AssignmentStatus(str, Enum):
    CLASSIFIED = "CLASSIFIED"
    UNCLASSIFIED = "UNCLASSIFIED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    PENDING_REVIEW = "PENDING_REVIEW"
    UNKNOWN = "UNKNOWN"
    CONFLICTED = "CONFLICTED"


class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    APPROVED = "APPROVED"
    UNVERIFIED = "UNVERIFIED"
    PENDING_REVIEW = "PENDING_REVIEW"
    CONFLICTED = "CONFLICTED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"


# Default Source Priority (Highest to lowest precedence)
SOURCE_PRIORITY: Dict[str, int] = {
    "OFFICIAL_ISSUER": 100,
    "VERIFIED_CLASSIFICATION_PROVIDER": 90,
    "INTERNAL_RESEARCH": 80,
    "VENDOR_REFERENCE_FEED": 50,
    "UNREVIEWED_MANUAL": 20,
    "DEVELOPMENT_SAMPLE": 10,
}


# Compatibility matrix between M04.01 InstrumentType and M04.02 AssetCategoryCode
ASSET_CATEGORY_COMPATIBILITY: Dict[str, Set[AssetCategoryCode]] = {
    "COMMON_STOCK": {AssetCategoryCode.COMMON_EQUITY},
    "PREFERRED_STOCK": {AssetCategoryCode.PREFERRED_SECURITY},
    "ETF": {AssetCategoryCode.ETF},
    "DEPOSITARY_RECEIPT": {AssetCategoryCode.DEPOSITARY_RECEIPT},
    "REIT": {AssetCategoryCode.REIT, AssetCategoryCode.COMMON_EQUITY},
    "OTHER_EQUITY": {AssetCategoryCode.OTHER_SUPPORTED_EQUITY, AssetCategoryCode.COMMON_EQUITY},
}


def validate_asset_category_compatibility(instrument_type: str, asset_category: str) -> bool:
    """Checks if an analytical asset category is compatible with the canonical instrument type."""
    allowed = ASSET_CATEGORY_COMPATIBILITY.get(instrument_type)
    if not allowed:
        return True  # If not explicitly restricted, allow with warning
    return AssetCategoryCode(asset_category) in allowed

