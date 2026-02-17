import app.services.resume_matcher as matcher
import numpy as np


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


def test_llm_match_hard_gate_blocks_on_total_years():
    resume = {"experience": [{"start": "Jan 2022", "end": "Dec 2022"}]}
    out = matcher.llm_match(resume, "Senior Engineer", "Minimum of 6 years of experience in backend systems")
    assert out["hard_gate_blocked"] is True
    assert out["match_score"] == 0.0
    assert "Hard gate" in out["match_reason"]


def test_llm_match_hybrid_scoring_uses_embedding_and_keyword_features(monkeypatch):
    resume = {
        "experience": [
            {
                "title": "Backend Engineer",
                "company": "ACME",
                "start": "Jan 2020",
                "end": "Dec 2023",
                "bullets": ["Built Python FastAPI services and PostgreSQL queries"],
            }
        ],
        "skills": {"Languages": ["Python"], "Frameworks": ["FastAPI"], "Databases": ["PostgreSQL"]},
    }
    monkeypatch.setattr(matcher, "_semantic_similarity_score", lambda a, b, **kwargs: 0.82)
    out = matcher.llm_match(resume, "Backend Engineer", "Python FastAPI PostgreSQL AWS")
    assert out["hard_gate_blocked"] is False
    assert out["match_reason"].startswith("Hybrid score")
    assert 0.0 <= out["match_score"] <= 1.0


def test_extract_required_skill_years_and_gate_blocks():
    jd = "We need 7+ years of Java and at least 3 years of Python."
    req = matcher._extract_required_skill_years_from_jd(jd)
    assert req.get("java") == 7.0
    assert req.get("python") == 3.0

    resume = {
        "experience": [
            {"title": "Java Developer", "start": "Jan 2022", "end": "Dec 2022", "bullets": ["Built Java services"]},
            {"title": "Python Engineer", "start": "Jan 2023", "end": "Dec 2023", "bullets": ["Built Python APIs"]},
        ]
    }
    fails = matcher._evaluate_skill_year_gates(resume, req)
    assert any(skill == "java" for skill, _, _ in fails)


def test_job_text_truncation_and_location_gate():
    long_desc = "x" * (matcher.MAX_RESUME_CHARS + 50)
    txt = matcher._job_to_full_text("Role", long_desc)
    assert txt.endswith("[truncated]")

    resume = {"contact": {"location": "Austin, TX"}}
    assert matcher._is_location_hard_gate_blocked(resume, "Austin, TX") is False
    assert matcher._is_location_hard_gate_blocked(resume, "Remote") is False
    assert matcher._is_location_hard_gate_blocked(resume, "New York, NY") is True


def test_normalize_and_coverage_helpers():
    toks = matcher._normalize_skill_tokens("Python, Java. PostgreSQL; UnknownTech")
    assert "python" in toks and "java" in toks and "postgresql" in toks
    assert "unknowntech" not in toks

    resume = {
        "skills": {"Languages": ["Python"], "Databases": ["PostgreSQL"]},
        "experience": [{"title": "Backend Engineer", "bullets": ["Built Java APIs"]}],
    }
    assert matcher._skill_coverage_score(resume, "") == 0.7
    cov = matcher._skill_coverage_score(resume, "Need Python Java AWS")
    assert 0.0 <= cov <= 1.0


def test_years_fit_score_helper():
    assert matcher._years_fit_score(None, None) == 0.75
    assert matcher._years_fit_score(None, 5.0) == 0.3
    assert matcher._years_fit_score(6.0, 5.0) == 1.0
    assert matcher._years_fit_score(2.0, 4.0) == 0.5


def test_compute_resume_skill_years_merges_intervals():
    resume = {
        "experience": [
            {"title": "Java Engineer", "start": "Jan 2020", "end": "Dec 2020", "bullets": ["Java services"]},
            {"title": "Backend", "start": "Jun 2020", "end": "Dec 2021", "bullets": ["Built in Java"]},
        ]
    }
    yrs = matcher._compute_resume_skill_years(resume, "java")
    assert yrs == 2.0


def test_semantic_similarity_with_vectors_and_fallback(monkeypatch):
    # Uses provided vectors; no embedding call required.
    score = matcher._semantic_similarity_score("a", "b", resume_embedding=[1.0, 0.0], job_embedding=[1.0, 0.0])
    assert score == 1.0

    monkeypatch.setattr(matcher, "_embed_cached", lambda t: (_ for _ in ()).throw(RuntimeError("embed down")))
    fb = matcher._semantic_similarity_score("resume", "job")
    assert 0.0 <= fb <= 1.0


def test_semantic_similarity_accepts_numpy_vectors():
    score = matcher._semantic_similarity_score(
        "resume",
        "job",
        resume_embedding=np.array([1.0, 0.0], dtype=float),
        job_embedding=np.array([1.0, 0.0], dtype=float),
    )
    assert score == 1.0


def test_llm_match_blocks_on_location_and_skill_years():
    resume = {
        "contact": {"location": "Austin, TX"},
        "experience": [
            {"title": "Java Dev", "start": "Jan 2022", "end": "Dec 2022", "bullets": ["Java APIs"]},
        ],
    }
    out_loc = matcher.llm_match(resume, "Engineer", "General JD", job_location="New York, NY")
    assert out_loc["hard_gate_blocked"] is True
    assert "location mismatch" in out_loc["match_reason"]

    out_skill = matcher.llm_match(resume, "Engineer", "Need 5 years of Java", job_location="Austin, TX")
    assert out_skill["hard_gate_blocked"] is True
    assert "required skills" in out_skill["match_reason"]
