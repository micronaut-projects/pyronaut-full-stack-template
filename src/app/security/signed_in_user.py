"""The signed-in user, as a route parameter.

The JWT subject is the user's id as a string, so a route that needs the
signed-in user needs a lookup. ``SignedInUserFilter`` does it once per request,
after Micronaut Security has authenticated it, and leaves the user in a request
attribute. ``SignedInUserBinder`` hands that user to any route that declares a
parameter of type ``User``::

    @Get("/me")
    def read_me(user: Annotated[User, Hidden]) -> UserPublic:

``Hidden`` is for Micronaut OpenAPI, which would otherwise document the
parameter as a query parameter carrying the whole entity.

Both are Python implementations of Micronaut's own extension points: a filter is
a bean with a ``@RequestFilter`` method, and a binder implements
``TypedRequestArgumentBinder``. Both are pooled, because they run on every
request and a singleton would put all of them through one GraalPy context.
"""

from uuid import UUID

from jakarta.inject import Singleton
from java.util import Optional
from micronaut.core.bind import ArgumentBinder
from micronaut.core.convert import ArgumentConversionContext
from micronaut.core.order import Ordered
from micronaut.core.type import Argument
from micronaut.http import HttpRequest
from micronaut.http.annotation import RequestFilter, ServerFilter
from micronaut.http.bind.binders import TypedRequestArgumentBinder
from micronaut.http.filter import ServerFilterPhase
from micronaut.scheduling.annotation import ExecuteOn
from micronaut.security.authentication import AuthorizationException

from ..entities import User
from ..repositories import UserRepository

# The request attribute holding the user, when there is one.
USER = "app.security.signed_in_user"


@ServerFilter("/**")
class SignedInUserFilter(Ordered):
    """Resolves the authenticated principal to a ``User``, once per request.

    A request with no authentication is passed through untouched, and so is one
    whose subject does not resolve to a user. The second is a real case — a
    token outlives the account it was issued for — but it is not this filter's
    to reject: the login page is open to everyone, stale cookie included, and
    refusing it here would redirect the login page to itself. The binder
    refuses instead, for exactly the routes that asked for a user.
    """

    def __init__(self, users: UserRepository):
        self.users = users

    # A JDBC call, so not on the event loop.
    @RequestFilter
    @ExecuteOn("blocking")
    def resolve(self, request: HttpRequest) -> None:
        principal = request.getUserPrincipal().orElse(None)
        if principal is None:
            return
        try:
            user_id = UUID(str(principal.getName()))
        except ValueError:
            # This application issues the tokens it reads, so a subject that is
            # not a user id identifies nobody, the same as one that is gone.
            return
        user = self.users.findById(user_id).orElse(None)
        if user is not None:
            request.setAttribute(USER, user)

    def getOrder(self) -> int:
        return ServerFilterPhase.SECURITY.after()


@Singleton
class SignedInUserBinder(TypedRequestArgumentBinder[User]):
    """Binds the signed-in ``User`` to a route parameter of that type.

    Asking for a ``User`` is asking to be signed in as one. When the request
    carries no user — a token whose account is gone — this raises what an absent
    session raises, so a browser is sent to the login page and an API client
    gets 401.
    """

    def argumentType(self) -> Argument[User]:
        return Argument.of(User)

    def bind(
        self, context: ArgumentConversionContext[User], source: HttpRequest
    ) -> ArgumentBinder.BindingResult[User]:
        # Route arguments are bound after the filters have run, so the filter
        # has already had its say by the time this is asked.
        user = source.getAttribute(USER).orElse(None)
        if user is None:
            # No authentication on the exception makes it "unauthorized" rather
            # than "forbidden".
            raise AuthorizationException(None)
        return lambda: Optional.of(user)
