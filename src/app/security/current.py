"""Resolving the authenticated principal to a User.

The JWT subject is the user's id as a string, so every route that needs the
signed-in user has to look it up. As a bean rather than a helper function
because it needs ``UserService`` injected, and the route modules that use it are
modules — there is no constructor to thread a dependency through.
"""

from uuid import UUID

from jakarta.inject import Singleton
from micronaut.security.authentication import Authentication

from ..entities import User
from ..services.users import UserService


@Singleton
class CurrentUser:
    def __init__(self, users: UserService):
        self.users = users

    def of(self, authentication: Authentication) -> User | None:
        """The signed-in user, or None if the subject no longer resolves.

        ``authentication.getName()`` is the subject: a string, so it is parsed
        rather than handed straight to the repository.
        """
        return self.users.by_id(UUID(str(authentication.getName())))
