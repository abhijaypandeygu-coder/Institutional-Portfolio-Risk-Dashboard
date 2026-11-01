"""
Reason codes for rejection and exception handling.
Configurable, extensible, and structured reason code catalog.
"""
from typing import Dict, Any, List

DEFAULT_REASON_CODES: List[Dict[str, Any]] = [
    {
        "code": "REJ_SCHEMA_INVALID",
        "name": "Schema Invalidation",
        "description": "Record violates required schema structure or mandatory fields are malformed.",
        "category": "STRUCTURAL",
        "severity": "CRITICAL",
        "recoverability": "RECOVERABLE",
        "is_active": True,
    },
    {
        "code": "REJ_REQUIRED_FIELD_MISSING",
        "name": "Missing Required Field",
        "description": "One or more mandatory fields (e.g. price, timestamp, symbol) are missing.",
        "category": "SCHEMA",
        "severity": "HIGH",
        "recoverability": "RECOVERABLE",
        "is_active": True,
    },
    {
        "code": "REJ_INVALID_IDENTIFIER",
        "name": "Invalid Instrument or Listing Identifier",
        "description": "Identifier cannot be resolved or mapped in instrument master.",
        "category": "REFERENCE_DATA",
        "severity": "HIGH",
        "recoverability": "RECOVERABLE",
        "is_active": True,
    },
    {
        "code": "REJ_INVALID_VALUE",
        "name": "Mandatory Value Rule Violation",
        "description": "Mandatory numerical value is non-positive, non-finite, or absurd.",
        "category": "VALIDATION",
        "severity": "CRITICAL",
        "recoverability": "RECOVERABLE",
        "is_active": True,
    },
    {
        "code": "REJ_MARKET_RULE_VIOLATION",
        "name": "Documented Market Rule Violation",
        "description": "Observation violates exchange price band, tick size, or circuit rules.",
        "category": "MARKET_RULES",
        "severity": "HIGH",
        "recoverability": "NON_RECOVERABLE",
        "is_active": True,
    },
    {
        "code": "REJ_UNSUPPORTED_RECORD",
        "name": "Unsupported Record Type",
        "description": "Feed or adapter supplied an event that cannot be represented in canonical model.",
        "category": "COMPATIBILITY",
        "severity": "MEDIUM",
        "recoverability": "NON_RECOVERABLE",
        "is_active": True,
    },
    {
        "code": "REJ_MANUAL_DECISION",
        "name": "Authorized Manual Rejection",
        "description": "Operator or risk officer manually rejected the observation following investigation.",
        "category": "OPERATIONAL",
        "severity": "HIGH",
        "recoverability": "RECOVERABLE",
        "is_active": True,
    },
    {
        "code": "REJ_POLICY_VIOLATION",
        "name": "Configured Quality Policy Violation",
        "description": "Observation fails an active strict data quality policy rule.",
        "category": "POLICY",
        "severity": "HIGH",
        "recoverability": "RECOVERABLE",
        "is_active": True,
    },
]

