"""Shared pytest fixtures.

MySQL is supplied by Micronaut Test Resources, which starts a container on
demand — there is no Docker Compose file to run first, and nothing to clean up
afterwards.

Test isolation note
-------------------
Pyronaut's pytest integration does not currently implement Micronaut Test's
per-test transaction lifecycle: ``transactional``, ``rollback`` and
``rebuild_context`` are accepted but have no effect. Until that is fixed
upstream, tests clean up after themselves through the ``clean_db`` fixture
below. When the upstream fix lands this fixture and its uses should be deleted.

Tracking: https://github.com/micronaut-projects/pyronaut/issues (see PLAN.md §9.1)
"""

import uuid

import pytest
from pyronaut import requests
from pyronaut.test import MicronautTest, micronaut_test_fixture

SUPERUSER_EMAIL = "admin@example.com"
SUPERUSER_PASSWORD = "testpassword123"


@pytest.fixture
def application_context(request):
    """A running application, with MySQL from Test Resources."""
    fixture = micronaut_test_fixture(
        request,
        MicronautTest(environments=["test"], transactional=False),
    )
    yield fixture
    fixture.stop()


@pytest.fixture
def client(application_context):
    """An HTTP client bound to the embedded server, so relative URLs work."""
    return requests.with_context(application_context)


@pytest.fixture
def superuser_client(client):
    """A client that has signed in as the bootstrapped superuser.

    Authentication rides an HttpOnly cookie, so the session persists on the
    client itself and no token has to be threaded through each call.
    """
    response = client.post(
        "/api/v1/login",
        json={"username": SUPERUSER_EMAIL, "password": SUPERUSER_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return client


@pytest.fixture
def unique_email():
    """An address no other test has used, so tests never collide on the unique index."""
    return lambda prefix="user": f"{prefix}-{uuid.uuid4().hex[:12]}@example.com"
