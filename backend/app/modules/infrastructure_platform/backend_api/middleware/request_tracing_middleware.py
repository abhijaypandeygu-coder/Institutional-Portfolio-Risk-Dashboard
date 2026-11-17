import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"
PROCESS_TIME_HEADER = "X-Process-Time"


class RequestTracingMiddleware(BaseHTTPMiddleware):
    """Institutional request correlation, timing, and security header middleware."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Extract or generate unique request correlation ID
        req_id = request.headers.get(REQUEST_ID_HEADER)
        if not req_id or len(req_id.strip()) == 0:
            req_id = f"req-{uuid.uuid4().hex[:12]}"

        # Store in request state for downstream handlers and error formatters
        request.state.request_id = req_id

        start_time = time.perf_counter()
        response = await call_next(request)
        process_time = time.perf_counter() - start_time

        # Inject tracing & security headers into response
        response.headers[REQUEST_ID_HEADER] = req_id
        response.headers[PROCESS_TIME_HEADER] = f"{process_time:.6f}s"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"

        return response
