"""User management.

Stateless routes, so module-level functions. ``Controller`` and ``Secured`` are
called at module level rather than decorating a class, and the services arrive
through module-level ``Annotated[..., Inject]`` declarations.

Docstrings on these functions become the operation descriptions in the OpenAPI
document that ``pyronaut process`` generates, which in turn become the doc
comments on the generated TypeScript client. They are the API reference, so
write them for the person calling the endpoint.
"""

from typing import Annotated
from uuid import UUID

from jakarta.inject import Inject
from jakarta.validation import Valid
from micronaut.http import HttpResponse, HttpStatus
from micronaut.http.annotation import Body, Controller, Delete, Get, Patch, Post, QueryValue
from micronaut.security.annotation import Secured
from micronaut.security.rules import SecurityRule
from swagger.v3.oas.annotations import Hidden

from ..dto import (
    ApiError,
    Message,
    UpdatePassword,
    UserCreate,
    UserPublic,
    UserRegister,
    UserUpdate,
    UserUpdateMe,
    UsersPublic,
)
from ..entities import User
from ..ids import same_id
from ..mappers import Projections
from ..paging import DEFAULT_PAGE_SIZE, page_request
from ..security.provider import ROLE_SUPERUSER
from ..services.mail import MailService
from ..services.users import EmailAlreadyUsed, UserService

Controller("/api/v1/users")
Secured(SecurityRule.IS_AUTHENTICATED)

users: Annotated[UserService, Inject]
mail: Annotated[MailService, Inject]
projections: Annotated[Projections, Inject]

NOT_ALLOWED_SELF_DELETE = "Superusers are not allowed to delete themselves"


def _email_conflict() -> HttpResponse:
    """409 for a duplicate email, in the one API error shape.

    ``EmailAlreadyUsed`` is a Python exception, and Micronaut's
    ``ExceptionHandler<T extends Throwable, R>`` bound only accepts Java
    throwables — so this is caught in the route rather than handled by a bean
    like the validation failures in ``errors.py``.
    """
    return HttpResponse.status(HttpStatus.CONFLICT).body(
        ApiError(
            message="A user with this email already exists",
            errors={"email": "Already registered"},
        )
    )


# -- collection ------------------------------------------------------
@Get
@Secured([ROLE_SUPERUSER])
def list_users(
    # Annotation values must be compile-time constants: the processor reads
    # them from source and cannot evaluate an expression, so a computed
    # default silently drops out and the parameter is published as required.
    page: Annotated[int, QueryValue(defaultValue="0")] = 0,
    size: Annotated[int, QueryValue(defaultValue="100")] = DEFAULT_PAGE_SIZE,
) -> UsersPublic:
    """List all users. Superuser only.

    Paginated with `page` and `size`. The total count is returned alongside
    the page so a client can render pagination controls without a second
    request.
    """
    result = users.page(page_request(page, size))
    return projections.users_public(result.getContent(), result.getTotalSize())


@Post
@Secured([ROLE_SUPERUSER])
def create_user(body: Annotated[UserCreate, Body, Valid]) -> HttpResponse:
    """Create a user. Superuser only.

    If email delivery is configured the new user is sent their credentials.
    """
    try:
        user = users.create(body)
    except EmailAlreadyUsed:
        return _email_conflict()
    mail.send_new_account_email(user.email, user.email, body.password)
    return HttpResponse.status(HttpStatus.CREATED).body(projections.user_public(user))


# -- the authenticated user -------------------------------------------
@Get("/me")
def read_me(user: Annotated[User, Hidden]) -> UserPublic:
    """Return the currently authenticated user."""
    return projections.user_public(user)


@Patch("/me")
def update_me(
    user: Annotated[User, Hidden], body: Annotated[UserUpdateMe, Body, Valid]
) -> UserPublic:
    """Update the authenticated user's own name or email."""
    return projections.user_public(users.update_me(user, body))


@Patch("/me/password")
def update_my_password(
    user: Annotated[User, Hidden], body: Annotated[UpdatePassword, Body, Valid]
) -> HttpResponse:
    """Change the authenticated user's password.

    Requires the current password. Returns 400 if it does not match, or if
    the new password is the same as the current one.
    """
    if not users.verify_password(user, body.currentPassword):
        return HttpResponse.badRequest(Message(message="Incorrect password"))
    if body.currentPassword == body.newPassword:
        return HttpResponse.badRequest(
            Message(message="The new password must differ from the current one")
        )
    users.set_password(user, body.newPassword)
    return HttpResponse.ok(Message(message="Password updated successfully"))


@Delete("/me")
def delete_me(user: Annotated[User, Hidden]) -> HttpResponse:
    """Delete the authenticated user's own account.

    A superuser may not delete themselves; doing so could leave the system
    with no administrator.
    """
    if user.isSuperuser:
        return HttpResponse.badRequest(Message(message=NOT_ALLOWED_SELF_DELETE))
    users.delete(user)
    return HttpResponse.ok(Message(message="User deleted successfully"))


# -- registration ------------------------------------------------------
@Post("/signup")
@Secured(SecurityRule.IS_ANONYMOUS)
def signup(body: Annotated[UserRegister, Body, Valid]) -> HttpResponse:
    """Register a new account.

    Open registration: the created user is always active and never a
    superuser, whatever the request asks for.
    """
    try:
        user = users.register(body)
    except EmailAlreadyUsed:
        return _email_conflict()
    return HttpResponse.status(HttpStatus.CREATED).body(projections.user_public(user))


# -- by id --------------------------------------------------------------
@Get("/{userId}")
def read_user(userId: UUID, requester: Annotated[User, Hidden]) -> HttpResponse:
    """Fetch a user by id.

    A user may always read their own record; reading anyone else's requires
    superuser.
    """
    if not same_id(requester.id, userId) and not requester.isSuperuser:
        return HttpResponse.status(HttpStatus.FORBIDDEN).body(
            Message(message="The user doesn't have enough privileges")
        )
    user = users.by_id(userId)
    return HttpResponse.notFound() if user is None else HttpResponse.ok(projections.user_public(user))


@Patch("/{userId}")
@Secured([ROLE_SUPERUSER])
def update_user(userId: UUID, body: Annotated[UserUpdate, Body, Valid]) -> HttpResponse:
    """Update any user. Superuser only."""
    user = users.by_id(userId)
    if user is None:
        return HttpResponse.notFound()
    try:
        return HttpResponse.ok(projections.user_public(users.update(user, body)))
    except EmailAlreadyUsed:
        return _email_conflict()


@Delete("/{userId}")
@Secured([ROLE_SUPERUSER])
def delete_user(userId: UUID, requester: Annotated[User, Hidden]) -> HttpResponse:
    """Delete any user, and their items. Superuser only.

    A superuser may not delete their own account through this endpoint
    either.
    """
    user = users.by_id(userId)
    if user is None:
        return HttpResponse.notFound()
    if same_id(user.id, requester.id):
        return HttpResponse.badRequest(Message(message=NOT_ALLOWED_SELF_DELETE))
    users.delete(user)
    return HttpResponse.ok(Message(message="User deleted successfully"))
