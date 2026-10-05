"""Comparing ids across the Python/Java boundary.

The same UUID reaches Python in two shapes. An entity the route was handed as a
parameter has been converted to the Python dataclass, and its ``id`` is a
``uuid.UUID``. An entity a repository returned is still the Java object, and its
``id`` is a foreign value whose ``str()`` is ``UUID('...')``, not the bare text.

So ``str(a.id) == str(b.id)`` is only right when both sides came the same way,
and wrong without complaint when they did not: the owner of an item is refused
it, and the check that stops a superuser deleting their own account passes.
Compare ids with ``same_id`` instead.
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
