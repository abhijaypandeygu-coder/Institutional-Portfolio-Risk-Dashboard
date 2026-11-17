import hashlib
import json
from datetime import timezone
from typing import Dict, Any

class CanonicalEventSerializer:
    """Deterministic, canonical serialization and cryptographic SHA-256 calculation for audit events.

    Excludes non-deterministic or database-generated local IDs. Normalizes keys, decimals,
    nulls, and ISO-8601 UTC timestamps.
    """

    @classmethod
    def canonicalize(cls, event_dict: Dict[str, Any]) -> str:
        """Produce deterministic canonical JSON string."""
        clean_dict = {}
        for k in sorted(event_dict.keys()):
            # Exclude runtime volatile fields
            if k in ("id", "recorded_at", "verification_status"):
                continue
            val = event_dict[k]
            clean_dict[k] = cls._normalize_value(val)

        return json.dumps(clean_dict, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    @classmethod
    def _normalize_value(cls, val: Any) -> Any:
        if isinstance(val, dict):
            return {k: cls._normalize_value(v) for k, v in sorted(val.items())}
        elif isinstance(val, (list, tuple)):
            return [cls._normalize_value(v) for v in val]
        elif hasattr(val, "isoformat"):
            # Normalize datetime without tzinfo or in UTC uniformly
            if hasattr(val, "tzinfo") and val.tzinfo is not None:
                val = val.astimezone(timezone.utc).replace(tzinfo=None)
            return val.isoformat()
        elif hasattr(val, "value"): # Enum
            return val.value
        return val

    @classmethod
    def compute_event_hash(cls, canonical_str: str, previous_hash: str) -> str:
        """Compute SHA-256 hash chaining H_i = SHA256(canonical_str || H_{i-1})."""
        input_data = f"{canonical_str}||{previous_hash}".encode("utf-8")
        return hashlib.sha256(input_data).hexdigest()
