import pytest
from sqlalchemy.exc import IntegrityError

from app.models import GroupMember


def test_create_group(client):
    response = client.post("/groups", json={"name": "Goa Trip"})
    assert response.status_code == 201
    assert response.json()["id"] == 1
    assert response.json()["name"] == "Goa Trip"


@pytest.mark.parametrize("payload", [{"name": ""}, {"name": "   "}, {}])
def test_reject_invalid_group_name(client, payload):
    assert client.post("/groups", json=payload).status_code == 422


def test_add_valid_user_to_group(api, client):
    user = api.user("Mohit")
    group = api.group()
    response = client.post(f"/groups/{group}/members", json={"user_id": user})
    assert response.status_code == 201
    body = response.json()
    assert (body["group_id"], body["user_id"], body["name"]) == (group, user, "Mohit")


def test_reject_unknown_user(api, client):
    group = api.group()
    response = client.post(f"/groups/{group}/members", json={"user_id": 999})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_reject_unknown_group(api, client):
    user = api.user("Mohit")
    response = client.post("/groups/999/members", json={"user_id": user})
    assert response.status_code == 404


def test_prevent_duplicate_membership(api, client):
    user = api.user("Mohit")
    group = api.group(members=(user,))
    response = client.post(f"/groups/{group}/members", json={"user_id": user})
    assert response.status_code == 409
    assert len(client.get(f"/groups/{group}/members").json()) == 1


def test_same_user_can_join_different_groups(api, client):
    user = api.user("Mohit")
    first, second = api.group("A", (user,)), api.group("B")
    assert client.post(f"/groups/{second}/members", json={"user_id": user}).status_code == 201
    assert first != second


def test_group_id_in_body_must_match_url(api, client):
    user = api.user("Mohit")
    group, other = api.group("A"), api.group("B")
    mismatch = client.post(f"/groups/{group}/members", json={"group_id": other, "user_id": user})
    assert mismatch.status_code == 422
    match = client.post(f"/groups/{group}/members", json={"group_id": group, "user_id": user})
    assert match.status_code == 201


def test_list_group_members(api, client):
    mohit, rahul = api.user("Mohit"), api.user("Rahul")
    group = api.group(members=(mohit, rahul))
    response = client.get(f"/groups/{group}/members")
    assert response.status_code == 200
    assert [m["name"] for m in response.json()] == ["Mohit", "Rahul"]


def test_list_members_of_empty_group(api, client):
    group = api.group()
    response = client.get(f"/groups/{group}/members")
    assert response.status_code == 200
    assert response.json() == []


def test_list_members_of_unknown_group(client):
    assert client.get("/groups/999/members").status_code == 404


def test_database_itself_rejects_duplicate_membership(api, db):
    user = api.user("Mohit")
    group = api.group(members=(user,))
    db.add(GroupMember(group_id=group, user_id=user))
    with pytest.raises(IntegrityError):
        db.commit()


def test_database_itself_rejects_dangling_references(api, db):
    group = api.group()
    db.add(GroupMember(group_id=group, user_id=12345))
    with pytest.raises(IntegrityError):
        db.commit()
