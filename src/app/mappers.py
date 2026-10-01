"""Entity to DTO projections.

The single-entity projections are compile-time bean mappers: an abstract method
annotated ``@Mapper`` on a ``Protocol``, whose implementation Micronaut generates
during ``pyronaut process``. The conversions the public shapes need come for
free — ``java.util.UUID`` and ``java.time.Instant`` become the ``str`` fields the
DTOs declare, and a source property the target does not have, such as
``hashedPassword``, is simply not carried across.

``ownerId`` is the one field that needs saying out loud, because it comes from a
relation rather than a property of the same name.

"""

from typing import Protocol

from jakarta.inject import Singleton
from micronaut.context.annotation import Mapper
from micronaut.context.python.scope import ContextPooled

from .dto import ItemPublic, ItemsPublic, UserPublic, UsersPublic
from .entities import Item, User


@Singleton
class UserMapper(Protocol):
    @Mapper
    def to_public(self, user: User) -> UserPublic: ...


@Singleton
class ItemMapper(Protocol):
    # The owner is a MANY_TO_ONE relation, so there is no `ownerId` on the entity
    # for the mapper to match by name.
    @Mapper.Mapping(to="ownerId", from_="#{item.owner.id}")
    @Mapper
    def to_public(self, item: Item) -> ItemPublic: ...


# Pooled, so a projection runs in whichever context serves the request.
@ContextPooled
class Projections:
    def __init__(self, users: UserMapper, items: ItemMapper):
        self.users = users
        self.items = items

    def user_public(self, user: User) -> UserPublic:
        """Public projection of a user. Never includes the password hash."""
        return self.users.to_public(user)

    def users_public(self, users, count: int) -> UsersPublic:
        return UsersPublic(data=[self.users.to_public(u) for u in users], count=int(count))

    def item_public(self, item: Item) -> ItemPublic:
        return self.items.to_public(item)

    def items_public(self, items, count: int) -> ItemsPublic:
        return ItemsPublic(data=[self.items.to_public(i) for i in items], count=int(count))
