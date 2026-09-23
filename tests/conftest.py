"""Shared pytest fixtures.

MySQL is supplied by Micronaut Test Resources, which starts a container on
demand — there is no Docker Compose file to run first, and nothing to clean up
afterwards.

Test isolation note
-------------------
``transactional``, ``rollback`` and ``rebuild_context`` are accepted by the
pytest integration and have no effect — measured, not assumed: a row written in
one test is still there in the next
(https://github.com/micronaut-projects/pyronaut/issues/174).

So isolation here is arranged by hand. Tests never assume an empty table and
never assert on a global row count; anything that has to be unique comes from
the ``unique_email`` fixture. When #174 is fixed, the honest simplification is
to make ``application_context`` transactional and delete those precautions --
but note that a rolled-back test transaction would not cover work done by the
embedded server on its own threads, so the HTTP-level tests would still need
``unique_email``.
"""

import uuid

import pytest
from org.testcontainers.containers import GenericContainer
from org.testcontainers.containers.wait.strategy import Wait
from org.testcontainers.utility import DockerImageName
from pyronaut import requests
from pyronaut.test import MicronautTest, micronaut_test_fixture

SUPERUSER_EMAIL = "admin@example.com"
SUPERUSER_PASSWORD = "testpassword123"

MAILPIT_IMAGE = "axllent/mailpit"
MAILPIT_SMTP_PORT = 1025
MAILPIT_HTTP_PORT = 8025


@pytest.fixture(scope="session")
def mailpit():
    """Mailpit, started once for the whole session.

    MySQL comes from Micronaut Test Resources, which has a module for it.
    Mailpit does not, so it is started here with Testcontainers — driven from
    Python, against the Java Testcontainers API. Either way there is no Docker
    Compose file: the test that needs a service starts it.

    Yields the properties the application needs to reach it.
    """
    container = (
        GenericContainer(DockerImageName.parse(MAILPIT_IMAGE))
        .withExposedPorts(MAILPIT_SMTP_PORT, MAILPIT_HTTP_PORT)
        .waitingFor(Wait.forHttp("/").forPort(MAILPIT_HTTP_PORT))
    )
    container.start()
    host = str(container.getHost())
    try:
        yield {
            "app.smtp-host": host,
            "app.smtp-port": str(container.getMappedPort(MAILPIT_SMTP_PORT)),
            "micronaut.http.services.mailpit.url": (
                f"http://{host}:{container.getMappedPort(MAILPIT_HTTP_PORT)}"
            ),
        }
    finally:
        container.stop()


@pytest.fixture
def application_context(request, mailpit):
    """A running application, with MySQL from Test Resources and Mailpit alongside."""
    fixture = micronaut_test_fixture(
        request,
        MicronautTest(environments=["test"], transactional=False, properties=mailpit),
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
