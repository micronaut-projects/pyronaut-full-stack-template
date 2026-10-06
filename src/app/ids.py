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
"""

import re

_UUID = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", re.IGNORECASE)


def _text(value) -> str | None:
    match = _UUID.search(str(value))
    return match.group(0).lower() if match else None


def same_id(a, b) -> bool:
    """Whether two ids are the same UUID, whichever shape each arrived in."""
    left = _text(a)
    return left is not None and left == _text(b)
