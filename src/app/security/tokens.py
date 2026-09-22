"""Password-reset tokens.

A reset token is a short-lived JWT of its own, carrying a ``purpose`` claim, so
it cannot be replayed as an access token and an access token cannot be replayed
as a reset. The upstream template signs its reset tokens with the same key and
distinguishes them the same way.
"""

from datetime import timedelta

from jakarta.inject import Singleton
from micronaut.security.token.jwt.generator import JwtTokenGenerator
from micronaut.security.token.jwt.validator import JwtTokenValidator

from ..config import AppConfig

SUBJECT_CLAIM = "sub"
PURPOSE_CLAIM = "purpose"
PASSWORD_RESET = "password-reset"


@Singleton
class PasswordResetTokens:
    """Issues and verifies password-reset tokens."""

    def __init__(
        self,
        config: AppConfig,
        generator: JwtTokenGenerator,
        validator: JwtTokenValidator,
    ):
        self.config = config
        self.generator = generator
        self.validator = validator

    def issue(self, email: str) -> str:
        expiry = int(timedelta(hours=self.config.email_reset_token_expire_hours).total_seconds())
        claims = {SUBJECT_CLAIM: email, PURPOSE_CLAIM: PASSWORD_RESET}
        return str(self.generator.generateToken(claims, expiry).orElseThrow())

    def verify(self, token: str) -> str | None:
        """Return the email the token was issued for, or None if it is not valid."""
        try:
            authentication = self.validator.validateToken(token, None).orElse(None)
        except Exception:
            return None
        if authentication is None:
            return None
        attributes = authentication.getAttributes()
        if str(attributes.get(PURPOSE_CLAIM)) != PASSWORD_RESET:
            return None
        subject = attributes.get(SUBJECT_CLAIM) or authentication.getName()
        return str(subject) if subject is not None else None
