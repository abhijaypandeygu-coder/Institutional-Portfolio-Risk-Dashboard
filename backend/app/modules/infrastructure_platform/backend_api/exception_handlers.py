import logging
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("m15_01.backend_api.exceptions")


def setup_exception_handlers(app: FastAPI):
    """Configures centralized, institutional error envelope handlers for the application."""

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        request_id = getattr(request.state, "request_id", "unknown-req")
        details = []
        for err in exc.errors():
            loc = " -> ".join(str(l) for l in err.get("loc", []))
            details.append({
                "field": loc,
                "code": err.get("type", "VALIDATION_ERROR").upper(),
                "message": err.get("msg", "Invalid value"),
            })

        logger.warning(f"[{request_id}] Validation failure on {request.method} {request.url.path}: {details}")

        detail_msg = "; ".join(d["message"] for d in details) if details else "Validation error"
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": detail_msg,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "The request contains invalid or unprocessable fields.",
                    "details": details,
                    "request_id": request_id,
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        request_id = getattr(request.state, "request_id", "unknown-req")
        
        # Determine machine-readable error code
        code_map = {
            400: "BAD_REQUEST",
            401: "UNAUTHENTICATED",
            403: "UNAUTHORIZED_ACCESS",
            404: "RESOURCE_NOT_FOUND",
            409: "RESOURCE_STATE_CONFLICT",
            422: "UNPROCESSABLE_ENTITY",
            429: "RATE_LIMIT_EXCEEDED",
            500: "INTERNAL_SERVER_ERROR",
            503: "SERVICE_UNAVAILABLE",
        }
        err_code = code_map.get(exc.status_code, f"HTTP_{exc.status_code}")

        # Protect against leaking raw exception data if passed as dict or string
        message = exc.detail if isinstance(exc.detail, str) else "An HTTP error occurred."

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": message,
                "error": {
                    "code": err_code,
                    "message": message,
                    "details": exc.detail if isinstance(exc.detail, (list, dict)) else [],
                    "request_id": request_id,
                }
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", "unknown-req")
        logger.error(f"[{request_id}] Unhandled server exception on {request.method} {request.url.path}: {str(exc)}", exc_info=True)

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred while processing the request. Investigation logged.",
                    "details": [],
                    "request_id": request_id,
                }
            },
        )
