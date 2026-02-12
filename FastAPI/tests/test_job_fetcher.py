import app.services.job_fetcher as jf


def test_site_names_from_settings_parses_csv(monkeypatch):
    monkeypatch.setattr(jf.settings, "job_site_names", "indeed, linkedin ,zip_recruiter")
    assert jf._site_names_from_settings() == ["indeed", "linkedin", "zip_recruiter"]


def test_site_names_from_settings_falls_back_when_empty(monkeypatch):
    monkeypatch.setattr(jf.settings, "job_site_names", "   ")
    assert jf._site_names_from_settings() == ["indeed", "linkedin", "zip_recruiter", "google"]


def test_fetch_and_deduplicate_jobs_requires_jobspy(monkeypatch):
    monkeypatch.setattr(jf, "scrape_jobs", None)
    try:
        jf.fetch_and_deduplicate_jobs()
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "jobspy" in str(e)


def test_fetch_and_deduplicate_jobs_wraps_scrape_errors(monkeypatch):
    monkeypatch.setattr(jf, "scrape_jobs", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("network")))
    try:
        jf.fetch_and_deduplicate_jobs()
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "Scraping error" in str(e)


def test_fetch_and_deduplicate_jobs_returns_none_on_empty(monkeypatch):
    import pandas as pd

    monkeypatch.setattr(jf, "scrape_jobs", lambda **kwargs: pd.DataFrame())
    out = jf.fetch_and_deduplicate_jobs()
    assert out is None


def test_fetch_and_deduplicate_jobs_normalizes_columns(monkeypatch):
    import pandas as pd

    df = pd.DataFrame(
        [
            {"title": "Engineer", "company_name": "ACME", "job_description": "desc", "job_url": "u1", "date_posted": "today"},
            {"title": "Engineer", "company_name": "ACME", "job_description": "desc2", "job_url": "u2", "date_posted": "today"},
            {"title": None, "company_name": None, "job_url": "u3", "date_posted": "today"},
        ]
    )
    monkeypatch.setattr(jf, "scrape_jobs", lambda **kwargs: df)
    out = jf.fetch_and_deduplicate_jobs()
    assert out is not None
    assert "description" in out.columns
    assert "company" in out.columns
    assert len(out) == 2
