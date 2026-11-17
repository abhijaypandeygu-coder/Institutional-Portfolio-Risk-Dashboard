import uuid
from contextvars import ContextVar
from typing import Optional

# Asyncio-safe context propagation across coroutines
_CORRELATION_ID: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)
_REQUEST_ID: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
_USER_ID: ContextVar[Optional[str]] = ContextVar("user_id", default=None)
_JOB_ID: ContextVar[Optional[str]] = ContextVar("job_id", default=None)


class CorrelationContext:
    """Manages thread-local / async-safe correlation, request, and tracing context."""

    @classmethod
    def get_correlation_id(cls) -> str:
        cid = _CORRELATION_ID.get()
        if not cid:
            cid = f"corr-{uuid.uuid4().hex[:12]}"
            _CORRELATION_ID.set(cid)
        return cid

    @classmethod
    def set_correlation_id(cls, correlation_id: str):
        _CORRELATION_ID.set(correlation_id)

    @classmethod
    def get_request_id(cls) -> Optional[str]:
        return _REQUEST_ID.get()

    @classmethod
    def set_request_id(cls, request_id: str):
        _REQUEST_ID.set(request_id)

    @classmethod
    def get_user_id(cls) -> Optional[str]:
        return _USER_ID.get()

    @classmethod
    def set_user_id(cls, user_id: str):
        _USER_ID.set(user_id)

    @classmethod
    def get_job_id(cls) -> Optional[str]:
        return _JOB_ID.get()

    @classmethod
    def set_job_id(cls, job_id: str):
        _JOB_ID.set(job_id)

    @classmethod
    def clear(cls):
        _CORRELATION_ID.set(None)
        _REQUEST_ID.set(None)
        _USER_ID.set(None)
        _JOB_ID.set(None)
