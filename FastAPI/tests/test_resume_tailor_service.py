import app.services.resume_tailor_service as rts
from app.services.resume_tailor_service import _render_latex


def test_render_latex_handles_markdown_bold_and_bullet_cleanup():
    resume_data = {
        "contact": {"name": "User", "email": "user@example.com"},
        "education": [],
        "certifications": [],
        "skills": {},
    }
    sections = {
        "summary_lines": ["**Strong** backend engineer"],
        "experience": [
            {
                "title": "Engineer",
                "company": "ACME",
                "location": "Remote",
                "date_range": "2024 - Present",
                "bullets": ["- built APIs", "• improved latency"],
            }
        ],
        "projects": [],
        "skills": {"languages": "Python"},
    }
    latex = _render_latex(resume_data, sections)
    assert r"\textbf{Strong}" in latex
    assert "- built APIs" not in latex
    assert "built APIs" in latex


def test_render_latex_infers_skills_from_nested_resume_structure():
    resume_data = {
        "contact": {"name": "User", "email": "user@example.com"},
        "education": [],
        "certifications": [],
        "skills": {
            "Core Skills": {
                "Languages": ["Python", "TypeScript"],
                "Cloud/DevOps": ["AWS", "Docker", "Kubernetes"],
                "Databases": ["PostgreSQL"],
            }
        },
    }
    sections = {
        "summary_lines": ["summary one", "summary two", "summary three"],
        "experience": [
            {
                "title": "Engineer",
                "company": "ACME",
                "location": "Remote",
                "date_range": "2024 - Present",
                "bullets": ["Built services"],
            }
        ],
        "projects": [],
        "skills": {},
    }
    latex = _render_latex(resume_data, sections)
    assert "Python" in latex
    assert "AWS" in latex
    assert "PostgreSQL" in latex


def test_tailor_helper_functions_coverage():
    assert rts._latex_escape("a_b&c") == r"a\_b\&c"
    assert rts._format_latex_text("- **Bold** item").startswith(r"\textbf{Bold}")
    assert rts._normalize_lines([" x ", "", None]) == ["x"]
    links = rts._contact_links({"phone": "123", "email": "a@b.com", "github": "https://github.com/me"})
    assert "mailto" in links and "GitHub" in links
    assert rts._experience_sort_key({"date_range": "2022 - Present"})[0] == 1
    assert "role|co|" == rts._experience_identity({"title": "Role", "company": "Co", "date_range": ""})


def test_experience_merge_and_bullet_extract():
    resume_data = {
        "experience": [
            {"title": "E1", "company": "C1", "duration": "2020 - 2021", "highlights": ["h1", "h2"]},
            {"title": "E2", "company": "C2", "start": "2022", "end": "Present", "description": "did x"},
        ]
    }
    sections = {
        "experience": [
            {"title": "E2", "company": "C2", "date_range": "2022 - Present", "bullets": ["b1", "b2"]}
        ]
    }
    merged = rts._merge_experience_items(sections, resume_data)
    assert len(merged) >= 2
    assert any(m["title"] == "E1" for m in merged)


def test_skills_collect_and_infer():
    vals = rts._collect_skill_values({"a": ["Python", {"x": "AWS, Docker"}], "b": "Postgres"})
    assert "Python" in vals and "AWS" in vals and "Postgres" in vals
    inferred = rts._skills_from_resume(
        {"Cloud/DevOps": ["AWS", "Docker"], "Languages": ["Python"]},
        ["cloud", "devops"],
    )
    assert "AWS" in inferred


def test_fallback_sections_and_generate_tailored_fallback(monkeypatch):
    resume = {"experience": [{"title": "Eng", "company": "ACME", "bullets": ["x"]}], "projects": [], "skills": {}}
    fb = rts._fallback_structured_sections(resume, "Backend Engineer")
    assert len(fb["summary_lines"]) == 3
    monkeypatch.setattr(rts, "llm_generate_tailored_resume_sections", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("llm down")))
    out = rts.generate_tailored_latex(resume, "Backend Engineer", "JD")
    assert "\\section{Work Experience}" in out


def test_format_certification_variants_and_project_education_blocks():
    c1 = rts._format_certification({"text": "AWS Cert", "link": "https://aws.amazon.com"})
    c2 = rts._format_certification("Plain Cert")
    assert "\\href{" in c1
    assert "Plain Cert" in c2

    resume_data = {
        "contact": {"name": "User", "email": "user@example.com"},
        "education": [{"degree": "MS", "institution": "Uni", "duration": "2020-2022", "gpa": "4.0"}],
        "certifications": [{"name": "Cert", "url": "https://cert.example.com"}],
        "skills": {"Languages": ["Python"], "Frameworks": {"backend": ["FastAPI"]}},
    }
    sections = {
        "summary_lines": ["one", "two", "three"],
        "experience": [{"title": "Eng", "company": "ACME", "date_range": "2022-Present", "bullets": ["Did A", "Did B"]}],
        "projects": [{"name": "P1", "date": "2024", "tech_stack": "Python", "bullets": ["b1", "b2"]}, "invalid"],
        "skills": {},
    }
    latex = rts._render_latex(resume_data, sections)
    assert "Technologies: Python" in latex
    assert "Certifications" in latex


def test_generate_tailored_success_and_collect_scalar_skill_values(monkeypatch):
    resume = {"contact": {"name": "User", "email": "user@example.com"}, "education": [], "certifications": [], "skills": {}}
    sections = {
        "summary_lines": ["one", "two", "three"],
        "experience": [{"title": "Eng", "company": "ACME", "date_range": "2022-Present", "bullets": ["Did A", "Did B"]}],
        "projects": [],
        "skills": {"tools": "Git"},
    }
    monkeypatch.setattr(rts, "llm_generate_tailored_resume_sections", lambda **kwargs: sections)
    out = rts.generate_tailored_latex(resume, "Backend Engineer", "JD")
    assert "\\begin{document}" in out
    vals = rts._collect_skill_values(123)
    assert vals == ["123"]
