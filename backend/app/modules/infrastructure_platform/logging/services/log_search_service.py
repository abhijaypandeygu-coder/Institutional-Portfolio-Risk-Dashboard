import os
import json
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from backend.app.modules.infrastructure_platform.logging.handlers.log_manager import (
    LOG_FILE_PATH,
)
from backend.app.modules.infrastructure_platform.logging.services.redaction_service import (
    LogRedactionService,
)


class LogSearchService:
    """Reads and filters local structured JSONL logs without loading entire files into memory."""

    @classmethod
    def search_logs(
        cls,
        level: Optional[str] = None,
        correlation_id: Optional[str] = None,
        module: Optional[str] = None,
        query: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        if not os.path.exists(LOG_FILE_PATH):
            return []

        results: List[Dict[str, Any]] = []
        target_level = level.upper() if level else None

        # Read in reverse (latest first) up to limit
        try:
            with open(LOG_FILE_PATH, "r", encoding="utf-8") as fp:
                lines = fp.readlines()

            for line in reversed(lines):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except Exception:
                    continue

                if target_level and record.get("level") != target_level:
                    continue

                if correlation_id and record.get("correlation_id") != correlation_id:
                    continue

                if module and module.lower() not in str(record.get("module", "")).lower():
                    continue

                if query and query.lower() not in str(record.get("message", "")).lower():
                    continue

                # Ensure sensitive fields remain redacted
                results.append(LogRedactionService.sanitize(record))

                if len(results) >= limit:
                    break

        except Exception:
            return []

        return results
