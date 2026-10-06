"""Comparing ids across the Python/Java boundary.

The same UUID reaches Python in more than one shape. An entity the route was
handed as a parameter has been converted to the Python dataclass, and its ``id``
is a ``uuid.UUID``. An entity reached through a repository can still be the Java
object: the ``owner`` joined onto an ``Item`` is one, and its ``id`` is a foreign
value whose ``str()`` is ``UUID('...')``, not the bare text. Not every repository
result is like that — ``str(user.id)`` of the user the authentication provider
loads is the bare text, which is what the JWT subject is made of.

So ``str(a.id) == str(b.id)`` is only right when both sides happen to share a
shape, and wrong without complaint when they do not: the owner of an item was
refused it, and the check that stops a superuser deleting their own account
passed. Compare ids with ``same_id`` instead.

This is a workaround; micronaut-projects/pyronaut#311 tracks the cause.
"""

import re

_UUID = re.compile(r"^(?:UUID\(')?([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})(?:'\))?$", re.IGNORECASE)


def _text(value) -> str:
    """The bare, lower-case text of a UUID in either shape.

    Raises for anything else, so that comparing the wrong thing — an entity
    rather than its id, say — fails in a test instead of answering False.
    """
    match = _UUID.match(str(value))
    if match is None:
        raise TypeError(f"not a UUID: {value!r}")
    return match.group(1).lower()


def same_id(a, b) -> bool:
    """Whether two ids are the same UUID, whichever shape each arrived in."""
    return _text(a) == _text(b)
