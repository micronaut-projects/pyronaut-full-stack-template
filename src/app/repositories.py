"""Micronaut Data JDBC repositories.

Repositories are declared as ``Protocol`` classes carrying only method
signatures. ``pyronaut process`` parses each method name into a query and
generates the implementation at build time. A method name that cannot be parsed
is a build failure, not a runtime one.
"""

from typing import Protocol

from java.util import UUID
from micronaut.data.annotation import Join, Query
from micronaut.data.jdbc.annotation import JdbcRepository
from micronaut.data.model import Page, Pageable
from micronaut.data.model.query.builder.sql import Dialect
from micronaut.data.repository import CrudRepository, PageableRepository

from .dto import ItemPublic
from .entities import Item, User


@JdbcRepository(dialect=Dialect.MYSQL)
class UserRepository(CrudRepository[User, UUID], PageableRepository[User, UUID], Protocol):
    """User lookups for authentication, the admin screens and signup."""

    def findByEmail(self, email: str) -> User | None: ...

    def existsByEmail(self, email: str) -> bool: ...

    @Query(
        "SELECT * FROM users ORDER BY created_at DESC",
        countQuery="SELECT COUNT(*) FROM users",
        nativeQuery=True,
    )
    def findAllOrdered(self, pageable: Pageable) -> Page[User]: ...


@JdbcRepository(dialect=Dialect.MYSQL)
class ItemRepository(CrudRepository[Item, UUID], PageableRepository[Item, UUID], Protocol):
    """Item queries.

    Every method that returns an ``Item`` joins its owner, so ``Item.owner`` is
    never a half-populated stub. This is the Micronaut Data answer to the
    lazy-loading footguns an ORM leaves in place.
    """

    @Join(value="owner", type=Join.Type.FETCH)
    def findById(self, id: UUID) -> Item | None: ...

    @Join(value="owner", type=Join.Type.FETCH)
    def findByOwnerId(self, ownerId: UUID, pageable: Pageable) -> Page[Item]: ...

    @Join(value="owner", type=Join.Type.FETCH)
    def findAll(self, pageable: Pageable) -> Page[Item]: ...

    # A page of items as public projections, built from the row by Micronaut Data rather
    # than materialised as entities and mapped afterwards. Nothing per row crosses into
    # Python, and `owner_id` comes off the column, so neither the owner nor a fetch join is
    # needed -- which is the whole cost of the entity path: it materialises an Item *and* an
    # owner User per row purely so the mapper can read `#{item.owner.id}`.
    #
    # Measured on a paged read of 20 rows, 32 concurrent clients: 2,199 req/s through the
    # mapper, 3,157 through these. See the benchmark project's findings.
    @Query(
        "SELECT i.id, i.title, i.description, i.owner_id, i.created_at FROM items i"
        " ORDER BY i.created_at DESC",
        countQuery="SELECT COUNT(*) FROM items",
        nativeQuery=True,
    )
    def findAllProjected(self, pageable: Pageable) -> Page[ItemPublic]: ...

    @Query(
        "SELECT i.id, i.title, i.description, i.owner_id, i.created_at FROM items i"
        " WHERE i.owner_id = :ownerId ORDER BY i.created_at DESC",
        countQuery="SELECT COUNT(*) FROM items WHERE owner_id = :ownerId",
        nativeQuery=True,
    )
    def findByOwnerIdProjected(self, ownerId: UUID, pageable: Pageable) -> Page[ItemPublic]: ...

    def countByOwnerId(self, ownerId: UUID) -> int: ...
