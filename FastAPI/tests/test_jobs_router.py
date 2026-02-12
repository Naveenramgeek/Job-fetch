import app.routers.jobs as jobs_mod


class _Job:
    def __init__(self, title="Backend Engineer", company="ACME", description="desc"):
        self.title = title
        self.company = company
        self.location = "Remote"
        self.job_url = "https://example.com"
        self.description = description
        self.posted_at = "today"
        self.created_at = None


class _Match:
    def __init__(self, match_id="m1", score=88.0, status="pending", with_job=True):
        self.id = match_id
        self.match_score = score
        self.match_reason = "good"
        self.resume_years_experience = 4.5
        self.applied_at = None
        self.status = status
        self.job_listing = _Job() if with_job else None


def test_run_pipeline_returns_500_when_internal_fails(monkeypatch, admin_client):
    monkeypatch.setattr(jobs_mod, "run_collector", lambda db: (_ for _ in ()).throw(RuntimeError("collector boom")))
    resp = admin_client.post("/jobs/run-pipeline")
    assert resp.status_code == 500
    assert "Pipeline run failed" in resp.json()["detail"]


def test_run_pipeline_success(monkeypatch, admin_client):
    monkeypatch.setattr("app.repos.search_category_repo.seed_default_categories", lambda db: ([], 0))
    monkeypatch.setattr("app.repos.job_listing_repo.delete_unmatched", lambda db: 5)
    monkeypatch.setattr(jobs_mod, "run_collector", lambda db: {"fetched": 10})
    monkeypatch.setattr(jobs_mod, "run_deep_match_all", lambda db: {"scored": 3})
    resp = admin_client.post("/jobs/run-pipeline")
    assert resp.status_code == 200
    assert resp.json()["cleanup_unmatched"] == 5


def test_render_latex_pdf_sanitizes_errors(monkeypatch, client):
    monkeypatch.setattr(jobs_mod, "render_latex_to_pdf_bytes", lambda latex: (_ for _ in ()).throw(RuntimeError("full stack trace")))
    resp = client.post("/jobs/render-latex-pdf", json={"latex": "\\documentclass{article}"})
    assert resp.status_code == 400
    assert "PDF generation failed" in resp.json()["detail"]


def test_tailor_resume_from_jd_requires_saved_resume(monkeypatch, client):
    monkeypatch.setattr(jobs_mod, "get_latest_by_user", lambda db, uid: None)
    resp = client.post("/jobs/tailor-resume-from-jd", json={"job_description": "A" * 100, "job_title": "Engineer"})
    assert resp.status_code == 400
    assert "No saved resume" in resp.json()["detail"]


def test_tailor_resume_from_jd_success(monkeypatch, client):
    class _Resume:
        parsed_data = {"summary": "hello", "experience": []}

    monkeypatch.setattr(jobs_mod, "get_latest_by_user", lambda db, uid: _Resume())
    monkeypatch.setattr(jobs_mod, "generate_tailored_latex", lambda **kwargs: "\\documentclass{article}")
    resp = client.post("/jobs/tailor-resume-from-jd", json={"job_description": "A" * 120, "job_title": "Backend Engineer"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["job_title"] == "Backend Engineer"
    assert data["latex"].startswith("\\documentclass")


def test_start_stop_pipeline_and_status(monkeypatch, admin_client):
    monkeypatch.setattr(jobs_mod, "start_scheduler", lambda: (True, "started"))
    monkeypatch.setattr(jobs_mod, "stop_scheduler", lambda: (True, "stopped"))
    monkeypatch.setattr(jobs_mod, "get_pipeline_status", lambda: {"running": True})
    r1 = admin_client.post("/jobs/start-pipeline")
    r2 = admin_client.post("/jobs/stop-pipeline")
    r3 = admin_client.get("/jobs/pipeline-status")
    assert r1.status_code == 200 and r1.json()["started"] is True
    assert r2.status_code == 200 and r2.json()["stopped"] is True
    assert r3.status_code == 200 and r3.json()["running"] is True


def test_start_pipeline_already_running(monkeypatch, admin_client):
    monkeypatch.setattr(jobs_mod, "start_scheduler", lambda: (False, "already running"))
    resp = admin_client.post("/jobs/start-pipeline")
    assert resp.status_code == 200
    assert resp.json()["started"] is False


def test_get_matched_jobs_and_applied(monkeypatch, client):
    monkeypatch.setattr(jobs_mod, "get_matches_for_user", lambda db, uid, status, limit: [_Match(with_job=True), _Match(with_job=False)])
    r1 = client.get("/jobs/matched")
    r2 = client.get("/jobs/applied")
    r3 = client.get("/jobs")
    assert r1.status_code == 200 and len(r1.json()) == 1
    assert r2.status_code == 200 and len(r2.json()) == 1
    assert r3.status_code == 200 and len(r3.json()["active"]) == 1


def test_delete_match_not_found(monkeypatch, client):
    monkeypatch.setattr(jobs_mod, "delete_match", lambda db, match_id, user_id: False)
    resp = client.delete("/jobs/matches/missing")
    assert resp.status_code == 404


def test_update_job_status_validations(monkeypatch, client):
    r_bad = client.patch("/jobs/matches/m1", json={"status": "pending"})
    assert r_bad.status_code == 400

    monkeypatch.setattr(jobs_mod, "update_status", lambda db, match_id, user_id, status: None)
    r_missing = client.patch("/jobs/matches/m1", json={"status": "applied"})
    assert r_missing.status_code == 404

    monkeypatch.setattr(jobs_mod, "update_status", lambda db, match_id, user_id, status: _Match(match_id=match_id, score=0.9))
    r_ok = client.patch("/jobs/matches/m1", json={"status": "applied"})
    assert r_ok.status_code == 200


def test_tailor_resume_for_match_paths(monkeypatch, client):
    monkeypatch.setattr(jobs_mod, "get_match_for_user", lambda db, match_id, user_id: None)
    r404 = client.post("/jobs/matches/m1/tailor-resume")
    assert r404.status_code == 404

    monkeypatch.setattr(jobs_mod, "get_match_for_user", lambda db, match_id, user_id: _Match())
    monkeypatch.setattr(jobs_mod, "get_latest_by_user", lambda db, uid: None)
    r400 = client.post("/jobs/matches/m1/tailor-resume")
    assert r400.status_code == 400

    class _Resume:
        parsed_data = {"summary": "x"}

    monkeypatch.setattr(jobs_mod, "get_latest_by_user", lambda db, uid: _Resume())
    monkeypatch.setattr(jobs_mod, "generate_tailored_latex", lambda **kwargs: "\\documentclass{article}")
    rok = client.post("/jobs/matches/m1/tailor-resume")
    assert rok.status_code == 200
    assert rok.json()["company"] == "ACME"


def test_tailor_resume_from_jd_rejects_blank_after_strip(monkeypatch, client):
    class _Resume:
        parsed_data = {"summary": "x"}

    monkeypatch.setattr(jobs_mod, "get_latest_by_user", lambda db, uid: _Resume())
    resp = client.post("/jobs/tailor-resume-from-jd", json={"job_description": " " * 30, "job_title": "Engineer"})
    assert resp.status_code == 400


def test_render_latex_pdf_success(monkeypatch, client):
    monkeypatch.setattr(jobs_mod, "render_latex_to_pdf_bytes", lambda latex: b"%PDF-1.4")
    resp = client.post("/jobs/render-latex-pdf", json={"latex": "\\documentclass{article}"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/pdf")
