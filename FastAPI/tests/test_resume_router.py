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
