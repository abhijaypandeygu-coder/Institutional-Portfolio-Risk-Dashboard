import re
from typing import Any, Dict, List, Set, Union

SENSITIVE_KEY_PATTERNS = [
    re.compile(r"password", re.IGNORECASE),
    re.compile(r"secret", re.IGNORECASE),
    re.compile(r"token", re.IGNORECASE),
    re.compile(r"api[_-]?key", re.IGNORECASE),
    re.compile(r"auth(orization)?", re.IGNORECASE),
    re.compile(r"cookie", re.IGNORECASE),
    re.compile(r"private[_-]?key", re.IGNORECASE),
    re.compile(r"kek", re.IGNORECASE),
    re.compile(r"dek", re.IGNORECASE),
]

REDACTED_PLACEHOLDER = "[REDACTED_SENSITIVE_DATA]"


class LogRedactionService:
    """Institutional-grade log redaction engine that masks sensitive keys and regex patterns."""

    @classmethod
    def is_sensitive_key(cls, key: str) -> bool:
        for pattern in SENSITIVE_KEY_PATTERNS:
            if pattern.search(key):
                return True
        return False

    @classmethod
    def sanitize(cls, data: Any) -> Any:
        if isinstance(data, dict):
            clean_dict = {}
            for k, v in data.items():
                if cls.is_sensitive_key(str(k)):
                    clean_dict[k] = REDACTED_PLACEHOLDER
                else:
                    clean_dict[k] = cls.sanitize(v)
            return clean_dict
        elif isinstance(data, (list, tuple, set)):
            return [cls.sanitize(item) for item in data]
        elif isinstance(data, str):
            # Redact common inline patterns like Bearer tokens or connection strings
            if "Bearer " in data:
                return re.sub(r"Bearer\s+[A-Za-z0-9_\-\.]+", f"Bearer {REDACTED_PLACEHOLDER}", data)
            if "password=" in data.lower():
                return re.sub(r"password=[^;&\s]+", f"password={REDACTED_PLACEHOLDER}", data, flags=re.IGNORECASE)
            return data
        return data
