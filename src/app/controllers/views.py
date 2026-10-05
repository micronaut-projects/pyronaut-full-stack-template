"""Server-rendered browser routes.

Stateless routes, so module-level functions. A module with routes and no
``Controller`` call is mounted at ``/``, which is what these want.

Each route returns the model for one screen, and Micronaut Views React renders
the `App` component on GraalJS with that model as its props. The same component
tree then hydrates in the browser from `/static/client.js`, so the first paint
comes from the server and the page stays interactive afterwards.

Every screen also works without a server-supplied model: `frontend/src/App.jsx`
falls back to fetching from the API when `initial` is absent. That is what keeps
the hydration real rather than decorative.

The handlers are named `*_page` so their operation ids cannot collide with the
API operations of the same name — `/login` the page and `/api/v1/login` the
endpoint both exist. A collision is not an error; Micronaut OpenAPI quietly
appends a number, and the generated client grows a `signup1` whose digit
depends on declaration order.
"""

from typing import Annotated

from jakarta.inject import Inject
from micronaut.http.annotation import Get, QueryValue
from micronaut.security.annotation import Secured
from micronaut.security.authentication import Authentication
from micronaut.security.rules import SecurityRule
from micronaut.views import View
from fullstack.security import CurrentUser

from ..mappers import Projections
from ..paging import page_request
from ..services.items import ItemService
from ..services.users import UserService

APP_VIEW = "App"

users: Annotated[UserService, Inject]
items: Annotated[ItemService, Inject]
current: Annotated[CurrentUser, Inject]
projections: Annotated[Projections, Inject]


def _model(page: str, **data) -> dict:
    """The shape frontend/src/App.jsx dispatches on."""
    return {"page": page, "data": data}


# -- anonymous screens --------------------------------------------------
@Get("/login")
@View(APP_VIEW)
@Secured(SecurityRule.IS_ANONYMOUS)
def login_page(error: Annotated[bool, QueryValue(defaultValue="false")] = False) -> dict:
    """The sign-in screen."""
    return _model("login", error=error)


@Get("/signup")
@View(APP_VIEW)
@Secured(SecurityRule.IS_ANONYMOUS)
def signup_page() -> dict:
    """The registration screen."""
    return _model("signup")


@Get("/recover-password")
@View(APP_VIEW)
@Secured(SecurityRule.IS_ANONYMOUS)
def recover_password_page() -> dict:
    """The "email me a reset link" screen."""
    return _model("recoverPassword")


@Get("/reset-password")
@View(APP_VIEW)
@Secured(SecurityRule.IS_ANONYMOUS)
def reset_password_page(token: Annotated[str, QueryValue(defaultValue="")] = "") -> dict:
    """The "set a new password" screen, reached from the recovery email."""
    return _model("resetPassword", token=token)


# -- authenticated screens ----------------------------------------------
@Get("/")
@View(APP_VIEW)
@Secured(SecurityRule.IS_AUTHENTICATED)
def dashboard_page(authentication: Authentication) -> dict:
    """The dashboard."""
    return _model("dashboard", user=projections.user_public(current.of(authentication)))


@Get("/items")
@View(APP_VIEW)
@Secured(SecurityRule.IS_AUTHENTICATED)
def items_page(authentication: Authentication) -> dict:
    """The item list, server-rendered with its first page already filled in."""
    user = current.of(authentication)
    result = items.list_for(user, page_request())
    return _model(
        "items",
        user=projections.user_public(user),
        items=[projections.item_public(item) for item in result.getContent()],
        count=result.getTotalSize(),
    )


@Get("/settings")
@View(APP_VIEW)
@Secured(SecurityRule.IS_AUTHENTICATED)
def settings_page(authentication: Authentication) -> dict:
    """The account settings screen."""
    return _model("settings", user=projections.user_public(current.of(authentication)))


@Get("/forbidden")
@View(APP_VIEW)
@Secured(SecurityRule.IS_AUTHENTICATED)
def forbidden_page(authentication: Authentication) -> dict:
    """Where a signed-in user lands after asking for a page they may not see."""
    return _model("forbidden", user=projections.user_public(current.of(authentication)))


@Get("/admin")
@View(APP_VIEW)
@Secured(["ROLE_SUPERUSER"])
def admin_page(authentication: Authentication) -> dict:
    """The user administration screen. Superuser only."""
    result = users.page(page_request())
    return _model(
        "admin",
        user=projections.user_public(current.of(authentication)),
        users=[projections.user_public(user) for user in result.getContent()],
        count=result.getTotalSize(),
    )
