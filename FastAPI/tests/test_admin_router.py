from datetime import datetime, timezone

import app.routers.admin as admin_mod


class _User:
    def __init__(
        self,
        user_id="u1",
        email="u@example.com",
        is_admin=True,
        is_active=True,
        search_category_id=None,
    ):
        self.id = user_id
        self.email = email
        self.is_admin = is_admin
        self.is_active = is_active
        self.search_category_id = search_category_id
        self.created_at = datetime.now(timezone.utc)


class _Category:
    def __init__(self, cat_id="c1", slug="software_engineer", display_name="Software Engineer"):
        self.id = cat_id
        self.slug = slug
        self.display_name = display_name


class _Listing:
    def __init__(self, listing_id="j1", title="Backend Engineer", company="ACME"):
        self.id = listing_id
        self.job_hash = "hash1"
        self.search_category_id = "c1"
        self.title = title
        self.company = company
        self.location = "Remote"
        self.job_url = "https://example.com/job"
        self.description = "desc"
        self.posted_at = "today"
        self.created_at = datetime.now(timezone.utc)


def test_admin_stats_success(monkeypatch, admin_client):
    monkeypatch.setattr(admin_mod, "get_stats", lambda db: {"users_total": 1})
    resp = admin_client.get("/admin/stats")
    assert resp.status_code == 200
    assert resp.json()["users_total"] == 1


def test_admin_stats_failure_sanitized(monkeypatch, admin_client):
    monkeypatch.setattr(admin_mod, "get_stats", lambda db: (_ for _ in ()).throw(RuntimeError("db fail")))
    resp = admin_client.get("/admin/stats")
    assert resp.status_code == 500
    assert "Failed to load admin stats" in resp.json()["detail"]


def test_admin_list_users_paginates(monkeypatch, admin_client):
    monkeypatch.setattr(admin_mod, "get_all_users_paginated", lambda db, search, limit, offset: ([_User()], 1))
    resp = admin_client.get("/admin/users?page=1&page_size=20")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1


def test_admin_get_user_not_found(monkeypatch, admin_client):
    monkeypatch.setattr(admin_mod, "get_by_id", lambda db, user_id: None)
    resp = admin_client.get("/admin/users/missing")
    assert resp.status_code == 404


def test_admin_create_user_validates_duplicate_email(monkeypatch, admin_client):
    monkeypatch.setattr("app.repos.user_repo.get_by_email", lambda db, email: _User())
    resp = admin_client.post(
        "/admin/users",
        json={"email": "dup@example.com", "password": "pass123", "is_admin": False, "is_active": True},
    )
    assert resp.status_code == 400
    assert "already" in resp.json()["detail"].lower()


