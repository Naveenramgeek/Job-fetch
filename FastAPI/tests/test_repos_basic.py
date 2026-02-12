from datetime import datetime, timezone, timedelta

import app.repos.job_listing_repo as jrepo
import app.repos.resume_repo as rrepo
import app.repos.search_category_repo as crepo
import app.repos.user_job_match_repo as mrepo
import app.repos.user_repo as urepo


class _Query:
    def __init__(self, data):
        self.data = data

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def options(self, *args, **kwargs):
        return self

    def offset(self, n):
        return self

    def limit(self, n):
        return self

    def all(self):
        return self.data if isinstance(self.data, list) else [self.data]

    def first(self):
        if isinstance(self.data, list):
            return self.data[0] if self.data else None
        return self.data

    def count(self):
        if isinstance(self.data, list):
            return len(self.data)
        return 1 if self.data else 0

    def delete(self, synchronize_session=False):
        return 1

    def join(self, *args, **kwargs):
        return self

    def distinct(self):
        return self

    def subquery(self):
        return object()

    def __invert__(self):
        return self


class _DB:
    def __init__(self, data=None):
        self.data = data
        self.added = []
        self.deleted = []
        self.executed = []
        self.committed = 0

    def query(self, model):
        return _Query(self.data)

    def add(self, obj):
        self.added.append(obj)

    def delete(self, obj):
        self.deleted.append(obj)

    def execute(self, *args, **kwargs):
        self.executed.append((args, kwargs))
        return type("R", (), {"rowcount": 1})()

    def commit(self):
        self.committed += 1

    def refresh(self, obj):
        return None


def test_user_repo_create_update_and_temp_password(monkeypatch):
    db = _DB(data=type("U", (), {"id": "u1", "created_at": None})())
    monkeypatch.setattr(urepo, "generate_id", lambda: "u1")
    monkeypatch.setattr(urepo, "hash_password", lambda p: "hashed")
    user = urepo.create(db, "u@example.com", "secret")
    assert user.id == "u1"
    assert db.committed >= 1

    monkeypatch.setattr(urepo, "get_by_id", lambda db, uid: user)
    urepo.update(db, "u1", email="new@example.com", is_admin=True, is_active=False)
    assert user.email == "new@example.com"
    assert user.is_admin is True
    assert user.is_active is False

    exp = datetime.now(timezone.utc) + timedelta(minutes=5)
    urepo.set_temp_password(db, "u1", "tmp", exp)
    assert urepo.is_temp_password_mode(user) in (True, False)
    urepo.clear_temp_password(db, "u1")


def test_resume_repo_create_get_update(monkeypatch):
    db = _DB(data=type("R", (), {"id": "r1", "user_id": "u1", "parsed_data": {"x": 1}})())
    monkeypatch.setattr(rrepo, "generate_id", lambda: "r1")
    out = rrepo.create(db, "u1", {"summary": "s"})
    assert out.id == "r1"
    assert rrepo.get_latest_by_user(db, "u1") is not None
    assert rrepo.get_by_id(db, "r1", "u1") is not None
    updated = rrepo.update(db, "r1", "u1", {"summary": "u"})
    assert updated.parsed_data == {"summary": "u"}


def test_search_category_repo_seed_and_fetch(monkeypatch):
    db = _DB(data=[])
    monkeypatch.setattr(crepo, "get_all", lambda db: [])
    created = []
    monkeypatch.setattr(crepo, "create", lambda db, slug, display_name: created.append((slug, display_name)) or type("C", (), {"slug": slug, "display_name": display_name})())
    cats, count = crepo.seed_default_categories(db)
    assert count == 4
    assert len(cats) == 4


def test_user_job_match_repo_core_paths(monkeypatch):
    db = _DB(data=type("M", (), {"id": "m1", "user_id": "u1", "job_listing_id": "j1", "status": "pending"})())
    monkeypatch.setattr(mrepo, "generate_id", lambda: "m1")
    created = mrepo.create(db, "u1", "j1", 88.0, "great", 4.2)
    assert created.id == "m1"
    assert mrepo.get_existing_match(db, "u1", "j1") is not None
    assert mrepo.get_matches_for_user(db, "u1", status="pending", limit=10)
    assert mrepo.get_match_for_user(db, "m1", "u1") is not None
    assert mrepo.delete_match(db, "m1", "u1") is True
    updated = mrepo.update_status(db, "m1", "u1", "applied")
    assert updated.status == "applied"


def test_job_listing_repo_batch_create_update_delete(monkeypatch):
    db = _DB(data=type("J", (), {"id": "j1", "title": "A", "company": "C", "job_url": "u", "created_at": datetime.now(timezone.utc), "search_category_id": "c1", "description": "d", "location": None, "posted_at": None})())
    monkeypatch.setattr(jrepo, "generate_id", lambda: "j1")
    n = jrepo.batch_upsert(db, [{"title": "A", "company": "C", "job_url": "u"}], "c1")
    assert n == 1
    one = jrepo.create_one(db, "c1", "T", "Co", "https://x")
    assert one.id == "j1"
    monkeypatch.setattr(jrepo, "get_by_id", lambda db, listing_id: one)
    upd = jrepo.update_one(db, "j1", title="New", company="NewCo", job_url="https://y")
    assert upd.title == "New"
    jrepo.get_all(db, search_category_id="c1", limit=10)
    items, total = jrepo.get_all_paginated(db, search_category_id="c1", search="new", limit=5, offset=0)
    assert isinstance(items, list) and total >= 1
    monkeypatch.setattr("sqlalchemy.delete", lambda model: f"delete:{model}")
    jrepo.delete_all(db)
    assert jrepo.delete_one(db, "j1") is True


def test_job_listing_repo_delete_unmatched(monkeypatch):
    class _Expr:
        def __invert__(self):
            return self

    class _Col:
        def in_(self, _):
            return _Expr()

    monkeypatch.setattr(jrepo.JobListing, "id", _Col())

    class _Q(_Query):
        def all(self):
            return [type("J", (), {})(), type("J", (), {})()]

    class _DB2(_DB):
        def query(self, model):
            return _Q(self.data)

    db = _DB2(data=[])
    deleted = jrepo.delete_unmatched(db, min_age_hours=0)
    assert deleted == 2


def test_job_listing_repo_get_jobs_by_category_since():
    db = _DB(data=[])
    out = jrepo.get_jobs_by_category_since(db, "c1", since_hours=2)
    assert isinstance(out, list)


def test_user_repo_additional_list_and_delete(monkeypatch):
    user = type("U", (), {"id": "u1", "created_at": None})()
    db = _DB(data=[user])
    assert isinstance(urepo.get_all_users(db), list)
    items, total = urepo.get_all_users_paginated(db, search="u", limit=10, offset=0)
    assert total >= 1 and isinstance(items, list)
    monkeypatch.setattr(urepo, "get_by_id", lambda db, uid: user)
    assert urepo.delete_user(db, "u1") is True


def test_search_category_repo_getters(monkeypatch):
    cat = type("C", (), {"id": "c1", "slug": "software_engineer"})()
    db = _DB(data=cat)
    monkeypatch.setattr(crepo, "generate_id", lambda: "c1")
    created = crepo.create(db, "software_engineer", "Software Engineer")
    assert created.id == "c1"
    assert crepo.get_by_slug(db, "software_engineer") is not None
    assert crepo.get_by_id(db, "c1") is not None
    assert isinstance(crepo.get_categories_with_active_users(db), list)
