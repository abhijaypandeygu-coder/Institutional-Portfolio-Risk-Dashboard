"""
M03.05 - Duplicate Detection Module.
"""

from backend.app.modules.market_data_quality.duplicate_detection.models import (
    EventIdentityRegistry,
    DuplicateEventReceipt,
    EventIdentityConflict,
    DuplicateDetectionRule,
    DuplicateDetectionMetrics,
)
from backend.app.modules.market_data_quality.duplicate_detection.service import (
    DuplicateDetectionService,
)
from backend.app.modules.market_data_quality.duplicate_detection.router import router

__all__ = [
    "EventIdentityRegistry",
    "DuplicateEventReceipt",
    "EventIdentityConflict",
    "DuplicateDetectionRule",
    "DuplicateDetectionMetrics",
    "DuplicateDetectionService",
    "router",
]
