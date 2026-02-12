from io import BytesIO

import app.main as main_mod


class _ConnOK:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, _query):
        return 1


class _EngineOK:
    def connect(self):
        return _ConnOK()


class _EngineFail:
    def connect(self):
        raise RuntimeError("db down")


def test_health_live(client):
    resp = client.get("/health/live")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_health_ready_ok(monkeypatch, client):
    monkeypatch.setattr(main_mod, "engine", _EngineOK())
    resp = client.get("/health/ready")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"


def test_health_ready_not_ready(monkeypatch, client):
    monkeypatch.setattr(main_mod, "engine", _EngineFail())
    resp = client.get("/health/ready")
    assert resp.status_code == 503
    assert resp.json()["status"] == "not_ready"


def test_parse_rejects_non_pdf_extension(client):
    resp = client.post(
        "/parse",
        files={"file": ("resume.txt", BytesIO(b"hello"), "text/plain")},
    )
    assert resp.status_code == 400
    assert "PDF" in resp.json()["detail"]


def test_parse_rejects_large_upload(monkeypatch, client):
    monkeypatch.setattr(main_mod.settings, "max_resume_upload_mb", 1)
    huge = b"%PDF" + (b"A" * (1024 * 1024 + 10))
    resp = client.post(
        "/parse",
        files={"file": ("resume.pdf", BytesIO(huge), "application/pdf")},
    )
    assert resp.status_code == 413


def test_parse_rejects_invalid_magic_bytes(client):
    resp = client.post(
        "/parse",
        files={"file": ("resume.pdf", BytesIO(b"NOT_PDF"), "application/pdf")},
    )
    assert resp.status_code == 400
    assert "Invalid PDF" in resp.json()["detail"]


def test_parse_success_strips_raw_fields(monkeypatch, client):
    def fake_build_resume_object(_path, ocr_fallback=True):
        return {
            "contact": {"name": "N"},
            "experience": [],
            "education": [],
            "raw_sections": {"x": 1},
            "raw_text": "secret",
        }

    monkeypatch.setattr(main_mod, "build_resume_object", fake_build_resume_object)
    payload = b"%PDF-1.4 mock content"
    resp = client.post(
        "/parse",
        files={"file": ("resume.pdf", BytesIO(payload), "application/pdf")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "raw_sections" not in data
    assert "raw_text" not in data


def test_root_route(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Resume Parser API" in resp.json()["message"]


def test_startup_production_placeholders_raise(monkeypatch):
    monkeypatch.setattr(main_mod.settings, "app_env", "production")
    monkeypatch.setattr(main_mod.settings, "secret_key", "replace-with-a-long-random-secret-key")
    monkeypatch.setattr(main_mod.settings, "database_url", "postgresql://username:password@localhost:5432/db")
    try:
        main_mod.on_startup()
        assert False, "expected runtime error"
    except RuntimeError:
        pass


def test_startup_nonprod_calls_init_db(monkeypatch):
    monkeypatch.setattr(main_mod.settings, "app_env", "development")
    monkeypatch.setattr(main_mod.settings, "secret_key", "dev-key")
    monkeypatch.setattr(main_mod.settings, "database_url", "postgresql://real:real@localhost:5432/db")
    called = {"ok": False}
    monkeypatch.setattr(main_mod, "init_db", lambda: called.update(ok=True))
    main_mod.on_startup()
    assert called["ok"] is True
