import time
import uuid
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.app.modules.infrastructure_platform.logging.services.correlation_context import (
    CorrelationContext,
)

logger = logging.getLogger("app.middleware.request_logging")


class StructuredRequestLoggingMiddleware(BaseHTTPMiddleware):
    """FastAPI Middleware: captures incoming correlation/request IDs, logs execution latency and status."""

    async def dispatch(self, request: Request, call_next):
        # 1. Extract or generate Correlation ID
        incoming_corr_id = request.headers.get("X-Correlation-ID") or request.headers.get("x-correlation-id")
        correlation_id = incoming_corr_id or f"corr-{uuid.uuid4().hex[:12]}"
        
        # Respect client-supplied X-Request-ID or existing state request_id if present
        incoming_req_id = request.headers.get("X-Request-ID") or request.headers.get("x-request-id")
        request_id = incoming_req_id or getattr(request.state, "request_id", None) or f"req-{uuid.uuid4().hex[:12]}"

        # Bind to async context
        CorrelationContext.set_correlation_id(correlation_id)
        CorrelationContext.set_request_id(request_id)

        start_time = time.perf_counter()

        try:
            response: Response = await call_next(request)
            duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

            # Skip logging high-frequency liveness probes unless error
            if request.url.path not in ("/health/live", "/health"):
                logger.info(
                    f"{request.method} {request.url.path} completed with {response.status_code} in {duration_ms}ms",
                    extra={
                        "event_name": "api.request.completed",
                        "extra_payload": {
                            "http_method": request.method,
                            "path": request.url.path,
                            "status_code": response.status_code,
                            "duration_ms": duration_ms,
                        },
                    },
                )

            # Attach correlation & request IDs to response headers
            response.headers["X-Correlation-ID"] = correlation_id
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            logger.error(
                f"Unhandled exception processing {request.method} {request.url.path}: {str(exc)}",
                exc_info=True,
                extra={
                    "event_name": "api.request.failed",
                    "extra_payload": {
                        "http_method": request.method,
                        "path": request.url.path,
                        "duration_ms": duration_ms,
                    },
                },
            )
            raise
        finally:
            CorrelationContext.clear()
