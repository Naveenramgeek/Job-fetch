import app.services.llm_client as llm


def test_call_bedrock_llm_tries_typo_fallback_model(monkeypatch):
    class _Client:
        def __init__(self):
            self.calls = 0

        def converse(self, modelId, messages, inferenceConfig):
            self.calls += 1
            if "ministral" in modelId:
                raise RuntimeError("bad model id")
            return {"output": {"message": {"content": [{"text": "ok-response"}]}}}

    fake = _Client()
    monkeypatch.setattr(llm, "boto3", type("B", (), {"client": lambda *args, **kwargs: fake}))
    monkeypatch.setattr(llm.settings, "bedrock_llm_model_id", "mistral.ministral-3-8b-instruct")
    monkeypatch.setattr(llm.settings, "aws_region", "us-west-2")
    out = llm._call_bedrock_llm("prompt")
    assert out == "ok-response"
    assert fake.calls == 2


def test_call_bedrock_llm_raises_when_all_models_fail(monkeypatch):
    class _Client:
        def converse(self, modelId, messages, inferenceConfig):
            raise RuntimeError("always fail")

    monkeypatch.setattr(llm, "boto3", type("B", (), {"client": lambda *args, **kwargs: _Client()}))
    monkeypatch.setattr(llm.settings, "bedrock_llm_model_id", "mistral.ministral-3-8b-instruct")
    monkeypatch.setattr(llm.settings, "aws_region", "us-west-2")
    try:
        llm._call_bedrock_llm("prompt")
        assert False, "expected failure"
    except RuntimeError:
        pass


def test_is_llm_enabled(monkeypatch):
    monkeypatch.setattr(llm.settings, "bedrock_llm_enabled", True)
    monkeypatch.setattr(llm.settings, "bedrock_llm_model_id", "mistral.x")
    monkeypatch.setattr(llm.settings, "aws_region", "us-west-2")
    assert llm.is_llm_enabled() is True


def test_llm_match_resume_job_parses_json_score_0_to_100(monkeypatch):
    monkeypatch.setattr(llm, "_call_bedrock_llm", lambda prompt: '{"match_score": 85, "match_reason": "good fit"}')
    score, reason = llm.llm_match_resume_job("resume", "title", "jd")
    assert score == 0.85
    assert reason == "good fit"


def test_llm_match_resume_job_parses_regex_fallback(monkeypatch):
    monkeypatch.setattr(
        llm,
        "_call_bedrock_llm",
        lambda prompt: 'Result:\n "match_score": 0.72, "match_reason": "solid skills"',
    )
    score, reason = llm.llm_match_resume_job("resume", "title", "jd")
    assert score == 0.72
    assert "solid skills" in reason


def test_llm_assign_category_returns_slug_or_none(monkeypatch):
    monkeypatch.setattr(llm, "_call_bedrock_llm", lambda prompt: "software_engineer")
    assert llm.llm_assign_category("Backend Engineer", ["software_engineer", "data_scientist"]) == "software_engineer"
    monkeypatch.setattr(llm, "_call_bedrock_llm", lambda prompt: "none")
    assert llm.llm_assign_category("Backend Engineer", ["software_engineer"]) is None


def test_llm_suggest_generic_slug_json_and_fallback(monkeypatch):
    monkeypatch.setattr(llm, "_call_bedrock_llm", lambda prompt: '{"slug":"ML Engineer","display_name":"ML Engineer"}')
    slug, display = llm.llm_suggest_generic_slug("Machine Learning Engineer")
    assert slug == "ml_engineer"
    assert display == "ML Engineer"

    monkeypatch.setattr(llm, "_call_bedrock_llm", lambda prompt: "not-json")
    slug2, display2 = llm.llm_suggest_generic_slug("Site Reliability Engineer")
    assert slug2.startswith("site_reliability")
    assert "Site Reliability Engineer" == display2


def test_llm_suggest_generic_slug_empty_title():
    slug, display = llm.llm_suggest_generic_slug("")
    assert slug == "general"
    assert display == "General"


def test_llm_suggest_generic_slug_json_decode_warning_path(monkeypatch):
    monkeypatch.setattr(llm, "_call_bedrock_llm", lambda prompt: "{bad-json}")
    slug, display = llm.llm_suggest_generic_slug("ML Engineer")
    assert slug.startswith("ml_engineer")


def test_llm_generate_tailored_resume_latex_strips_fences(monkeypatch):
    monkeypatch.setattr(llm, "_call_bedrock_llm", lambda prompt, timeout=120.0: "```latex\n\\documentclass{article}\n```")
    out = llm.llm_generate_tailored_resume_latex({}, "title", "jd", "template", "instructions")
    assert out.startswith("\\documentclass")


def test_llm_generate_tailored_resume_sections_validates_and_retries(monkeypatch):
    resume_data = {
        "experience": [
            {"title": "Engineer", "company": "ACME", "bullets": ["a", "b"]},
        ],
        "projects": [{"name": "P1"}],
    }
    responses = iter(
        [
            '{"summary_lines":["only one"],"experience":[],"projects":[],"skills":{}}',
            """{
              "summary_lines": ["one", "two", "three"],
              "experience": [{"title":"Engineer","company":"ACME","location":"Remote","date_range":"2024-Present","bullets":["x","y"]}],
              "projects": [{"name":"P1","date":"","tech_stack":"","bullets":["a","b"]}],
              "skills": {"languages":"Python","frameworks":"FastAPI","cloud_devops":"AWS","databases":"Postgres","tools":"Git"}
            }""",
        ]
    )
    monkeypatch.setattr(llm, "_call_bedrock_llm", lambda prompt, timeout=120.0: next(responses))
    out = llm.llm_generate_tailored_resume_sections(resume_data, "Backend Engineer", "JD", "instructions")
    assert len(out["summary_lines"]) == 3
    assert len(out["experience"]) == 1


def test_llm_generate_tailored_resume_sections_raises_after_retries(monkeypatch):
    resume_data = {"experience": [{"title": "Engineer", "company": "ACME"}], "projects": []}
    monkeypatch.setattr(llm, "_call_bedrock_llm", lambda prompt, timeout=120.0: "not json")
    try:
        llm.llm_generate_tailored_resume_sections(resume_data, "Backend Engineer", "JD", "instructions")
        assert False, "expected ValueError"
    except ValueError:
        pass
