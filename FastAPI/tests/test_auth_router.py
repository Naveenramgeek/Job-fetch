from datetime import datetime, timedelta, timezone

import app.routers.auth as auth_mod


class _User:
    def __init__(
        self,
        *,
        user_id="u1",
        email="u@example.com",
        is_active=True,
        is_admin=False,
        password_hash="hashed",
        temp_password_hash=None,
        temp_password_expires_at=None,
    ):
        self.id = user_id
        self.email = email
        self.is_active = is_active
        self.is_admin = is_admin
        self.password_hash = password_hash
        self.temp_password_hash = temp_password_hash
        self.temp_password_expires_at = temp_password_expires_at


def test_register_rejects_existing_email(monkeypatch, client):
    monkeypatch.setattr(auth_mod, "get_by_email", lambda db, email: _User())
    resp = client.post("/auth/register", json={"email": "u@example.com", "password": "password123", "confirm_password": "password123"})
    assert resp.status_code == 400
    assert "already" in resp.json()["detail"].lower()


def test_register_success(monkeypatch, client):
    monkeypatch.setattr(auth_mod, "get_by_email", lambda db, email: None)
    monkeypatch.setattr(auth_mod, "create_user", lambda db, email, pw: _User(user_id="new1", email=email))
    monkeypatch.setattr(auth_mod, "get_latest_by_user", lambda db, uid: None)
    monkeypatch.setattr(auth_mod, "create_access_token", lambda uid: "token-1")
    resp = client.post("/auth/register", json={"email": "new@example.com", "password": "password123", "confirm_password": "password123"})
    assert resp.status_code == 200
    assert resp.json()["access_token"] == "token-1"


def test_login_invalid_credentials(monkeypatch, client):
    monkeypatch.setattr(auth_mod, "get_by_email", lambda db, email: None)
    resp = client.post("/auth/login", json={"email": "x@example.com", "password": "bad"})
    assert resp.status_code == 401


def test_login_disabled_user(monkeypatch, client):
    monkeypatch.setattr(auth_mod, "get_by_email", lambda db, email: _User(is_active=False))
    resp = client.post("/auth/login", json={"email": "x@example.com", "password": "bad"})
    assert resp.status_code == 403


def test_login_temp_password_path(monkeypatch, client):
    exp = datetime.now(timezone.utc) + timedelta(minutes=5)
    user = _User(temp_password_hash="tmphash", temp_password_expires_at=exp)
    monkeypatch.setattr(auth_mod, "get_by_email", lambda db, email: user)
    monkeypatch.setattr(auth_mod, "verify_password", lambda plain, hashed: hashed == "tmphash")
    monkeypatch.setattr(auth_mod, "get_latest_by_user", lambda db, uid: object())
    monkeypatch.setattr(auth_mod, "create_access_token", lambda uid: "temp-token")
    resp = client.post("/auth/login", json={"email": "u@example.com", "password": "anything"})
    assert resp.status_code == 200
    assert resp.json()["access_token"] == "temp-token"


def test_login_normal_password_success(monkeypatch, client):
    user = _User(temp_password_hash=None, temp_password_expires_at=None, password_hash="normal-hash")
    monkeypatch.setattr(auth_mod, "get_by_email", lambda db, email: user)
    monkeypatch.setattr(auth_mod, "verify_password", lambda plain, hashed: hashed == "normal-hash")
    monkeypatch.setattr(auth_mod, "get_latest_by_user", lambda db, uid: None)
    monkeypatch.setattr(auth_mod, "create_access_token", lambda uid: "normal-token")
    resp = client.post("/auth/login", json={"email": "u@example.com", "password": "good"})
    assert resp.status_code == 200
    assert resp.json()["access_token"] == "normal-token"


def test_forgot_password_generic_response_for_unknown(monkeypatch, client):
    monkeypatch.setattr(auth_mod, "get_by_email", lambda db, email: None)
    resp = client.post("/auth/forgot-password", json={"email": "none@example.com"})
    assert resp.status_code == 200
    assert "If an account exists" in resp.json()["message"]


def test_forgot_password_can_expose_temp_when_enabled(monkeypatch, client):
    user = _User()
    monkeypatch.setattr(auth_mod, "get_by_email", lambda db, email: user)
    monkeypatch.setattr(auth_mod, "generate_temp_password", lambda: "TEMP1234")
    monkeypatch.setattr(auth_mod, "hash_password", lambda x: "hashed-temp")
    monkeypatch.setattr(auth_mod, "set_temp_password", lambda db, uid, h, e: user)
    monkeypatch.setattr(auth_mod.settings, "expose_temp_password_in_response", True)
    resp = client.post("/auth/forgot-password", json={"email": "u@example.com"})
    assert resp.status_code == 200
    assert resp.json()["temp_password"] == "TEMP1234"


def test_change_password_requires_temp_mode(monkeypatch, client):
    monkeypatch.setattr(auth_mod, "is_temp_password_mode", lambda u: False)
    resp = client.post(
        "/auth/change-password",
        json={"new_password": "newpassword1", "confirm_password": "newpassword1"},
    )
    assert resp.status_code == 400


