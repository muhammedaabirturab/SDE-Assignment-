def test_create_valid_user(client):
    response = client.post("/users", json={"name": "Mohit"})
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 1
    assert body["name"] == "Mohit"
    assert "created_at" in body


def test_name_is_trimmed(client):
    response = client.post("/users", json={"name": "  Rahul  "})
    assert response.status_code == 201
    assert response.json()["name"] == "Rahul"


def test_reject_empty_name(client):
    response = client.post("/users", json={"name": ""})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_reject_whitespace_only_name(client):
    assert client.post("/users", json={"name": "   "}).status_code == 422


def test_reject_missing_or_invalid_name(client):
    assert client.post("/users", json={}).status_code == 422
    assert client.post("/users", json={"name": None}).status_code == 422
    assert client.post("/users", json={"name": 123}).status_code == 422
    assert client.post("/users", json={"name": "x" * 101}).status_code == 422


def test_duplicate_name_is_rejected_case_insensitively(client):
    assert client.post("/users", json={"name": "Mohit"}).status_code == 201
    response = client.post("/users", json={"name": "mohit"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"


def test_list_users(client):
    client.post("/users", json={"name": "Mohit"})
    client.post("/users", json={"name": "Rahul"})
    response = client.get("/users")
    assert response.status_code == 200
    assert [u["name"] for u in response.json()] == ["Mohit", "Rahul"]


def test_list_users_on_empty_database(client):
    response = client.get("/users")
    assert response.status_code == 200
    assert response.json() == []


def test_health_check(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_unknown_route_uses_error_envelope(client):
    response = client.get("/nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