def test_admin_create_user_success(monkeypatch, admin_client):
    created = _User(user_id="new1", email="new@example.com", is_admin=False)
    monkeypatch.setattr("app.repos.user_repo.get_by_email", lambda db, email: None)
    monkeypatch.setattr("app.repos.search_category_repo.get_by_id", lambda db, cid: _Category(cat_id=cid))
    monkeypatch.setattr(admin_mod, "create_user_repo", lambda db, email, password: created)
    monkeypatch.setattr(admin_mod, "update_user", lambda db, user_id, **kwargs: created)
    monkeypatch.setattr(admin_mod, "get_by_id", lambda db, user_id: created)
    resp = admin_client.post(
        "/admin/users",
        json={
            "email": "new@example.com",
            "password": "pass123",
            "is_admin": True,
            "is_active": True,
            "search_category_id": "c1",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == "new1"


def test_admin_update_user_prevents_self_demotion(monkeypatch, admin_client):
    monkeypatch.setattr(admin_mod, "get_by_id", lambda db, user_id: _User(user_id="admin-1"))
    resp = admin_client.patch("/admin/users/admin-1", json={"is_admin": False})
    assert resp.status_code == 400


def test_admin_update_user_success(monkeypatch, admin_client):
    monkeypatch.setattr(admin_mod, "get_by_id", lambda db, user_id: _User(user_id=user_id))
    monkeypatch.setattr("app.repos.user_repo.get_by_email", lambda db, email: None)
    monkeypatch.setattr("app.repos.search_category_repo.get_by_id", lambda db, cid: _Category(cat_id=cid))
    monkeypatch.setattr(admin_mod, "hash_password", lambda p: "hashed")
    monkeypatch.setattr(
        admin_mod,
        "update_user",
        lambda db, user_id, **kwargs: _User(user_id=user_id, email=kwargs.get("email") or "u@example.com"),
    )
    resp = admin_client.patch("/admin/users/u-2", json={"email": "new2@example.com", "password": "x123"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "new2@example.com"


def test_admin_delete_user_self_forbidden(admin_client):
    resp = admin_client.delete("/admin/users/admin-1")
    assert resp.status_code == 400


def test_admin_delete_user_success(monkeypatch, admin_client):
    monkeypatch.setattr(admin_mod, "get_by_id", lambda db, user_id: _User(user_id=user_id))
    monkeypatch.setattr(admin_mod, "delete_user", lambda db, user_id: True)
    resp = admin_client.delete("/admin/users/u-9")
    assert resp.status_code == 200
    assert "deleted" in resp.json()["message"].lower()


def test_admin_categories_and_seed(monkeypatch, admin_client):
    monkeypatch.setattr(admin_mod, "get_all_categories", lambda db: [_Category()])
    monkeypatch.setattr(admin_mod, "init_db", lambda: None)
    monkeypatch.setattr(admin_mod, "seed_default_categories", lambda db: ([_Category()], 1))
    r1 = admin_client.get("/admin/categories")
    r2 = admin_client.post("/admin/seed-categories")
    assert r1.status_code == 200 and len(r1.json()) == 1
    assert r2.status_code == 200 and "Created" in r2.json()["message"]


def test_admin_job_listing_crud_paths(monkeypatch, admin_client):
    listing = _Listing()
    monkeypatch.setattr(admin_mod, "get_job_listings_paginated", lambda db, **kwargs: ([listing], 1))
    monkeypatch.setattr(admin_mod, "get_job_listing_by_id", lambda db, listing_id: listing if listing_id == "j1" else None)
    monkeypatch.setattr("app.repos.search_category_repo.get_by_id", lambda db, cid: _Category(cat_id=cid))
    monkeypatch.setattr(admin_mod, "create_job_listing", lambda db, **kwargs: _Listing(listing_id="j2"))
    monkeypatch.setattr(admin_mod, "update_job_listing", lambda db, listing_id, **kwargs: _Listing(listing_id=listing_id))
    monkeypatch.setattr(admin_mod, "delete_all_job_listings", lambda db: 3)
    monkeypatch.setattr(admin_mod, "delete_job_listing", lambda db, listing_id: listing_id == "j1")

    r_list = admin_client.get("/admin/job-listings?page=1&page_size=10")
    r_get = admin_client.get("/admin/job-listings/j1")
    r_create = admin_client.post(
        "/admin/job-listings",
        json={"search_category_id": "c1", "title": "T", "company": "C", "job_url": "https://e.com"},
    )
    r_update = admin_client.patch("/admin/job-listings/j1", json={"title": "Updated"})
    r_del_all = admin_client.delete("/admin/job-listings")
    r_del_one_ok = admin_client.delete("/admin/job-listings/j1")
    r_del_one_missing = admin_client.delete("/admin/job-listings/missing")

    assert r_list.status_code == 200 and r_list.json()["total"] == 1
    assert r_get.status_code == 200 and "description" in r_get.json()
    assert r_create.status_code == 200
    assert r_update.status_code == 200
    assert r_del_all.status_code == 200 and r_del_all.json()["deleted"] == 3
    assert r_del_one_ok.status_code == 200
    assert r_del_one_missing.status_code == 404
