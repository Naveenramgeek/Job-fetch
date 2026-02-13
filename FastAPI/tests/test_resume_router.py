import app.routers.resume as resume_mod


def test_get_latest_resume_not_found(monkeypatch, client):
    monkeypatch.setattr(resume_mod, "get_latest_by_user", lambda db, uid: None)
    resp = client.get("/resumes/latest")
    assert resp.status_code == 404


def test_save_resume_success_even_if_category_assignment_fails(monkeypatch, client):
    class _Resume:
        id = "r1"
        user_id = "user-1"
        parsed_data = {"summary": "x"}

    monkeypatch.setattr(resume_mod, "create_resume", lambda db, uid, data: _Resume())
    monkeypatch.setattr(
        resume_mod,
        "assign_user_category",
        lambda db, uid, resume_data: (_ for _ in ()).throw(RuntimeError("llm failed")),
    )
    resp = client.post("/resumes", json={"parsed_data": {"summary": "x"}})
    assert resp.status_code == 200
    assert resp.json()["id"] == "r1"


def test_update_latest_resume_returns_500_on_repo_failure(monkeypatch, client):
    class _Resume:
        id = "r1"
        user_id = "user-1"
        parsed_data = {"summary": "x"}

    monkeypatch.setattr(resume_mod, "get_latest_by_user", lambda db, uid: _Resume())
    monkeypatch.setattr(resume_mod, "update_resume", lambda db, rid, uid, data: (_ for _ in ()).throw(RuntimeError("db")))
    resp = client.put("/resumes/latest", json={"parsed_data": {"summary": "updated"}})
    assert resp.status_code == 500


def test_get_latest_resume_success(monkeypatch, client):
    class _Resume:
        id = "r1"
        user_id = "user-1"
        parsed_data = {"summary": "x"}

    monkeypatch.setattr(resume_mod, "get_latest_by_user", lambda db, uid: _Resume())
    resp = client.get("/resumes/latest")
    assert resp.status_code == 200
    assert resp.json()["id"] == "r1"


def test_update_latest_resume_success(monkeypatch, client):
    class _Resume:
        id = "r1"
        user_id = "user-1"
        parsed_data = {"summary": "x"}

    monkeypatch.setattr(resume_mod, "get_latest_by_user", lambda db, uid: _Resume())
    monkeypatch.setattr(resume_mod, "update_resume", lambda db, rid, uid, data: _Resume())
    monkeypatch.setattr(resume_mod, "assign_user_category", lambda db, uid, resume_data: "software_engineer")
    resp = client.put("/resumes/latest", json={"parsed_data": {"summary": "updated"}})
    assert resp.status_code == 200


def test_save_resume_returns_500_on_create_failure(monkeypatch, client):
    monkeypatch.setattr(resume_mod, "create_resume", lambda db, uid, data: (_ for _ in ()).throw(RuntimeError("db")))
    resp = client.post("/resumes", json={"parsed_data": {"summary": "x"}})
    assert resp.status_code == 500


def test_update_latest_resume_success_even_if_category_assign_fails(monkeypatch, client):
    class _Resume:
        id = "r1"
        user_id = "user-1"
        parsed_data = {"summary": "x"}

    monkeypatch.setattr(resume_mod, "get_latest_by_user", lambda db, uid: _Resume())
    monkeypatch.setattr(resume_mod, "update_resume", lambda db, rid, uid, data: _Resume())
    monkeypatch.setattr(
        resume_mod,
        "assign_user_category",
        lambda db, uid, resume_data: (_ for _ in ()).throw(RuntimeError("llm failed")),
    )
    resp = client.put("/resumes/latest", json={"parsed_data": {"summary": "updated"}})
    assert resp.status_code == 200


def test_update_latest_resume_not_found(monkeypatch, client):
    monkeypatch.setattr(resume_mod, "get_latest_by_user", lambda db, uid: None)
    resp = client.put("/resumes/latest", json={"parsed_data": {"summary": "updated"}})
    assert resp.status_code == 404


def test_save_resume_triggers_bootstrap_when_category_assigned(monkeypatch, client):
    class _Resume:
        id = "r1"
        user_id = "user-1"
        parsed_data = {"summary": "x"}

    called = {"ok": False}
    monkeypatch.setattr(resume_mod, "create_resume", lambda db, uid, data: _Resume())
    monkeypatch.setattr(resume_mod, "assign_user_category", lambda db, uid, resume_data: "software_engineer")
    monkeypatch.setattr(resume_mod, "_run_new_user_bootstrap_pipeline", lambda uid: called.update(ok=True))
    resp = client.post("/resumes", json={"parsed_data": {"summary": "x"}})
    assert resp.status_code == 200
    assert called["ok"] is True


def test_save_resume_skips_bootstrap_when_no_category_assigned(monkeypatch, client):
    class _Resume:
        id = "r1"
        user_id = "user-1"
        parsed_data = {"summary": "x"}

    monkeypatch.setattr(resume_mod, "create_resume", lambda db, uid, data: _Resume())
    monkeypatch.setattr(resume_mod, "assign_user_category", lambda db, uid, resume_data: None)
    monkeypatch.setattr(
        resume_mod,
        "_run_new_user_bootstrap_pipeline",
        lambda uid: (_ for _ in ()).throw(RuntimeError("must not run")),
    )
    resp = client.post("/resumes", json={"parsed_data": {"summary": "x"}})
    assert resp.status_code == 200


def test_new_user_bootstrap_pipeline_skips_when_user_missing(monkeypatch):
    class _DB:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    db = _DB()
    monkeypatch.setattr(resume_mod, "SessionLocal", lambda: db)
    monkeypatch.setattr(resume_mod, "get_user_by_id", lambda _db, _uid: None)
    resume_mod._run_new_user_bootstrap_pipeline("u1")
    assert db.closed is True


def test_new_user_bootstrap_pipeline_runs_collector_and_match(monkeypatch):
    class _DB:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    class _User:
        search_category_id = "c1"

    db = _DB()
    called = {"collector": False, "match": False}
    monkeypatch.setattr(resume_mod, "SessionLocal", lambda: db)
    monkeypatch.setattr(resume_mod, "get_user_by_id", lambda _db, _uid: _User())
    monkeypatch.setattr(
        resume_mod,
        "run_collector",
        lambda _db, **kwargs: called.update(collector=(kwargs["results_wanted"] == 200 and kwargs["hours_old"] == 10)) or {},
    )
    monkeypatch.setattr(
        resume_mod,
        "run_deep_match_for_user",
        lambda _db, _uid, since_hours: called.update(match=(since_hours == 10)) or {},
    )
    resume_mod._run_new_user_bootstrap_pipeline("u1")
    assert called["collector"] is True
    assert called["match"] is True
    assert db.closed is True
