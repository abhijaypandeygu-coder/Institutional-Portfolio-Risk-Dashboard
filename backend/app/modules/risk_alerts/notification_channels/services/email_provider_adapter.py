"""
Email provider adapter interface and SMTP implementation for M12.07 — Notification Channels.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, Dict, Any, Tuple


class EmailProviderResult:
    def __init__(
        self,
        success: bool,
        outcome: str,  # SUCCESS, TRANSIENT_FAILURE, PERMANENT_FAILURE, TIMEOUT, RATE_LIMITED
        provider_response_code: Optional[str] = None,
        provider_message_id: Optional[str] = None,
        error_category: Optional[str] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ):
        self.success = success
        self.outcome = outcome
        self.provider_response_code = provider_response_code
        self.provider_message_id = provider_message_id
        self.error_category = error_category
        self.error_code = error_code
        self.error_message = error_message


class EmailProviderAdapter(ABC):
    @abstractmethod
    async def send_email(
        self,
        to_address: str,
        subject: str,
        text_body: str,
        html_body: str,
        sender_display: Optional[str] = None,
    ) -> EmailProviderResult:
        pass


class MockEmailProvider(EmailProviderAdapter):
    """
    Mock email provider for deterministic unit and integration testing.
    """
    def __init__(self, simulate_failure_type: Optional[str] = None):
        self.simulate_failure_type = simulate_failure_type
        self.sent_messages: list[dict] = []

    async def send_email(
        self,
        to_address: str,
        subject: str,
        text_body: str,
        html_body: str,
        sender_display: Optional[str] = None,
    ) -> EmailProviderResult:
        if self.simulate_failure_type == "TRANSIENT_TIMEOUT":
            return EmailProviderResult(
                success=False,
                outcome="TRANSIENT_FAILURE",
                error_category="NETWORK_TIMEOUT",
                error_code="TIMEOUT_408",
                error_message="Simulated connection timeout to mail gateway",
            )
        elif self.simulate_failure_type == "PERMANENT_AUTH":
            return EmailProviderResult(
                success=False,
                outcome="PERMANENT_FAILURE",
                error_category="AUTHENTICATION_FAILURE",
                error_code="AUTH_535",
                error_message="535 5.7.8 Authentication credentials invalid",
            )
        elif self.simulate_failure_type == "INVALID_RECIPIENT":
            return EmailProviderResult(
                success=False,
                outcome="PERMANENT_FAILURE",
                error_category="INVALID_RECIPIENT",
                error_code="RCPT_550",
                error_message="550 5.1.1 User mailbox not found",
            )
        elif self.simulate_failure_type == "RATE_LIMITED":
            return EmailProviderResult(
                success=False,
                outcome="RATE_LIMITED",
                error_category="PROVIDER_RATE_LIMIT",
                error_code="RATE_421",
                error_message="421 4.7.0 Too many concurrent connections",
            )

        # Successful acceptance
        import uuid
        msg_id = f"mock-msg-{uuid.uuid4().hex[:12]}"
        self.sent_messages.append({
            "to": to_address,
            "subject": subject,
            "text": text_body,
            "html": html_body,
            "msg_id": msg_id,
        })
        return EmailProviderResult(
            success=True,
            outcome="SUCCESS",
            provider_response_code="250_OK",
            provider_message_id=msg_id,
        )


class SMTPEmailProvider(EmailProviderAdapter):
    """
    Production-ready SMTP adapter loading credentials safely from environment variables.
    Never exposes passwords in logs or API payloads.
    """
    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_tls: bool = True,
        sender_email: Optional[str] = None,
        timeout_seconds: int = 10,
    ):
        self.host = host or os.getenv("SMTP_HOST", "localhost")
        self.port = port or int(os.getenv("SMTP_PORT", "587"))
        self.username = username or os.getenv("SMTP_USERNAME", "")
        self.password = password or os.getenv("SMTP_PASSWORD", "")
        self.use_tls = use_tls
        self.sender_email = sender_email or os.getenv("SMTP_SENDER_EMAIL", "risk-alerts@institutional-portfolio.internal")
        self.timeout_seconds = timeout_seconds

    async def send_email(
        self,
        to_address: str,
        subject: str,
        text_body: str,
        html_body: str,
        sender_display: Optional[str] = None,
    ) -> EmailProviderResult:
        import asyncio

        def _sync_send():
            msg = MIMEMultipart("alternative")
            sender = f"{sender_display or 'Institutional Risk Alerts'} <{self.sender_email}>"
            msg["From"] = sender
            msg["To"] = to_address
            # Sanitize subject to prevent header injection
            safe_subject = "".join(ch for ch in subject if ch not in "\r\n")
            msg["Subject"] = safe_subject

            part1 = MIMEText(text_body, "plain", "utf-8")
            part2 = MIMEText(html_body, "html", "utf-8")
            msg.attach(part1)
            msg.attach(part2)

            server = None
            try:
                server = smtplib.SMTP(self.host, self.port, timeout=self.timeout_seconds)
                if self.use_tls:
                    server.starttls()
                if self.username and self.password:
                    server.login(self.username, self.password)
                
                resp = server.sendmail(self.sender_email, [to_address], msg.as_string())
                return EmailProviderResult(
                    success=True,
                    outcome="SUCCESS",
                    provider_response_code="250_OK",
                    provider_message_id=f"smtp-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                )
            except smtplib.SMTPAuthenticationError as e:
                return EmailProviderResult(
                    success=False,
                    outcome="PERMANENT_FAILURE",
                    error_category="AUTHENTICATION_FAILURE",
                    error_code="AUTH_FAILED",
                    error_message=str(e),
                )
            except (smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused) as e:
                return EmailProviderResult(
                    success=False,
                    outcome="PERMANENT_FAILURE",
                    error_category="INVALID_RECIPIENT",
                    error_code="RECIPIENT_REFUSED",
                    error_message=str(e),
                )
            except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError, TimeoutError, OSError) as e:
                return EmailProviderResult(
                    success=False,
                    outcome="TRANSIENT_FAILURE",
                    error_category="NETWORK_TIMEOUT",
                    error_code="CONNECTION_ERROR",
                    error_message=str(e),
                )
            except Exception as e:
                return EmailProviderResult(
                    success=False,
                    outcome="TRANSIENT_FAILURE",
                    error_category="INTERNAL_PROCESSING_FAILURE",
                    error_code="GENERIC_SMTP_ERROR",
                    error_message=str(e),
                )
            finally:
                if server:
                    try:
                        server.quit()
                    except Exception:
                        pass

        # Execute in thread executor to keep async loop non-blocking
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _sync_send)

