import parser.resume_parser as rp


def test_build_resume_object_salvages_experience_when_strict_parse_misses(monkeypatch):
    raw_text = """
John Doe
john@example.com

EXPERIENCE
Full Stack Developer - Federal Soft Systems Jan 2025 - Present
- Built cloud-native services on AWS.
- Improved API latency by 50%.
"""

    monkeypatch.setattr(rp, "extract_text_from_pdf", lambda _path, ocr_fallback=True: raw_text)
    data = rp.build_resume_object("dummy.pdf", ocr_fallback=False)

    assert len(data["experience"]) >= 1
    assert any("Full Stack Developer" in (x.get("title") or "") for x in data["experience"])
    assert not any((x.get("reason") == "experience_parse_failed") for x in data["other"])


def test_build_resume_object_salvages_education_when_strict_parse_misses(monkeypatch):
    raw_text = """
Jane Doe
jane@example.com

EDUCATION
Master of Science in Computer Science, University of Texas, Austin
Bachelor of Engineering in CSE, Anna University
"""

    monkeypatch.setattr(rp, "extract_text_from_pdf", lambda _path, ocr_fallback=True: raw_text)
    data = rp.build_resume_object("dummy.pdf", ocr_fallback=False)

    assert len(data["education"]) >= 1
    assert any("Master of Science" in (x.get("degree") or "") for x in data["education"])
    assert not any((x.get("reason") == "education_parse_failed") for x in data["other"])
