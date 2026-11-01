"""
Module 01: Feed Registry & Configuration - Validation Utilities.
"""
import re
from typing import Any, Dict, List
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from backend.app.core.security import SecretReference
from backend.app.modules.feed_registry.models import TransportProtocol
from backend.app.modules.feed_registry.schemas import ConfigurationPayload, TradingSessionInterval


class ValidationError(Exception):
    """Domain-specific validation exception."""
    pass


def validate_transport_endpoint(transport: TransportProtocol, endpoint_url: str) -> None:
    """
    Validates that the endpoint URL scheme matches the transport protocol.
    """
    parsed = urlparse(endpoint_url)
    scheme = parsed.scheme.lower()

    if transport == TransportProtocol.WEBSOCKET:
        if scheme not in ("ws", "wss"):
            raise ValidationError(
                f"Invalid endpoint scheme '{scheme}' for WEBSOCKET transport. Expected 'ws' or 'wss'."
            )
    elif transport == TransportProtocol.TCP_SOCKET:
        if scheme not in ("tcp", "ssl", "tls"):
            raise ValidationError(
                f"Invalid endpoint scheme '{scheme}' for TCP_SOCKET transport. Expected 'tcp', 'ssl', or 'tls'."
            )
    elif transport == TransportProtocol.UDP_MULTICAST:
        if scheme not in ("udp", "multicast"):
            raise ValidationError(
                f"Invalid endpoint scheme '{scheme}' for UDP_MULTICAST transport. Expected 'udp' or 'multicast'."
            )
    elif transport == TransportProtocol.HTTP_REST:
        if scheme not in ("http", "https"):
            raise ValidationError(
                f"Invalid endpoint scheme '{scheme}' for HTTP_REST transport. Expected 'http' or 'https'."
            )
    elif transport == TransportProtocol.SIMULATED:
        if scheme not in ("sim", "mock", "file", "local"):
            raise ValidationError(
                f"Invalid endpoint scheme '{scheme}' for SIMULATED transport. Expected 'sim', 'mock', 'file', or 'local'."
            )


def validate_secret_reference(secret_ref: str) -> None:
    """
    Validates that a string is a valid SecretReference syntax (secret://<scope>/<key>).
    Plaintext secrets like 'password123' will fail validation!
    """
    if not secret_ref:
        return
    
    if not SecretReference.is_valid_uri(secret_ref):
        raise ValidationError(
            f"Invalid secret reference format: '{secret_ref}'. "
            "Must follow 'secret://<scope>/<key>' to ensure zero plaintext credential storage."
        )


def validate_timezone(tz_name: str) -> None:
    """
    Validates that a string is a recognized IANA timezone identifier.
    """
    try:
        ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        raise ValidationError(f"Invalid IANA timezone: '{tz_name}'.")


def validate_session_intervals(sessions: List[TradingSessionInterval]) -> None:
    """
    Validates session start and end times in HH:MM:SS format and checks start < end.
    """
    time_regex = re.compile(r"^([01]\d|2[0-3]):([0-5]\d):([0-5]\d)$")
    for s in sessions:
        if not time_regex.match(s.start_time):
            raise ValidationError(f"Session '{s.name}' start_time '{s.start_time}' is not valid HH:MM:SS format.")
        if not time_regex.match(s.end_time):
            raise ValidationError(f"Session '{s.name}' end_time '{s.end_time}' is not valid HH:MM:SS format.")
        if s.start_time >= s.end_time:
            raise ValidationError(f"Session '{s.name}' start_time ({s.start_time}) must be earlier than end_time ({s.end_time}).")


def validate_configuration_payload(transport: TransportProtocol, payload: ConfigurationPayload) -> None:
    """
    Runs full semantic validation on configuration payload against feed transport and safety rules.
    """
    validate_transport_endpoint(transport, payload.endpoint_url)
    if payload.backup_endpoint_url:
        validate_transport_endpoint(transport, payload.backup_endpoint_url)

    if payload.auth_credentials_ref:
        validate_secret_reference(payload.auth_credentials_ref)

    if payload.reconnect_backoff_initial_ms > payload.reconnect_backoff_max_ms:
        raise ValidationError("reconnect_backoff_initial_ms cannot exceed reconnect_backoff_max_ms.")
