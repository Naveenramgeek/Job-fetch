import app.main as main_mod
import pytest


def test_auth_rate_limit_blocks_excess_requests(monkeypatch, client):
    # Isolate limiter state for deterministic test.
    main_mod.rate_limiter._state.clear()  # noqa: SLF001
    monkeypatch.setattr(main_mod.settings, "rate_limit_auth_per_min", 2)
    monkeypatch.setattr(main_mod.settings, "rate_limit_parse_per_min", 1000)
    monkeypatch.setattr(main_mod.settings, "rate_limit_tailor_per_min", 1000)
    monkeypatch.setattr(main_mod.settings, "rate_limit_pdf_render_per_min", 1000)

    # login endpoint should be limited by middleware before auth logic fully succeeds.
    payload = {"email": "x@example.com", "password": "bad"}
    r1 = client.post("/auth/login", json=payload)
    r2 = client.post("/auth/login", json=payload)
    r3 = client.post("/auth/login", json=payload)

    assert r1.status_code in (401, 403, 500)
    assert r2.status_code in (401, 403, 500)
    assert r3.status_code == 429


def test_auth_rate_limit_applies_to_activate_endpoint_and_forwarded_ip(monkeypatch, client):
    main_mod.rate_limiter._state.clear()  # noqa: SLF001
    monkeypatch.setattr(main_mod.settings, "rate_limit_auth_per_min", 1)
    monkeypatch.setattr(main_mod.settings, "rate_limit_parse_per_min", 1000)
    monkeypatch.setattr(main_mod.settings, "rate_limit_tailor_per_min", 1000)
    monkeypatch.setattr(main_mod.settings, "rate_limit_pdf_render_per_min", 1000)

    headers = {"x-forwarded-for": "203.0.113.9"}
    r1 = client.get("/auth/activate", params={"token": "invalid-token"}, headers=headers)
    r2 = client.get("/auth/activate", params={"token": "invalid-token"}, headers=headers)

    assert r1.status_code == 400
    assert r2.status_code == 429
    assert "Retry-After" in r2.headers


@pytest.mark.parametrize(
    "path, payload, first_statuses",
    [
        ("/auth/activate", {"token": "bad-token"}, {405}),
        ("/auth/reset-password", {"token": "bad", "new_password": "longenough1", "confirm_password": "longenough1"}, {400}),
    ],
)
def test_auth_rate_limit_applies_to_new_auth_paths(monkeypatch, client, path, payload, first_statuses):
    main_mod.rate_limiter._state.clear()  # noqa: SLF001
    monkeypatch.setattr(main_mod.settings, "rate_limit_auth_per_min", 1)
    monkeypatch.setattr(main_mod.settings, "rate_limit_parse_per_min", 1000)
    monkeypatch.setattr(main_mod.settings, "rate_limit_tailor_per_min", 1000)
    monkeypatch.setattr(main_mod.settings, "rate_limit_pdf_render_per_min", 1000)

    headers = {"x-forwarded-for": "198.51.100.7"}
    if path == "/auth/activate":
        r1 = client.post(path, headers=headers)  # wrong method still passes through middleware
        r2 = client.post(path, headers=headers)
    else:
        r1 = client.post(path, json=payload, headers=headers)
        r2 = client.post(path, json=payload, headers=headers)

    assert r1.status_code in first_statuses
    assert r2.status_code == 429
