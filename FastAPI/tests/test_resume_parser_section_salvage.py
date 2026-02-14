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


def test_build_resume_object_parses_mm_yyyy_experience_line(monkeypatch):
    raw_text = """
John Doe
john@example.com

EXPERIENCE
DevOps Engineer, MetLife 10/2024 - Present | Remote, USA
- Built CI/CD pipelines for microservices.
"""

    monkeypatch.setattr(rp, "extract_text_from_pdf", lambda _path, ocr_fallback=True: raw_text)
    data = rp.build_resume_object("dummy.pdf", ocr_fallback=False)

    assert len(data["experience"]) == 1
    exp = data["experience"][0]
    assert exp["title"] == "DevOps Engineer"
    assert exp["company"] == "MetLife"
    assert exp["location"] == "Remote, USA"
    assert exp["start"] == "10/2024"
    assert exp["end"].lower() == "present"


def test_parse_skills_keeps_commas_inside_parentheses():
    parsed = rp.parse_skills(
        "Cloud Platforms: AWS (CloudFormation, Cost Explorer, Config), Azure (Key Vault, DevOps), Terraform"
    )
    assert "Cloud Platforms" in parsed
    assert parsed["Cloud Platforms"] == [
        "AWS (CloudFormation, Cost Explorer, Config)",
        "Azure (Key Vault, DevOps)",
        "Terraform",
    ]


def test_extract_contact_recovers_missing_open_paren_in_phone():
    text = "Jane Doe\njane@example.com\nPhone: 913) 749-8473\n"
    contact = rp.extract_contact(text)
    assert contact["phone"] == "(913) 749-8473"


def test_enrich_contact_from_hidden_links():
    contact = {"email": None, "linkedin": None, "github": None}
    links = [
        ("LinkedIn", "linkedin.com/in/janedoe"),
        ("GitHub", "github.com/janedoe"),
        ("Email", "mailto:janedoe@example.com"),
    ]

    rp._enrich_contact_from_links(contact, links)

    assert contact["linkedin"] == "https://linkedin.com/in/janedoe"
    assert contact["github"] == "https://github.com/janedoe"
    assert contact["email"] == "janedoe@example.com"


def test_attach_links_to_projects_and_certs():
    projects = [
        rp.ProjectItem(name="JobFetch", bullets=["Built parser"], link=None),
        rp.ProjectItem(name="Infra", bullets=["IaC"], link=None),
    ]
    certs = [
        {"text": "AWS Certified Developer", "link": None},
        {"text": "Terraform Associate", "link": None},
    ]
    links = [
        ("GitHub", "https://github.com/user/jobfetch"),
        ("Project Website", "https://jobfetch.example.com"),
        ("Credential", "https://www.credly.com/badges/abc"),
    ]

    rp._attach_links_to_projects_and_certs(projects, certs, links, set())

    assert projects[0].link == "https://github.com/user/jobfetch"
    assert projects[1].link == "https://jobfetch.example.com"
    assert certs[0]["link"] == "https://www.credly.com/badges/abc"


def test_hidden_contact_link_replaces_short_visible_link():
    contact = {
        "email": "naveenvemula2487@gmail.com",
        "linkedin": "linkedin.com/in/naveen-vemula",
        "github": "github.com/Naveenramgeek",
    }
    links = [
        ("LinkedIn", "https://www.linkedin.com/in/naveen-vemula/?trk=public_profile"),
        ("GitHub", "https://github.com/Naveenramgeek?tab=repositories"),
    ]

    rp._enrich_contact_from_links(contact, links)

    assert contact["linkedin"] == "https://www.linkedin.com/in/naveen-vemula/?trk=public_profile"
    assert contact["github"] == "https://github.com/Naveenramgeek?tab=repositories"


def test_parse_experience_supports_dash_company_and_pre():
    parsed = rp.parse_experience(
        "Full Stack Developer — Federal soft systems Jan 2025 - Pre\n"
        "- Built cloud-native services on AWS.\n"
    )
    assert len(parsed) == 1
    assert parsed[0].title == "Full Stack Developer"
    assert parsed[0].company == "Federal soft systems"
    assert parsed[0].start == "Jan 2025"
    assert parsed[0].end in {"Pre", "Pres", "Present"}


def test_attach_links_does_not_duplicate_same_cert_url_across_multiple_certs():
    projects = []
    certs = [
        {"text": "IBM Generative AI for Software Development", "link": None},
        {"text": "HackMidwest Winner", "link": None},
    ]
    links = [
        ("Certificate", "https://coursera.org/share/abc123"),
        ("Certificate", "https://coursera.org/share/abc123"),  # duplicate source URL
    ]

    rp._attach_links_to_projects_and_certs(projects, certs, links, set())

    assigned = [c.get("link") for c in certs if c.get("link")]
    assert assigned == ["https://coursera.org/share/abc123"]


def test_attach_links_matches_cert_links_by_text_not_input_order():
    projects = []
    certs = [
        {"text": "AWS Certified Developer Associate", "link": None},
        {"text": "IBM Generative AI for Software Development", "link": None},
    ]
    # Intentionally reversed order; mapping should still follow anchor/text similarity.
    links = [
        ("IBM Generative AI certificate", "https://coursera.org/share/ibm123"),
        ("AWS Certified Developer badge", "https://www.credly.com/badges/aws456"),
    ]

    rp._attach_links_to_projects_and_certs(projects, certs, links, set())

    assert certs[0]["link"] == "https://www.credly.com/badges/aws456"
    assert certs[1]["link"] == "https://coursera.org/share/ibm123"


def test_attach_links_matches_project_links_by_project_name():
    projects = [
        rp.ProjectItem(name="JobFetch Agent", bullets=["Parser app"], link=None),
        rp.ProjectItem(name="Retail Pricing Dashboard", bullets=["Visualization"], link=None),
    ]
    certs = []
    # Order does not align with project order; text similarity should align links.
    links = [
        ("Retail Pricing Dashboard - GitHub", "https://github.com/user/retail-pricing-dashboard"),
        ("JobFetch Agent Repository", "https://github.com/user/jobfetch-agent"),
    ]

    rp._attach_links_to_projects_and_certs(projects, certs, links, set())

    assert projects[0].link == "https://github.com/user/jobfetch-agent"
    assert projects[1].link == "https://github.com/user/retail-pricing-dashboard"
