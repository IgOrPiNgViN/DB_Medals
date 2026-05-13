import sys
from pathlib import Path

# Make the server package importable from anywhere pytest is invoked.
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from database import engine, get_db, Base
from main import app


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    """Ensure all tables exist once per test session."""
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def db(create_tables):
    """
    Provide a transactional Session that is rolled back after each test.
    Uses SQLAlchemy 2.0 join_transaction_mode="create_savepoint" so that
    the ORM Session and the outer connection transaction cooperate correctly.
    """
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    trans.rollback()
    conn.close()


@pytest.fixture
def client(db):
    """
    TestClient whose database dependency is overridden to use the
    transactional session supplied by the `db` fixture.
    """
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
