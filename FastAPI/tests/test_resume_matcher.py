import app.services.resume_matcher as matcher


def test_compute_resume_total_years_merges_overlaps():
    resume = {
        "experience": [
            {"start": "Jan 2020", "end": "Dec 2020"},
            {"start": "Jun 2020", "end": "Dec 2021"},
            {"start": "2023", "end": "2023"},
        ]
    }
    years = matcher._compute_resume_total_years(resume)
    # Jan 2020-Dec 2021 => 24 months, plus full 2023 => 12 months => 3.0 years.
    assert years == 3.0


def test_extract_required_years_from_jd_parses_multiple_patterns():
    jd = "Need at least 3 years experience. Also 5+ years of experience preferred."
    req = matcher._extract_required_years_from_jd(jd)
    assert req == 5.0


def test_llm_match_hard_gate_blocks_before_llm(monkeypatch):
    resume = {"experience": [{"start": "Jan 2022", "end": "Dec 2022"}]}
    monkeypatch.setattr(matcher, "is_llm_enabled", lambda: True)
    monkeypatch.setattr(matcher, "llm_match_resume_job", lambda a, b, c: (0.99, "should not be called"))
    out = matcher.llm_match(resume, "Senior Engineer", "Minimum of 6 years of experience in backend systems")
    assert out["hard_gate_blocked"] is True
    assert out["match_score"] == 0.0
    assert "Hard gate" in out["match_reason"]


def test_llm_match_falls_back_when_llm_fails(monkeypatch):
    resume = {
        "experience": [
            {
                "title": "Backend Engineer",
                "company": "ACME",
                "start": "Jan 2020",
                "end": "Dec 2023",
                "bullets": ["Built Python FastAPI services and PostgreSQL queries"],
            }
        ]
    }
    monkeypatch.setattr(matcher, "is_llm_enabled", lambda: True)
    monkeypatch.setattr(
        matcher,
        "llm_match_resume_job",
        lambda a, b, c: (_ for _ in ()).throw(RuntimeError("bedrock timeout")),
    )
    out = matcher.llm_match(resume, "Backend Engineer", "Python FastAPI PostgreSQL AWS")
    assert out["hard_gate_blocked"] is False
    assert out["match_reason"].startswith("Fallback similarity")
    assert 0.35 <= out["match_score"] <= 0.92
