from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_current_admin, get_current_user, get_current_user_full_access
from app.main import app


@dataclass
class StubUser:
    id: str = "user-1"
    email: str = "user@example.com"
    is_admin: bool = False
    is_active: bool = True
    password_hash: str = "hashed-password"
    temp_password_hash: str | None = None
    temp_password_expires_at: object | None = None


@pytest.fixture
def stub_user() -> StubUser:
    return StubUser()


@pytest.fixture
def admin_user() -> StubUser:
    return StubUser(id="admin-1", email="admin@example.com", is_admin=True)


@pytest.fixture
def client(stub_user: StubUser):
    def _db_override():
        yield object()

    app.dependency_overrides[get_db] = _db_override
    app.dependency_overrides[get_current_user] = lambda: stub_user
    app.dependency_overrides[get_current_user_full_access] = lambda: stub_user
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def admin_client(admin_user: StubUser):
    def _db_override():
        yield object()

    app.dependency_overrides[get_db] = _db_override
    app.dependency_overrides[get_current_user] = lambda: admin_user
    app.dependency_overrides[get_current_user_full_access] = lambda: admin_user
    app.dependency_overrides[get_current_admin] = lambda: admin_user
    yield TestClient(app)
    app.dependency_overrides.clear()