def test_change_password_success(monkeypatch, client):
    user = _User(user_id="u1", email="u@example.com", temp_password_hash="tmp", temp_password_expires_at=datetime.now(timezone.utc))
    monkeypatch.setattr(auth_mod, "is_temp_password_mode", lambda u: True)
    monkeypatch.setattr(auth_mod, "hash_password", lambda p: "new-hash")
    monkeypatch.setattr(auth_mod, "update_user", lambda db, uid, **kwargs: user)
    monkeypatch.setattr(auth_mod, "clear_temp_password", lambda db, uid: user)
    monkeypatch.setattr(auth_mod, "get_by_id", lambda db, uid: user)
    monkeypatch.setattr(auth_mod, "get_latest_by_user", lambda db, uid: None)
    monkeypatch.setattr(auth_mod, "create_access_token", lambda uid: "tok-new")
    monkeypatch.setattr(auth_mod, "get_current_user", lambda: user)
    resp = client.post(
        "/auth/change-password",
        json={"new_password": "newpassword1", "confirm_password": "newpassword1"},
    )
    assert resp.status_code == 200
    assert resp.json()["access_token"] == "tok-new"


def test_get_me(monkeypatch, client):
    monkeypatch.setattr(auth_mod, "get_latest_by_user", lambda db, uid: object())
    resp = client.get("/auth/me")
    assert resp.status_code == 200
    assert resp.json()["has_resume"] is True


def test_update_profile_email_conflict(monkeypatch, client):
    monkeypatch.setattr(auth_mod, "get_by_email", lambda db, email: _User(user_id="other"))
    resp = client.patch("/auth/me", json={"email": "other@example.com"})
    assert resp.status_code == 400


def test_update_profile_wrong_current_password(monkeypatch, client):
    monkeypatch.setattr(auth_mod, "get_by_email", lambda db, email: None)
    monkeypatch.setattr(auth_mod, "verify_password", lambda plain, hashed: False)
    resp = client.patch(
        "/auth/me",
        json={
            "current_password": "wrong",
            "new_password": "newpassword1",
            "confirm_new_password": "newpassword1",
        },
    )
    assert resp.status_code == 401


def test_update_profile_success(monkeypatch, client):
    current = _User(user_id="user-1", email="user@example.com", password_hash="old-hash")
    updated = _User(user_id="user-1", email="next@example.com", password_hash="new-hash")
    monkeypatch.setattr(auth_mod, "get_by_email", lambda db, email: None)
    monkeypatch.setattr(auth_mod, "update_user", lambda db, uid, **kwargs: updated)
    monkeypatch.setattr(auth_mod, "verify_password", lambda plain, hashed: True)
    monkeypatch.setattr(auth_mod, "hash_password", lambda p: "new-hash")
    monkeypatch.setattr(auth_mod, "get_by_id", lambda db, uid: updated)
    monkeypatch.setattr(auth_mod, "get_latest_by_user", lambda db, uid: None)
    monkeypatch.setattr(auth_mod, "get_current_user_full_access", lambda: current)
    resp = client.patch(
        "/auth/me",
        json={
            "email": "next@example.com",
            "current_password": "oldpassword",
            "new_password": "newpassword1",
            "confirm_new_password": "newpassword1",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == "next@example.com"


def test_delete_account_success(monkeypatch, client):
    monkeypatch.setattr(auth_mod, "delete_user", lambda db, uid: True)
    resp = client.delete("/auth/account")
    assert resp.status_code == 200
    assert "deleted" in resp.json()["message"].lower()


def test_register_returns_500_on_unexpected_failure(monkeypatch, client):
    monkeypatch.setattr(auth_mod, "get_by_email", lambda db, email: None)
    monkeypatch.setattr(auth_mod, "create_user", lambda db, email, pw: (_ for _ in ()).throw(RuntimeError("db")))
    resp = client.post("/auth/register", json={"email": "x@example.com", "password": "password123", "confirm_password": "password123"})
    assert resp.status_code == 500


def test_forgot_password_returns_500_on_failure(monkeypatch, client):
    monkeypatch.setattr(auth_mod, "get_by_email", lambda db, email: _User())
    monkeypatch.setattr(auth_mod, "generate_temp_password", lambda: "TEMP1234")
    monkeypatch.setattr(auth_mod, "hash_password", lambda x: "hashed-temp")
    monkeypatch.setattr(auth_mod, "set_temp_password", lambda db, uid, h, e: (_ for _ in ()).throw(RuntimeError("db")))
    resp = client.post("/auth/forgot-password", json={"email": "u@example.com"})
    assert resp.status_code == 500


def test_change_password_returns_500_on_failure(monkeypatch, client):
    monkeypatch.setattr(auth_mod, "is_temp_password_mode", lambda u: True)
    monkeypatch.setattr(auth_mod, "update_user", lambda db, uid, **kwargs: (_ for _ in ()).throw(RuntimeError("db")))
    resp = client.post(
        "/auth/change-password",
        json={"new_password": "newpassword1", "confirm_password": "newpassword1"},
    )
    assert resp.status_code == 500


def test_update_profile_returns_500_on_failure(monkeypatch, client):
    monkeypatch.setattr(auth_mod, "get_by_email", lambda db, email: None)
    monkeypatch.setattr(auth_mod, "update_user", lambda db, uid, **kwargs: (_ for _ in ()).throw(RuntimeError("db")))
    resp = client.patch("/auth/me", json={"email": "next@example.com"})
    assert resp.status_code == 500


def test_delete_account_returns_500_on_failure(monkeypatch, client):
    monkeypatch.setattr(auth_mod, "delete_user", lambda db, uid: (_ for _ in ()).throw(RuntimeError("db")))
    resp = client.delete("/auth/account")
    assert resp.status_code == 500
