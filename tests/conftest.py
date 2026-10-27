import os

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.database import get_session
from app.main import app

TEST_URL = os.getenv(
    "TEST_DATABASE_URL", "postgresql+psycopg://ledger:ledger@localhost:5434/ledger_test"
)


@pytest.fixture(scope="session")
def session_factory():
    # Cleanup is destructive: only accept an explicitly named test database.
    database = make_url(TEST_URL).database
    if not database or not database.endswith("_test"):
        pytest.fail("TEST_DATABASE_URL database name must end with _test")
    engine = create_engine(TEST_URL, pool_size=12, max_overflow=12)
    from app.config import get_settings

    settings = get_settings()
    previous = settings.database_url
    settings.database_url = TEST_URL
    try:
        command.upgrade(Config("alembic.ini"), "head")
    finally:
        settings.database_url = previous
    yield sessionmaker(engine, expire_on_commit=False)
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_database(session_factory):
    with session_factory() as session, session.begin():
        session.execute(text("TRUNCATE transactions, transfers, accounts"))


@pytest.fixture
def client(session_factory):
    def override():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def account(client):
    return client.post("/accounts", json={"name": "Alice"}).json()["id"]


def post_entry(client, account, kind="credit", amount="100.00", reference="ref-1"):
    return client.post(
        f"/accounts/{account}/transactions",
        json={"type": kind, "amount": amount, "reference_id": reference},
    )
