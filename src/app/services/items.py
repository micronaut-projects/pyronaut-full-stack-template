"""Item service.

Corresponds to ``api/routes/items.py`` in the upstream template, minus the HTTP
concerns. Pagination is a ``Pageable`` handed to the repository, so the count
query is generated rather than written out per endpoint.
"""

from uuid import UUID
from micronaut.context.python.scope import ContextPooled
from jakarta.transaction import Transactional
from micronaut.data.model import Page, Pageable

from ..dto import ItemCreate, ItemPublic, ItemUpdate
from ..entities import Item, User
from ..ids import same_id
from ..repositories import ItemRepository


@ContextPooled
class ItemService:
    def __init__(self, items: ItemRepository):
        self.items = items

    def by_id(self, item_id: UUID) -> Item | None:
        return self.items.findById(item_id).orElse(None)

    def list_for(self, user: User, pageable: Pageable) -> Page[Item]:
        """Superusers see every item; everyone else sees their own."""
        if user.isSuperuser:
            return self.items.findAll(pageable)
        return self.items.findByOwnerId(user.id, pageable)

    def list_public_for(self, user: User, pageable: Pageable) -> Page[ItemPublic]:
        """The same page as ``list_for``, projected in Java rather than mapped in Python.

        A list response needs nothing from an ``Item`` that the row does not already carry,
        so there is no reason to build one per row -- nor an owner ``User`` per row, which
        the entity path needs only to read an id that is already the ``owner_id`` column.
        """
        if user.isSuperuser:
            return self.items.findAllProjected(pageable)
        return self.items.findByOwnerIdProjected(user.id, pageable)

    @staticmethod
    def is_owned_by(item: Item, user: User) -> bool:
        return item.owner is not None and same_id(item.owner.id, user.id)

    @staticmethod
    def may_access(item: Item, user: User) -> bool:
        return user.isSuperuser or ItemService.is_owned_by(item, user)

    @Transactional
    def create(self, data: ItemCreate, owner: User) -> Item:
        return self.items.save(
            Item(title=data.title, description=data.description, owner=owner)
        )

    @Transactional
    def update(self, item: Item, data: ItemUpdate) -> Item:
        if data.title is not None:
            item.title = data.title
        if data.description is not None:
            item.description = data.description
        return self.items.update(item)

    @Transactional
    def delete(self, item: Item) -> None:
        self.items.delete(item)
