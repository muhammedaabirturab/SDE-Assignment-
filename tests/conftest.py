"""Shared test fixtures.

By default the tests run on a throw-away SQLite file so they work anywhere.
Set TEST_DATABASE_URL to an EMPTY PostgreSQL database to run the very same
suite against PostgreSQL (tables are dropped and recreated for every test).
"""

import os
import tempfile
from pathlib import Path

import pytest

_sqlite_dir = tempfile.mkdtemp(prefix="expense_tests_")
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL") or (
    f"sqlite:///{Path(_sqlite_dir, 'test.db').as_posix()}"
)
# The app refuses to start without DATABASE_URL; point it at the test database.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import app.models  # noqa: E402,F401
from app.database.base import Base  # noqa: E402
from app.database.connection import build_engine, get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def engine():
    engine = build_engine(TEST_DATABASE_URL)
    yield engine
    engine.dispose()


@pytest.fixture()
def session_factory(engine):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.drop_all(engine)


@pytest.fixture()
def db(session_factory):
    """A direct database session, for tests that poke at the schema itself."""
    with session_factory() as session:
        yield session


@pytest.fixture()
def client(session_factory):
    def _get_db():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db
    # raise_server_exceptions=False so 500 handlers can be asserted on.
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class Api:
    """Tiny helper that makes the tests read like the scenarios they describe."""

    def __init__(self, client: TestClient) -> None:
        self.client = client

    def user(self, name: str) -> int:
        response = self.client.post("/users", json={"name": name})
        assert response.status_code == 201, response.text
        return response.json()["id"]

    def group(self, name: str = "Goa Trip", members: tuple[int, ...] = ()) -> int:
        response = self.client.post("/groups", json={"name": name})
        assert response.status_code == 201, response.text
        group_id = response.json()["id"]
        for user_id in members:
            added = self.client.post(f"/groups/{group_id}/members", json={"user_id": user_id})
            assert added.status_code == 201, added.text
        return group_id

    def expense(self, group_id: int, paid_by: int, amount, description: str = "Dinner", **extra):
        body = {"group_id": group_id, "paid_by": paid_by, "amount": amount,
                "description": description, **extra}
        return self.client.post("/expenses", json=body)

    def settle(self, group_id: int, paid_by: int, paid_to: int, amount, **extra):
        body = {"group_id": group_id, "paid_by": paid_by, "paid_to": paid_to,
                "amount": amount, **extra}
        return self.client.post("/settlements", json=body)

    def balances(self, group_id: int | None = None):
        params = {} if group_id is None else {"group_id": group_id}
        response = self.client.get("/balances", params=params)
        assert response.status_code == 200, response.text
        return response.json()

    def plan(self, group_id: int):
        response = self.client.get(f"/groups/{group_id}/settlements/suggestions")
        assert response.status_code == 200, response.text
        return response.json()


@pytest.fixture()
def api(client) -> Api:
    return Api(client)


@pytest.fixture()
def trip(api):
    """The assignment's scenario: Mohit, Rahul and Ankit in the Goa Trip group."""
    mohit, rahul, ankit = api.user("Mohit"), api.user("Rahul"), api.user("Ankit")
    group = api.group("Goa Trip", (mohit, rahul, ankit))
    return {"group": group, "mohit": mohit, "rahul": rahul, "ankit": ankit}
