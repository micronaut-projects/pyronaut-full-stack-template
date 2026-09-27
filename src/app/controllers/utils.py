"""Operational endpoints.

Stateless routes, so module-level functions.
"""

from typing import Annotated

from jakarta.inject import Inject
from micronaut.http.annotation import Controller, Get, Post
from micronaut.security.annotation import Secured
from micronaut.security.rules import SecurityRule

from ..dto import Message
from ..security.provider import ROLE_SUPERUSER
from ..services.mail import MailService

Controller("/api/v1/utils")

mail: Annotated[MailService, Inject]


@Get("/health-check")
@Secured(SecurityRule.IS_ANONYMOUS)
def health_check() -> bool:
    """Liveness probe. Returns `true` when the application is serving."""
    return True


@Post("/test-email")
@Secured([ROLE_SUPERUSER])
def test_email(emailTo: str) -> Message:
    """Send a test email. Superuser only.

    Useful for checking SMTP configuration end to end. In development the
    message is captured by Mailpit rather than delivered.
    """
    mail.send_test_email(emailTo)
    return Message(message="Test email sent")
