"""User management, registration and authorisation rules."""

from datetime import datetime

from conftest import LOGIN_SUCCESS, SUPERUSER_EMAIL, sign_in


def test_signup_creates_an_active_non_superuser(client, unique_email):
    email = unique_email("signup")
    response = client.post(
        "/api/v1/users/signup",
        json={"email": email, "password": "a-good-password", "fullName": "New Person"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["email"] == email
    assert body["isActive"] is True
    # Open registration must never be able to mint an administrator.
    assert body["isSuperuser"] is False


def test_signup_rejects_a_duplicate_email(client, unique_email):
    email = unique_email("dupe")
    payload = {"email": email, "password": "a-good-password"}
    assert client.post("/api/v1/users/signup", json=payload).status_code == 201
    conflict = client.post("/api/v1/users/signup", json=payload)
    assert conflict.status_code == 409, conflict.text
    assert "email" in conflict.json()["errors"]


def test_signup_rejects_a_short_password(client, unique_email):
    response = client.post(
        "/api/v1/users/signup",
        json={"email": unique_email("short"), "password": "tiny"},
    )
    assert response.status_code == 422, response.text
    assert "password" in response.json()["errors"]


def test_signup_rejects_a_malformed_email(client):
    response = client.post(
        "/api/v1/users/signup",
        json={"email": "not-an-email", "password": "a-good-password"},
    )
    assert response.status_code == 422, response.text
    assert "email" in response.json()["errors"]


def test_a_new_user_can_sign_in(client, unique_email):
    email = unique_email("signin")
    client.post(
        "/api/v1/users/signup", json={"email": email, "password": "a-good-password"}
    )
    assert sign_in(client, email, "a-good-password") == LOGIN_SUCCESS


def test_read_me_returns_the_signed_in_user(superuser_client):
    body = superuser_client.get("/api/v1/users/me").json()
    assert body["email"] == SUPERUSER_EMAIL
    assert "hashedPassword" not in body


def test_update_me_changes_the_full_name(superuser_client):
    response = superuser_client.patch(
        "/api/v1/users/me", json={"fullName": "Renamed Administrator"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["fullName"] == "Renamed Administrator"


def test_password_change_requires_the_current_password(superuser_client):
    response = superuser_client.patch(
        "/api/v1/users/me/password",
        json={"currentPassword": "wrong-password", "newPassword": "another-password"},
    )
    assert response.status_code == 400
    assert response.json()["message"] == "Incorrect password"


def test_a_session_outliving_its_account_cannot_act_as_it(client, unique_email):
    """The cookie still verifies after the account is gone.

    Validating a JWT does not touch the database, so the token stays valid until
    it expires. A route that needs the user as an entity then has nothing to
    bind, and answers 400 rather than failing with a 500 or acting on a `None`.
    """
    email = unique_email("gone")
    client.post(
        "/api/v1/users/signup", json={"email": email, "password": "a-good-password"}
    )
    assert sign_in(client, email, "a-good-password") == LOGIN_SUCCESS
    assert client.delete("/api/v1/users/me").status_code == 200

    assert client.get("/api/v1/users/me").status_code == 400
    assert client.get("/api/v1/login/test-token").status_code == 400


def test_a_plain_user_may_read_their_own_record_and_no_other(superuser_client, unique_email):
    admin_id = superuser_client.get("/api/v1/users/me").json()["id"]

    # The same client: signing in again replaces the superuser's session.
    client = superuser_client
    email = unique_email("self")
    created = client.post(
        "/api/v1/users/signup", json={"email": email, "password": "a-good-password"}
    ).json()
    assert sign_in(client, email, "a-good-password") == LOGIN_SUCCESS

    own = client.get(f"/api/v1/users/{created['id']}")
    assert own.status_code == 200, own.text
    assert own.json()["email"] == email
    assert client.get(f"/api/v1/users/{admin_id}").status_code == 403


def test_listing_users_requires_superuser(client, unique_email):
    """A plain user must not be able to read the user directory."""
    email = unique_email("plain")
    client.post(
        "/api/v1/users/signup", json={"email": email, "password": "a-good-password"}
    )
    assert sign_in(client, email, "a-good-password") == LOGIN_SUCCESS
    assert client.get("/api/v1/users").status_code == 403


def test_the_admin_page_sends_a_plain_user_to_the_forbidden_page(client, unique_email):
    """A signed-in browser that is not allowed is told so.

    A signed-out one is sent to the login page; this one is already past it.
    """
    email = unique_email("plain")
    client.post(
        "/api/v1/users/signup", json={"email": email, "password": "a-good-password"}
    )
    assert sign_in(client, email, "a-good-password") == LOGIN_SUCCESS
    # What a browser sends when navigating. `text/html` alone would not do: the
    # page routes do not declare that they produce it, so it would match no route.
    browser = {"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
    response = client.get("/admin", headers=browser, allow_redirects=False)
    assert response.status_code == 303
    assert response.headers.get("Location") == "/forbidden"

    page = client.get("/forbidden", headers=browser, allow_redirects=False)
    assert page.status_code == 200, page.text
    assert "You do not have permission to see this page." in page.text


def test_superuser_can_list_users(superuser_client):
    response = superuser_client.get("/api/v1/users")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["count"] >= 1
    assert any(user["email"] == SUPERUSER_EMAIL for user in body["data"])


def test_a_superuser_may_not_delete_themselves(superuser_client):
    me = superuser_client.get("/api/v1/users/me").json()
    response = superuser_client.delete(f"/api/v1/users/{me['id']}")
    assert response.status_code == 400
    assert "delete themselves" in response.json()["message"]

def test_created_at_is_iso_8601(superuser_client):
    """The published timestamp must be parseable by an ordinary client.

    Worth pinning because it was not: the projection used to be str() on a
    coerced datetime, which yields '2026-09-27 10:25:36.029085+00:00' -- a space
    where ISO-8601 wants a T, which Date.parse is not obliged to accept. The
    bean mapper in app/mappers.py converts the Instant properly.
    """
    created_at = superuser_client.get("/api/v1/users/me").json()["createdAt"]
    assert "T" in created_at, created_at
    datetime.fromisoformat(created_at)  # raises if it is not ISO-8601
