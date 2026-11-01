"""
M04.07 Instrument Mapping Module.
Authoritative external-to-canonical identifier mapping, namespaces, normalization, and pre-ingestion resolution.
"""

from backend.app.modules.instrument_reference_data.instrument_mapping.models import (
    IdentifierNamespace,
    ExternalIdentifierMapping,
    MappingConflictRecord,
    NamespaceType,
    MappingTargetType,
    MappingStatus,
    VerificationStatus,
    ResolutionMatchingLevel
)
from backend.app.modules.instrument_reference_data.instrument_mapping.services.service import InstrumentMappingService
from backend.app.modules.instrument_reference_data.instrument_mapping.router import router

__all__ = [
    "IdentifierNamespace",
    "ExternalIdentifierMapping",
    "MappingConflictRecord",
    "NamespaceType",
    "MappingTargetType",
    "MappingStatus",
    "VerificationStatus",
    "ResolutionMatchingLevel",
    "InstrumentMappingService",
    "router"
]
