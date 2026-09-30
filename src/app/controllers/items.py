"""Item CRUD.

Stateless routes, so module-level functions. ``Controller`` and ``Secured`` are
called at module level rather than decorating a class, and the services arrive
through module-level ``Annotated[..., Inject]`` declarations.

Ownership is not expressible as a role, so it stays an explicit check here, the
same way the upstream template does it. Everything that *is* expressible as a
role — "must be signed in", "must be a superuser" — is left to ``Secured``.
"""

from typing import Annotated
from uuid import UUID

from jakarta.inject import Inject
from jakarta.validation import Valid
from micronaut.http import HttpResponse, HttpStatus
from micronaut.http.annotation import Body, Controller, Delete, Get, Post, Put, QueryValue
from micronaut.security.annotation import Secured
from micronaut.security.authentication import Authentication
from micronaut.security.rules import SecurityRule
from fullstack.security import CurrentUser

from ..dto import ItemCreate, ItemUpdate, ItemsPublic, Message
from ..mappers import Projections
from ..paging import DEFAULT_PAGE_SIZE, page_request
from ..services.items import ItemService

Controller("/api/v1/items")
Secured(SecurityRule.IS_AUTHENTICATED)

items: Annotated[ItemService, Inject]
current: Annotated[CurrentUser, Inject]
projections: Annotated[Projections, Inject]

FORBIDDEN = Message(message="The user doesn't have enough privileges")


def _accessible(itemId: UUID, authentication: Authentication):
    """The item, or an HttpResponse explaining why it is not available.

    Returns a (item, response) pair: exactly one is None. The three routes that
    load an item by id all owe the same 404-then-403 answer, and writing it once
    keeps them from drifting apart.
    """
    item = items.by_id(itemId)
    if item is None:
        return None, HttpResponse.notFound()
    if not items.may_access(item, current.of(authentication)):
        return None, HttpResponse.status(HttpStatus.FORBIDDEN).body(FORBIDDEN)
    return item, None


@Get
def list_items(
    authentication: Authentication,
    page: Annotated[int, QueryValue(defaultValue="0")] = 0,
    size: Annotated[int, QueryValue(defaultValue="100")] = DEFAULT_PAGE_SIZE,
) -> ItemsPublic:
    """List items.

    A superuser sees every item; everyone else sees only their own.
    Paginated with `page` and `size`.
    """
    result = items.list_for(current.of(authentication), page_request(page, size))
    return projections.items_public(result.getContent(), result.getTotalSize())


@Get("/{itemId}")
def read_item(itemId: UUID, authentication: Authentication) -> HttpResponse:
    """Fetch one item by id.

    Returns 404 when the item does not exist and 403 when it belongs to
    someone else.
    """
    item, refusal = _accessible(itemId, authentication)
    return refusal or HttpResponse.ok(projections.item_public(item))


@Post
def create_item(
    authentication: Authentication, body: Annotated[ItemCreate, Body, Valid]
) -> HttpResponse:
    """Create an item owned by the authenticated user."""
    item = items.create(body, current.of(authentication))
    return HttpResponse.status(HttpStatus.CREATED).body(projections.item_public(item))


@Put("/{itemId}")
def update_item(
    itemId: UUID,
    authentication: Authentication,
    body: Annotated[ItemUpdate, Body, Valid],
) -> HttpResponse:
    """Update an item. Only the owner, or a superuser, may do so."""
    item, refusal = _accessible(itemId, authentication)
    return refusal or HttpResponse.ok(projections.item_public(items.update(item, body)))


@Delete("/{itemId}")
def delete_item(itemId: UUID, authentication: Authentication) -> HttpResponse:
    """Delete an item. Only the owner, or a superuser, may do so."""
    item, refusal = _accessible(itemId, authentication)
    if refusal is not None:
        return refusal
    items.delete(item)
    return HttpResponse.ok(Message(message="Item deleted successfully"))
