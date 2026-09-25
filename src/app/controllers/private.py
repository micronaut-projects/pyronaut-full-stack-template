"""Test-support endpoints, available only in the `dev` and `test` environments.

`Requires(env=...)` is evaluated when the bean is loaded, so in production these
routes do not exist at all — they are not routes that check a flag, they are
routes that were never registered. The upstream template achieves the same thing
by conditionally including a router.

They exist so that end-to-end tests can create a user directly instead of going
through signup and email verification.

Stateless routes, so module-level functions: `Controller`, `Requires` and
`Secured` are called at module level rather than decorating a class. Pyronaut
puts a module-level annotation call onto the generated bean, the same as a class
decorator — verified here by reading the metadata back out of
`app.controllers.$Private$Definition`, which carries `Requires` with `dev` and
`test` exactly as the class version did. Worth checking if this is ever
restructured: losing that gate would publish an unauthenticated user-creation
endpoint in production.
"""

from typing import Annotated

from jakarta.inject import Inject
from jakarta.validation import Valid
from micronaut.context.annotation import Requires
from micronaut.http import HttpResponse, HttpStatus
from micronaut.http.annotation import Body, Controller, Post
from micronaut.security.annotation import Secured
from micronaut.security.rules import SecurityRule

from ..dto import UserCreate
from ..mappers import user_public
from ..services.users import EmailAlreadyUsed, UserService

Controller("/api/v1/private")
Requires(env=["dev", "test"])
Secured(SecurityRule.IS_ANONYMOUS)

users: Annotated[UserService, Inject]


@Post("/users")
def create_user_directly(body: Annotated[UserCreate, Body, Valid]) -> HttpResponse:
    """Create a user without authentication. Never available in production.

    Named distinctly from `create_user` on the users controller: operation
    ids must be unique across the whole API or the generated client ends up
    with a `createUser1`, whose number depends on declaration order.
    """
    try:
        user = users.create(body)
    except EmailAlreadyUsed:
        return HttpResponse.status(HttpStatus.CONFLICT).body(
            user_public(users.by_email(body.email))
        )
    return HttpResponse.status(HttpStatus.CREATED).body(user_public(user))
