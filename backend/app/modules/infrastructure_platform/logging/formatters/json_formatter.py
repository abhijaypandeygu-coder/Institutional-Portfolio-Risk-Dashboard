import json
import logging
import traceback
from datetime import datetime, timezone
from typing import Dict, Any

from backend.app.modules.infrastructure_platform.logging.services.redaction_service import (
    LogRedactionService,
)
from backend.app.modules.infrastructure_platform.logging.services.correlation_context import (
    CorrelationContext,
)


class JsonLogFormatter(logging.Formatter):
    """Institutional JSON Formatter: serializes log records into structured, redacted JSON events."""

    def __init__(self, service_name: str = "institutional-portfolio-risk-dashboard", environment: str = "development"):
        super().__init__()
        self.service_name = service_name
        self.environment = environment

    def format(self, record: logging.LogRecord) -> str:
        # Base structured schema
        log_event: Dict[str, Any] = {
            "schema_version": "1.0",
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "service": self.service_name,
            "environment": self.environment,
            "logger": record.name,
            "message": record.getMessage(),
            "event_name": getattr(record, "event_name", record.name),
            "correlation_id": getattr(record, "correlation_id", None) or CorrelationContext.get_correlation_id(),
            "request_id": getattr(record, "request_id", None) or CorrelationContext.get_request_id(),
            "user_id": getattr(record, "user_id", None) or CorrelationContext.get_user_id(),
            "job_id": getattr(record, "job_id", None) or CorrelationContext.get_job_id(),
            "source_file": record.filename,
            "source_line": record.lineno,
        }

        # Extra metadata passed via logger.info("...", extra={...})
        if hasattr(record, "extra_payload") and isinstance(record.extra_payload, dict):
            for k, v in record.extra_payload.items():
                if k not in log_event:
                    log_event[k] = v

        # Exception formatting
        if record.exc_info:
            log_event["exception_type"] = record.exc_info[0].__name__ if record.exc_info[0] else "Exception"
            log_event["stack_trace"] = traceback.format_exception(*record.exc_info)

        # Apply redaction before serialization
        clean_event = LogRedactionService.sanitize(log_event)

        return json.dumps(clean_event)
