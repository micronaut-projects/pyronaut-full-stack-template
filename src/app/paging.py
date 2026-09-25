"""Pagination helpers.

``Pageable.from(page, size)`` is the natural Micronaut Data call, and ``from`` is a
Python keyword -- so Pyronaut exposes it as ``from_``, which is its general rule for
escaping a Java name that collides with one. No ``getattr`` needed.

The clamping is why this module still exists: a page size arrives from a query
parameter, and a client should not be able to ask for the world.
"""

from micronaut.data.model import Pageable

DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 500


def page_request(page: int = 0, size: int = DEFAULT_PAGE_SIZE) -> Pageable:
    """Build a Pageable, clamping the inputs so a client cannot ask for the world."""
    page = max(0, int(page))
    size = min(max(1, int(size)), MAX_PAGE_SIZE)
    return Pageable.from_(page, size)
