"""Item CRUD and ownership rules."""

from conftest import LOGIN_SUCCESS, sign_in


def _create_item(client, title="A thing", description="Made by a test"):
    response = client.post(
        "/api/v1/items", json={"title": title, "description": description}
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_items_require_authentication(client):
    assert client.get("/api/v1/items").status_code == 401


def test_create_and_read_an_item(superuser_client):
    item = _create_item(superuser_client, title="First item")
    assert item["title"] == "First item"
    assert item["ownerId"]

    fetched = superuser_client.get(f"/api/v1/items/{item['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == item["id"]


def test_list_returns_data_and_count(superuser_client):
    _create_item(superuser_client, title="Listed item")
    response = superuser_client.get("/api/v1/items")
    assert response.status_code == 200
    body = response.json()
    assert "data" in body and "count" in body
    assert body["count"] >= 1
    assert any(item["title"] == "Listed item" for item in body["data"])


def test_update_an_item(superuser_client):
    item = _create_item(superuser_client)
    response = superuser_client.put(
        f"/api/v1/items/{item['id']}", json={"title": "Renamed"}
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Renamed"


def test_delete_an_item(superuser_client):
    item = _create_item(superuser_client)
    assert superuser_client.delete(f"/api/v1/items/{item['id']}").status_code == 200
    assert superuser_client.get(f"/api/v1/items/{item['id']}").status_code == 404


def test_unknown_item_is_not_found(superuser_client):
    missing = "00000000-0000-0000-0000-000000000000"
    assert superuser_client.get(f"/api/v1/items/{missing}").status_code == 404


def test_a_blank_title_is_rejected_with_the_one_error_shape(superuser_client):
    """Validation is declarative, and every failure uses {message, errors}."""
    response = superuser_client.post("/api/v1/items", json={"title": ""})
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["message"] == "Validation failed"
    assert "title" in body["errors"]


def test_a_plain_user_owns_their_items_and_nobody_elses(superuser_client, unique_email):
    """Ownership, for a user who cannot fall back on being a superuser.

    Every other test here signs in as the superuser, who may touch any item, so
    none of them would notice the ownership check refusing the owner.
    """
    theirs = superuser_client.post("/api/v1/items", json={"title": "Not yours"}).json()

    # The same client: signing in again replaces the superuser's session.
    client = superuser_client
    email = unique_email("owner")
    client.post("/api/v1/users/signup", json={"email": email, "password": "a-good-password"})
    assert sign_in(client, email, "a-good-password") == LOGIN_SUCCESS

    mine = client.post("/api/v1/items", json={"title": "Mine"})
    assert mine.status_code == 201, mine.text
    item_id = mine.json()["id"]

    assert client.get(f"/api/v1/items/{item_id}").status_code == 200
    updated = client.put(f"/api/v1/items/{item_id}", json={"title": "Still mine"})
    assert updated.status_code == 200, updated.text
    assert [item["id"] for item in client.get("/api/v1/items").json()["data"]] == [item_id]

    assert client.get(f"/api/v1/items/{theirs['id']}").status_code == 403
    assert client.delete(f"/api/v1/items/{theirs['id']}").status_code == 403

    assert client.delete(f"/api/v1/items/{item_id}").status_code == 200

