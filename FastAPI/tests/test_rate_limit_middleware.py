import app.main as main_mod


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
