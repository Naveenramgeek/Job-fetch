import pytest
from fastapi import HTTPException

import app.dependencies as deps


class _Creds:
    def __init__(self, token: str):
        self.credentials = token


class _User:
    def __init__(self, user_id="u1", is_admin=False):
        self.id = user_id
        self.is_admin = is_admin


def test_get_current_user_missing_credentials():
    with pytest.raises(HTTPException) as ex:
        deps.get_current_user(db=object(), credentials=None)
    assert ex.value.status_code == 401


def test_get_current_user_invalid_token(monkeypatch):
    monkeypatch.setattr(deps, "decode_access_token", lambda token: None)
    with pytest.raises(HTTPException) as ex:
        deps.get_current_user(db=object(), credentials=_Creds("bad"))
    assert ex.value.status_code == 401


def test_get_current_user_user_not_found(monkeypatch):
    monkeypatch.setattr(deps, "decode_access_token", lambda token: "u1")
    monkeypatch.setattr(deps, "get_by_id", lambda db, uid: None)
    with pytest.raises(HTTPException) as ex:
        deps.get_current_user(db=object(), credentials=_Creds("tok"))
    assert ex.value.status_code == 401


def test_get_current_user_success(monkeypatch):
    user = _User(user_id="u1")
    monkeypatch.setattr(deps, "decode_access_token", lambda token: "u1")
    monkeypatch.setattr(deps, "get_by_id", lambda db, uid: user)
    out = deps.get_current_user(db=object(), credentials=_Creds("tok"))
    assert out is user


def test_get_current_user_full_access_blocks_temp(monkeypatch):
    monkeypatch.setattr("app.repos.user_repo.is_temp_password_mode", lambda u: True)
    with pytest.raises(HTTPException) as ex:
        deps.get_current_user_full_access(user=_User())
    assert ex.value.status_code == 403


def test_get_current_admin_requires_admin():
    with pytest.raises(HTTPException) as ex:
        deps.get_current_admin(user=_User(is_admin=False))
    assert ex.value.status_code == 403


def test_get_current_admin_success():
    user = _User(is_admin=True)
    assert deps.get_current_admin(user=user) is user


def test_get_current_user_full_access_success(monkeypatch):
    user = _User()
    monkeypatch.setattr("app.repos.user_repo.is_temp_password_mode", lambda u: False)
    assert deps.get_current_user_full_access(user=user) is user
