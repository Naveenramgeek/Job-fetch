import app.repos.feedback_repo as repo


class _DB:
    def __init__(self):
        self.added = None
        self.committed = False
        self.refreshed = False

    def add(self, obj):
        self.added = obj

    def commit(self):
        self.committed = True

    def refresh(self, obj):
        self.refreshed = True


class _Query:
    def __init__(self):
        self.filtered = False

    def join(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        self.filtered = True
        return self

    def count(self):
        return 2

    def offset(self, n):
        return self

    def limit(self, n):
        return self

    def all(self):
        return [("f1", "u1"), ("f2", "u2")]


class _DBQuery:
    def query(self, *args, **kwargs):
        return _Query()


def test_create_feedback_persists_record(monkeypatch):
    monkeypatch.setattr(repo, "generate_id", lambda: "fb-1")
    db = _DB()
    item = repo.create_feedback(
        db,
        user_id="u1",
        category="General",
        message="Useful product and easy navigation",
        rating=5,
        page="/dashboard",
    )
    assert item.id == "fb-1"
    assert db.added is item
    assert db.committed is True
    assert db.refreshed is True


def test_get_feedback_paginated_returns_items_and_total():
    items, total = repo.get_feedback_paginated(_DBQuery(), search="foo", page=1, page_size=20)
    assert total == 2
    assert len(items) == 2
