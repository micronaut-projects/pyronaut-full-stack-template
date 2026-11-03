"""Login-adjacent endpoints: token check and password recovery.

These are stateless routes, so they are module-level functions rather than
methods on a class. ``Controller("/api/v1")`` called at module level sets the
prefix without introducing one, and the services arrive through module-level
``Annotated[..., Inject]`` declarations.

Login and logout themselves are not here. Micronaut Security provides them at
`/api/v1/login` and `/api/v1/logout`, configured in `config/application.toml`;
the authentication itself lives in `app/security/provider.py`.

That is the one deliberate departure from the upstream template, which exposes
`POST /login/access-token` taking an OAuth2 form and answering with a bearer
token. Here the login page posts an ordinary form to `/api/v1/login`, and
Micronaut Security answers with a redirect and the session cookie.
"""

from typing import Annotated

from jakarta.inject import Inject
from jakarta.validation import Valid
from micronaut.http import HttpResponse
from micronaut.http.annotation import Body, Controller, Get, Post
from micronaut.security.annotation import Secured
from micronaut.security.rules import SecurityRule
from swagger.v3.oas.annotations import Hidden

from ..dto import Message, NewPassword, UserPublic
from ..entities import User
from ..mappers import Projections
from ..security.tokens import PasswordResetTokens
from ..services.mail import MailService
from ..services.users import UserService

Controller("/api/v1")

users: Annotated[UserService, Inject]
mail: Annotated[MailService, Inject]
tokens: Annotated[PasswordResetTokens, Inject]
projections: Annotated[Projections, Inject]


@Get("/login/test-token")
@Secured(SecurityRule.IS_AUTHENTICATED)
def test_token(user: Annotated[User, Hidden]) -> UserPublic:
    """Verify an access token and return the user it belongs to."""
    return projections.user_public(user)


@Post("/password-recovery/{email}")
@Secured(SecurityRule.IS_ANONYMOUS)
def recover_password(email: str) -> Message:
    """Send a password recovery link.

    The response is identical whether or not the address is registered, so
    this endpoint cannot be used to discover which emails have accounts.
    """
    user = users.by_email(email)
    if user is not None:
        token = tokens.issue(user.email)
        mail.send_reset_password_email(user.email, user.email, token)
    return Message(message="If that email is registered, we sent a password recovery link")


@Post("/reset-password")
@Secured(SecurityRule.IS_ANONYMOUS)
def reset_password(body: Annotated[NewPassword, Body, Valid]) -> HttpResponse:
    """Set a new password using a recovery token.

    An expired token, a token issued for another purpose, and a token for a
    user that no longer exists all return the same error, so the response
    reveals nothing about which case applied.
    """
    email = tokens.verify(body.token)
    if email is None:
        return HttpResponse.badRequest(Message(message="Invalid token"))
    user = users.by_email(email)
    if user is None or not user.isActive:
        return HttpResponse.badRequest(Message(message="Invalid token"))
    users.set_password(user, body.newPassword)
    return HttpResponse.ok(Message(message="Password updated successfully"))
