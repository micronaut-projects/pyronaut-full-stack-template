"""Transactional email, asserted on the message Mailpit actually received.

The upstream FastAPI template never checks the contents of the mail it sends.
Here the bodies are React components rendered on GraalJS, so what arrives is
worth asserting: `micronaut-email-mailpit-http-client` reads the captured
message back out of Mailpit's API.
"""

import pytest
from conftest import LOGIN_FAILURE, LOGIN_SUCCESS, SUPERUSER_EMAIL, sign_in

MAILPIT_CLIENT = "io.micronaut.email.mailpit.client.MailpitClient"


@pytest.fixture
def mailpit_client(application_context):
    return application_context[MAILPIT_CLIENT]


def test_password_recovery_sends_a_rendered_email(client, mailpit_client):
    response = client.post(f"/api/v1/password-recovery/{SUPERUSER_EMAIL}")
    assert response.status_code == 200, response.text

    message = mailpit_client.getMessage("latest")
    assert message is not None

    recipients = [str(address.address()) for address in message.to()]
    assert SUPERUSER_EMAIL in recipients
    assert "Password recovery" in str(message.subject())

    html = str(message.html())
    # Rendered by the React component in frontend/emails/ResetPasswordEmail.jsx.
    assert "Password recovery" in html
    assert "/reset-password?token=" in html
    # An email must carry no external stylesheet.
    assert "<link" not in html


def test_the_email_carries_no_hydration_payload(client, mailpit_client):
    """An email is not a browser page: it should carry no scripts and no model."""
    assert client.post(f"/api/v1/password-recovery/{SUPERUSER_EMAIL}").status_code == 200
    html = str(mailpit_client.getMessage("latest").html())
    assert "<script" not in html
    assert "rootProps" not in html


def test_the_recovery_token_in_the_email_actually_works(client, mailpit_client):
    """End to end: request a reset, read the link out of the delivered mail, use it."""
    email = f"reset-{__import__('uuid').uuid4().hex[:10]}@example.com"
    original = "original-password"
    assert (
        client.post(
            "/api/v1/users/signup", json={"email": email, "password": original}
        ).status_code
        == 201
    )

    assert client.post(f"/api/v1/password-recovery/{email}").status_code == 200

    html = str(mailpit_client.getMessage("latest").html())
    token = html.split("/reset-password?token=")[1].split('"')[0]

    new_password = "a-brand-new-password"
    reset = client.post(
        "/api/v1/reset-password", json={"token": token, "newPassword": new_password}
    )
    assert reset.status_code == 200, reset.text

    # The new password works and the old one does not.
    assert sign_in(client, email, new_password) == LOGIN_SUCCESS
    assert sign_in(client, email, original) == LOGIN_FAILURE


def test_test_email_requires_superuser(client):
    response = client.post("/api/v1/utils/test-email?emailTo=someone@example.com")
    assert response.status_code == 401
