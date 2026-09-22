"""Authentication and password recovery."""

from conftest import SUPERUSER_EMAIL, SUPERUSER_PASSWORD


def test_superuser_is_created_on_startup(client):
    """The bootstrap listener seeds the first superuser, so login works cold."""
    response = client.post(
        "/api/v1/login",
        json={"username": SUPERUSER_EMAIL, "password": SUPERUSER_PASSWORD},
    )
    assert response.status_code == 200, response.text


def test_login_rejects_a_wrong_password(client):
    response = client.post(
        "/api/v1/login",
        json={"username": SUPERUSER_EMAIL, "password": "not-the-password"},
    )
    assert response.status_code == 401


def test_login_does_not_distinguish_unknown_users(client):
    """An unknown email fails exactly like a wrong password.

    Anything else turns the login endpoint into an account-enumeration oracle.
    """
    unknown = client.post(
        "/api/v1/login",
        json={"username": "nobody@example.com", "password": "whatever-123"},
    )
    wrong_password = client.post(
        "/api/v1/login",
        json={"username": SUPERUSER_EMAIL, "password": "whatever-123"},
    )
    assert unknown.status_code == wrong_password.status_code == 401


def test_authenticated_routes_require_a_session(client):
    assert client.get("/api/v1/users/me").status_code == 401


def test_test_token_returns_the_authenticated_user(superuser_client):
    response = superuser_client.get("/api/v1/login/test-token")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["email"] == SUPERUSER_EMAIL
    assert body["isSuperuser"] is True
    # The public projection must never leak the hash.
    assert "hashedPassword" not in body


def test_password_recovery_answers_the_same_for_unknown_addresses(client):
    """Constant response, so recovery cannot be used to enumerate accounts."""
    known = client.post(f"/api/v1/password-recovery/{SUPERUSER_EMAIL}")
    unknown = client.post("/api/v1/password-recovery/nobody@example.com")
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()


def test_reset_password_rejects_a_forged_token(client):
    response = client.post(
        "/api/v1/reset-password",
        json={"token": "forged.signature", "newPassword": "brand-new-password"},
    )
    assert response.status_code == 400
    assert response.json()["message"] == "Invalid token"
