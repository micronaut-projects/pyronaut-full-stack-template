"""Pagination helpers.

``Pageable.from(page, size)`` is the natural Micronaut Data call, and ``from`` is a
Python keyword -- so Pyronaut exposes it as ``from_``.
"""

from micronaut.data.model import Pageable

DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 500


def page_request(page: int = 0, size: int = DEFAULT_PAGE_SIZE) -> Pageable:
    """Build a Pageable, clamping the inputs so a client cannot ask for the world."""
    page = max(0, int(page))
    size = min(max(1, int(size)), MAX_PAGE_SIZE)
    return Pageable.from_(page, size)
