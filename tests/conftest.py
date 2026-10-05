"""Shared pytest fixtures.

MySQL is supplied by Micronaut Test Resources, which starts a container on
demand — there is no Docker Compose file to run first, and nothing to clean up
afterwards.

Test isolation note
-------------------
``transactional`` is off deliberately.

It would not help here. Every test in this suite goes through an HTTP client, so
the writes happen on the embedded server's own threads in its own transactions,
and rolling back the *test's* transaction leaves them in place. With a reusable
Test Resources server the database outlives the run as well.

So isolation is arranged by hand and stays that way. Tests never assume an empty
table and never assert on a global row count; anything that has to be unique
comes from the ``unique_email`` fixture. A test that called a service or
repository directly could use ``transactional`` instead.
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

# Where Micronaut Security sends the browser after a login attempt; see
# [micronaut.security.redirect] in config/application.toml.
LOGIN_SUCCESS = "/"
LOGIN_FAILURE = "/login?error=true"

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


def sign_in(client, email, password):
    """Post the login form the way a browser does, and return where it redirects to.

    The login endpoint answers 303 whether or not the credentials were right, so
    the redirect is not followed: its `Location` is the answer. Following it would
    end on a rendered page and a 200 either way.
    """
    response = client.post(
        "/api/v1/login",
        data={"username": email, "password": password},
        allow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return response.headers.get("Location")


@pytest.fixture
def superuser_client(client):
    """A client that has signed in as the bootstrapped superuser.

    Authentication rides an HttpOnly cookie, so the session persists on the
    client itself and no token has to be threaded through each call.
    """
    assert sign_in(client, SUPERUSER_EMAIL, SUPERUSER_PASSWORD) == LOGIN_SUCCESS
    return client


@pytest.fixture
def unique_email():
    """An address no other test has used, so tests never collide on the unique index."""
    return lambda prefix="user": f"{prefix}-{uuid.uuid4().hex[:12]}@example.com"
