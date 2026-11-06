"""The Alembic migration must build exactly the schema the models describe."""

import warnings
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text

from app.database.base import Base
from tests.conftest import TEST_DATABASE_URL

ROOT = Path(__file__).resolve().parent.parent
EXPECTED_TABLES = {
    "users", "groups", "group_members", "expenses", "expense_splits", "settlements",
}


def _alembic_config() -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL.replace("%", "%%"))
    return config


def _reset(engine) -> None:
    Base.metadata.drop_all(engine)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))


def test_migration_matches_models_and_is_reversible(engine):
    _reset(engine)
    config = _alembic_config()
    try:
        command.upgrade(config, "head")
        assert EXPECTED_TABLES <= set(inspect(engine).get_table_names())

        with engine.connect() as connection, warnings.catch_warnings():
            # SQLite cannot reflect the lower(name) index; PostgreSQL can.
            warnings.simplefilter("ignore")
            diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
        assert diff == []

        command.downgrade(config, "base")
        assert EXPECTED_TABLES.isdisjoint(inspect(engine).get_table_names())
    finally:
        _reset(engine)
