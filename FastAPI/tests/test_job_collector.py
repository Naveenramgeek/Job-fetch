import pandas as pd

import app.services.job_collector as jc


class _Category:
    def __init__(self, cat_id, slug):
        self.id = cat_id
        self.slug = slug


def test_fetch_for_category_handles_fetch_exception(monkeypatch):
    monkeypatch.setattr(jc, "fetch_and_deduplicate_jobs", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
    out = jc._fetch_for_category("software_engineer", "c1")
    assert out == []


def test_fetch_for_category_maps_dataframe_rows(monkeypatch):
    df = pd.DataFrame(
        [
            {"title": "A", "company": "X", "job_url": "u1", "description": "d1"},
            {"title": "B", "company_name": "Y", "job_url": "u2", "job_description": "d2"},
            {"title": "C", "company": "Z", "job_url": "", "description": "skip"},
        ]
    )
    monkeypatch.setattr(jc, "fetch_and_deduplicate_jobs", lambda **kwargs: df)
    out = jc._fetch_for_category("software_engineer", "c1")
    assert len(out) == 2
    assert out[0]["search_category_id"] == "c1"


def test_run_collector_returns_zero_when_no_categories(monkeypatch):
    monkeypatch.setattr(jc, "get_categories_with_active_users", lambda db: [])
    monkeypatch.setattr(jc, "get_all", lambda db: [])
    out = jc.run_collector(db=object())
    assert out["total_fetched"] == 0
    assert out["categories"] == 0


def test_run_collector_dedupes_and_batches_by_category(monkeypatch):
    cats = [_Category("c1", "software_engineer"), _Category("c2", "data_scientist")]
    monkeypatch.setattr(jc, "get_categories_with_active_users", lambda db: cats)

    def fake_fetch(slug, cid):
        if cid == "c1":
            return [
                {"title": "A", "company": "X", "job_url": "u1", "search_category_id": "c1"},
                {"title": "A", "company": "X", "job_url": "u1-dup", "search_category_id": "c1"},
            ]
        return [{"title": "B", "company": "Y", "job_url": "u2", "search_category_id": "c2"}]

    monkeypatch.setattr(jc, "_fetch_for_category", fake_fetch)
    called = []

    def fake_upsert(db, rows, cid):
        called.append((cid, len(rows)))
        return len(rows)

    monkeypatch.setattr(jc, "batch_upsert", fake_upsert)
    out = jc.run_collector(db=object())
    assert out["total_fetched"] == 3
    assert out["total_deduped"] == 2
    assert out["inserted"] == 2
    assert sorted(called) == [("c1", 1), ("c2", 1)]


def test_run_collector_with_category_override_and_fetch_window(monkeypatch):
    cats = [_Category("c1", "software_engineer")]
    monkeypatch.setattr(jc, "get_category_by_id", lambda db, cid: cats[0] if cid == "c1" else None)
    captured = {}

    def fake_fetch(slug, cid, results_wanted=None, hours_old=None):
        captured["wanted"] = results_wanted
        captured["hours"] = hours_old
        return [{"title": "A", "company": "X", "job_url": "u1", "search_category_id": "c1"}]

    monkeypatch.setattr(jc, "_fetch_for_category", fake_fetch)
    monkeypatch.setattr(jc, "batch_upsert", lambda db, rows, cid: len(rows))
    out = jc.run_collector(db=object(), category_ids=["c1"], results_wanted=200, hours_old=10)
    assert out["categories"] == 1
    assert out["inserted"] == 1
    assert captured["wanted"] == 200
    assert captured["hours"] == 10


def test_run_collector_with_invalid_category_override_returns_zero(monkeypatch):
    monkeypatch.setattr(jc, "get_category_by_id", lambda db, cid: None)
    out = jc.run_collector(db=object(), category_ids=["missing"])
    assert out == {"total_fetched": 0, "total_deduped": 0, "inserted": 0, "categories": 0}


def test_run_collector_handles_thread_fetch_exception(monkeypatch):
    cats = [_Category("c1", "software_engineer")]
    monkeypatch.setattr(jc, "get_categories_with_active_users", lambda db: cats)
    monkeypatch.setattr(jc, "_fetch_for_category", lambda slug, cid: (_ for _ in ()).throw(RuntimeError("boom")))
    out = jc.run_collector(db=object())
    assert out["total_fetched"] == 0
    assert out["categories"] == 1
