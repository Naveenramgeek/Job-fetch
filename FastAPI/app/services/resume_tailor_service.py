import re
import logging
from typing import Any

from app.services.llm_client import llm_generate_tailored_resume_sections

logger = logging.getLogger(__name__)

LATEX_PREAMBLE = r"""\documentclass[letterpaper,11pt]{article}

\usepackage[empty]{fullpage}
\usepackage{titlesec}
\usepackage{enumitem}
\usepackage[hidelinks]{hyperref}
\usepackage{fancyhdr}
\usepackage[english]{babel}
\usepackage{tabularx}
\input{glyphtounicode}

\pagestyle{fancy}
\fancyhf{}
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0pt}

\addtolength{\oddsidemargin}{-0.5in}
\addtolength{\textwidth}{1in}
\addtolength{\topmargin}{-.7in}
\addtolength{\textheight}{1.0in}

\raggedbottom
\raggedright
\setlength{\tabcolsep}{0in}
\setlist[itemize]{topsep=2pt, itemsep=2pt, parsep=0pt, partopsep=0pt}
\pdfgentounicode=1

\titleformat{\section}
  {\scshape\raggedright\large}
  {}
  {0em}
  {}
  [\vspace{0pt}\hrule height 0.5pt \vspace{-0.7pt}]
\titlespacing{\section}{0pt}{4pt}{4pt}

\newcommand{\resumeItem}[1]{\item \small{#1}}
\newcommand{\resumeSubheading}[4]{
  \item
  \begin{tabularx}{0.97\textwidth}[t]{Xr}
    \textbf{#1} & #2 \\
    \textit{\small #3} & \textit{\small #4} \\
  \end{tabularx}\vspace{-2pt}
}
\newcommand{\resumeProjectHeading}[3]{
  \item
  \begin{tabularx}{0.97\textwidth}[t]{Xr}
    \textbf{#1} & #2 \\
    \textit{\small #3} & \\
  \end{tabularx}\vspace{-2pt}
}
\newcommand{\resumeListStart}{\begin{itemize}[leftmargin=0.15in, label=\textbullet, itemsep=2pt]}
\newcommand{\resumeListEnd}{\end{itemize}}
"""

TAILORING_INSTRUCTIONS = """You are an expert technical recruiter and hiring manager. Optimize my resume for the provided Job Description to achieve 90%+ ATS match.

Create a 3-line professional summary using this structure:

Differentiating identity + years + JD tech stack + scale/context

How I translate requirements into production systems + my productivity advantage (AI-assisted development if relevant)

Ownership + 1–2 concrete metrics aligned with JD priorities

Rewrite experience bullets using Problem -> Solution -> Impact, starting with ownership verbs (Led, Built, Owned, Architected). Every bullet must show technical depth + business impact with metrics.

Integrate exact JD keywords, eliminate buzzwords, ensure each bullet fits within 2 lines, and preserve original LaTeX format.

Highlight leadership, scalability, reliability, and delivery speed. If JD is vague, infer priorities from similar backend/fintech roles.

Goal: pass 10-second scan, show I’ve solved their problems before, and position me as a safe, high-impact hire."""


def _latex_escape(text: Any) -> str:
    s = str(text or "")
    repl = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    for k, v in repl.items():
        s = s.replace(k, v)
    return re.sub(r"\s{2,}", " ", s).strip()


def _format_latex_text(text: Any) -> str:
    s = str(text or "")
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"^\s*(?:[-*•‣◦▪▸–—]+|\d+[.)])\s+", "", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"BOLDOPEN\1BOLDCLOSE", s)
    s = _latex_escape(s)
    s = s.replace("BOLDOPEN", r"\textbf{").replace("BOLDCLOSE", "}")
    return s


def _normalize_lines(lines: Any) -> list[str]:
    if not isinstance(lines, list):
        return []
    out: list[str] = []
    for item in lines:
        txt = _format_latex_text(item)
        if txt:
            out.append(txt)
    return out


def _contact_links(contact: dict[str, Any]) -> str:
    parts: list[str] = []
    phone = _latex_escape(contact.get("phone") or "N/A")
    email = _latex_escape(contact.get("email") or "candidate@example.com")
    parts.append(phone)
    parts.append(rf"\href{{mailto:{email}}}{{{email}}}")
    if contact.get("linkedin"):
        parts.append(rf"\href{{{_latex_escape(contact.get('linkedin'))}}}{{LinkedIn}}")
    if contact.get("github"):
        parts.append(rf"\href{{{_latex_escape(contact.get('github'))}}}{{GitHub}}")
    if contact.get("portfolio"):
        parts.append(rf"\href{{{_latex_escape(contact.get('portfolio'))}}}{{Portfolio}}")
    return " $|$ ".join(parts)


def _experience_sort_key(exp: dict[str, Any]) -> tuple[int, int, int]:
    date_range = str(exp.get("date_range") or "")
    years = [int(y) for y in re.findall(r"\b(?:19|20)\d{2}\b", date_range)]
    is_present = 1 if re.search(r"\b(present|current|now)\b", date_range, flags=re.IGNORECASE) else 0
    end_year = max(years) if years else 0
    start_year = min(years) if years else 0
    return (is_present, end_year, start_year)


def _experience_identity(exp: dict[str, Any]) -> str:
    title = str(exp.get("title") or "").strip().lower()
    company = str(exp.get("company") or "").strip().lower()
    date_range = str(exp.get("date_range") or "").strip().lower()
    return f"{title}|{company}|{date_range}"


def _extract_resume_experience_bullets(exp: dict[str, Any]) -> list[str]:
    bullets = exp.get("bullets")
    if isinstance(bullets, list):
        return [str(b).strip() for b in bullets if str(b or "").strip()]
    if isinstance(bullets, str) and bullets.strip():
        return [bullets.strip()]

    for key in ("highlights", "responsibilities", "description", "summary"):
        val = exp.get(key)
        if isinstance(val, list):
            items = [str(v).strip() for v in val if str(v or "").strip()]
            if items:
                return items
        if isinstance(val, str) and val.strip():
            return [val.strip()]
    return []


def _normalize_resume_experience_item(exp: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": exp.get("title") or exp.get("role") or "Role",
        "company": exp.get("company") or exp.get("organization") or "Company",
        "location": exp.get("location") or "",
        "date_range": exp.get("duration") or f"{exp.get('start') or ''} - {exp.get('end') or ''}".strip(" -"),
        "bullets": _extract_resume_experience_bullets(exp),
    }


def _merge_experience_items(sections: dict[str, Any], resume_data: dict[str, Any]) -> list[dict[str, Any]]:
    llm_items = [e for e in (sections.get("experience") or []) if isinstance(e, dict)]
    normalized_llm: list[dict[str, Any]] = []
    for e in llm_items:
        normalized_llm.append(
            {
                "title": e.get("title") or "Role",
                "company": e.get("company") or "Company",
                "location": e.get("location") or "",
                "date_range": e.get("date_range") or "",
                "bullets": e.get("bullets") or [],
            }
        )

    resume_items_raw = resume_data.get("experience") or []
    normalized_resume = [
        _normalize_resume_experience_item(e)
        for e in resume_items_raw
        if isinstance(e, dict)
    ]

    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in normalized_llm:
        ident = _experience_identity(item)
        if ident in seen:
            continue
        seen.add(ident)
        merged.append(item)

    for item in normalized_resume:
        ident = _experience_identity(item)
        if ident in seen:
            continue
        seen.add(ident)
        merged.append(item)

    # Ensure chronological ordering and keep a practical cap.
    merged = sorted(merged, key=_experience_sort_key, reverse=True)
    return merged[:6]


def _format_certification(cert: Any) -> str:
    if isinstance(cert, dict):
        text = _format_latex_text(cert.get("text") or cert.get("name") or cert.get("title") or "")
        link = str(cert.get("link") or cert.get("url") or "").strip()
        if link:
            href = _latex_escape(link)
            label = text or href
            return rf"\href{{{href}}}{{{label}}}"
        return text
    return _format_latex_text(cert)


def _collect_skill_values(value: Any) -> list[str]:
    out: list[str] = []
    if value is None:
        return out
    if isinstance(value, str):
        txt = value.strip()
        if txt:
            out.extend([p.strip() for p in txt.split(",") if p.strip()])
        return out
    if isinstance(value, list):
        for item in value:
            out.extend(_collect_skill_values(item))
        return out
    if isinstance(value, dict):
        for _, v in value.items():
            out.extend(_collect_skill_values(v))
        return out
    txt = str(value).strip()
    if txt:
        out.append(txt)
    return out


def _skills_from_resume(skills: dict[str, Any], keywords: list[str]) -> list[str]:
    matches: list[str] = []
    all_values: list[str] = []
    for k, v in skills.items():
        key_norm = str(k or "").lower()
        vals = _collect_skill_values(v)
        all_values.extend(vals)
        if any(word in key_norm for word in keywords):
            matches.extend(vals)

    chosen = matches if matches else all_values
    deduped: list[str] = []
    seen: set[str] = set()
    for item in chosen:
        item_norm = item.strip().lower()
        if not item_norm or item_norm in seen:
            continue
        seen.add(item_norm)
        deduped.append(item.strip())
    return deduped[:12]


def _fallback_structured_sections(resume_data: dict[str, Any], job_title: str) -> dict[str, Any]:
    summary_line = f"Targeting {job_title or 'software engineering role'} with production backend experience."
    exp = resume_data.get("experience") or []
    projects = resume_data.get("projects") or []
    skills = resume_data.get("skills") or {}
    return {
        "summary_lines": [summary_line, "Strong ownership in delivery, reliability, and scale.", "Hands-on in APIs, data, and CI/CD automation."],
        "experience": [
            {
                "title": e.get("title") or "Role",
                "company": e.get("company") or "Company",
                "location": e.get("location") or "",
                "date_range": e.get("duration") or f"{e.get('start') or ''} - {e.get('end') or ''}".strip(" -"),
                "bullets": (e.get("bullets") or [])[:3],
            }
            for e in exp[:3]
            if isinstance(e, dict)
        ],
        "projects": [
            {
                "name": p.get("name") or "Project",
                "date": p.get("date") or "",
                "tech_stack": p.get("tech_stack") or "",
                "bullets": (p.get("bullets") or [])[:3],
            }
            for p in projects[:2]
            if isinstance(p, dict)
        ],
        "skills": {
            "languages": ", ".join((skills.get("Languages") or skills.get("languages") or [])[:8]) if isinstance(skills, dict) else "",
            "frameworks": ", ".join((skills.get("Frameworks") or skills.get("frameworks") or [])[:8]) if isinstance(skills, dict) else "",
            "cloud_devops": ", ".join((skills.get("Cloud/DevOps") or skills.get("cloud_devops") or [])[:8]) if isinstance(skills, dict) else "",
            "databases": ", ".join((skills.get("Databases") or skills.get("databases") or [])[:8]) if isinstance(skills, dict) else "",
            "tools": ", ".join((skills.get("Tools") or skills.get("tools") or [])[:8]) if isinstance(skills, dict) else "",
        },
    }


def _render_latex(resume_data: dict[str, Any], sections: dict[str, Any]) -> str:
    contact = resume_data.get("contact") or {}
    name = _format_latex_text(contact.get("name") or "Candidate Name")
    header_links = _contact_links(contact)

    summary_lines = _normalize_lines(sections.get("summary_lines") or [])
    summary_text = " ".join(summary_lines) if summary_lines else _format_latex_text(resume_data.get("summary") or "")

    exp_items = _merge_experience_items(sections, resume_data)
    exp_blocks: list[str] = []
    for e in exp_items[:6]:
        title = _format_latex_text(e.get("title") or "Role")
        company = _format_latex_text(e.get("company") or "Company")
        location = _format_latex_text(e.get("location") or "")
        date_range = _format_latex_text(e.get("date_range") or "")
        bullets = _normalize_lines(e.get("bullets") or [])[:4]
        if not bullets:
            continue
        bullet_lines = "\n".join([rf"  \resumeItem{{{b}}}" for b in bullets])
        exp_blocks.append(
            rf"""\resumeSubheading
  {{{title}}}{{{date_range}}}
  {{{company}}}{{{location}}}
\resumeListStart
{bullet_lines}
\resumeListEnd"""
        )

    proj_items = sections.get("projects") or []
    proj_blocks: list[str] = []
    for p in proj_items[:3]:
        if not isinstance(p, dict):
            continue
        pname = _format_latex_text(p.get("name") or "Project")
        pdate = _format_latex_text(p.get("date") or "")
        ptech = _format_latex_text(p.get("tech_stack") or "")
        bullets = _normalize_lines(p.get("bullets") or [])[:3]
        if not bullets:
            continue
        bullet_lines = "\n".join([rf"  \resumeItem{{{b}}}" for b in bullets])
        proj_blocks.append(
            rf"""\resumeProjectHeading
  {{{pname}}}{{{pdate}}}
  {{Technologies: {ptech}}}
\resumeListStart
{bullet_lines}
\resumeListEnd"""
        )

    edu_items = resume_data.get("education") or []
    edu_blocks: list[str] = []
    for e in edu_items[:3]:
        if not isinstance(e, dict):
            continue
        degree = _format_latex_text(e.get("degree") or "Degree")
        grad = _format_latex_text(e.get("graduation") or e.get("duration") or "")
        school = _format_latex_text(e.get("institution") or "Institution")
        honors = _format_latex_text(e.get("gpa") or e.get("location") or "")
        edu_blocks.append(
            rf"""\resumeSubheading
  {{{degree}}}{{{grad}}}
  {{{school}}}{{{honors}}}"""
        )

    sk = sections.get("skills") if isinstance(sections.get("skills"), dict) else {}
    skills = resume_data.get("skills") if isinstance(resume_data.get("skills"), dict) else {}

    def _skills_value(primary_key: str, fallback_keys: list[str], keywords: list[str]) -> str:
        val = _format_latex_text(sk.get(primary_key) or "")
        if val:
            return val
        for k in fallback_keys:
            raw = skills.get(k)
            if isinstance(raw, list) and raw:
                return _format_latex_text(", ".join(raw[:12]))
            if isinstance(raw, dict):
                nested = _collect_skill_values(raw)
                if nested:
                    return _format_latex_text(", ".join(nested[:12]))
            if isinstance(raw, str) and raw.strip():
                return _format_latex_text(raw)
        inferred = _skills_from_resume(skills, keywords)
        if inferred:
            return _format_latex_text(", ".join(inferred))
        return ""

    languages = _skills_value("languages", ["Languages", "languages"], ["language"])
    frameworks = _skills_value("frameworks", ["Frameworks", "frameworks", "Frameworks/Libraries"], ["framework", "library"])
    cloud_devops = _skills_value("cloud_devops", ["Cloud/DevOps", "cloud_devops", "cloud", "devops"], ["cloud", "devops", "kubernetes", "docker", "aws", "gcp", "azure", "terraform", "jenkins", "ci/cd"])
    databases = _skills_value("databases", ["Databases", "databases", "database"], ["database", "sql", "postgres", "mysql", "mongodb", "redis"])
    tools = _skills_value("tools", ["Tools", "tools"], ["tool", "testing", "monitoring", "git"])

    certs = resume_data.get("certifications") or []
    cert_lines = []
    for c in certs[:6]:
        txt = _format_certification(c)
        if txt:
            cert_lines.append(rf"\item {txt}")
    if not cert_lines:
        cert_lines = [r"\item N/A"]

    exp_content = chr(10).join(exp_blocks) if exp_blocks else r"\item \small{No experience entries available.}"
    proj_content = chr(10).join(proj_blocks) if proj_blocks else r"\item \small{No project entries available.}"
    edu_content = chr(10).join(edu_blocks) if edu_blocks else r"\item \small{No education entries available.}"
    cert_content = chr(10).join(cert_lines)

    return rf"""{LATEX_PREAMBLE}

\begin{{document}}

\begin{{center}}
    \textbf{{\Huge \scshape {name}}} \\ \vspace{{2pt}}
    \small {header_links}
\end{{center}}

\section{{Professional Summary}}
\small{{{summary_text}}}

\section{{Work Experience}}
\begin{{itemize}}[leftmargin=0in, label={{}}]
{exp_content}
\end{{itemize}}

\section{{Projects}}
\begin{{itemize}}[leftmargin=0in, label={{}}]
{proj_content}
\end{{itemize}}

\section{{Education}}
\begin{{itemize}}[leftmargin=0in, label={{}}]
{edu_content}
\end{{itemize}}

\section{{Technical Skills}}
\begin{{itemize}}[leftmargin=0.15in, label={{}}]
\small{{
\item{{
\textbf{{Languages:}} {languages} \\
\textbf{{Frameworks:}} {frameworks} \\
\textbf{{Cloud/DevOps:}} {cloud_devops} \\
\textbf{{Databases:}} {databases} \\
\textbf{{Tools:}} {tools} \\
}}
}}
\end{{itemize}}

\section{{Certifications}}
\begin{{itemize}}[leftmargin=0.15in]
{cert_content}
\end{{itemize}}

\end{{document}}
"""


def generate_tailored_latex(
    resume_data: dict[str, Any],
    job_title: str,
    job_description: str,
) -> str:
    try:
        sections = llm_generate_tailored_resume_sections(
            resume_data=resume_data,
            job_title=job_title,
            job_description=job_description,
            tailoring_instructions=TAILORING_INSTRUCTIONS,
        )
        return _render_latex(resume_data, sections)
    except Exception as e:
        logger.warning("LLM tailoring failed, using fallback structured sections: %s", e)
        return _render_latex(resume_data, _fallback_structured_sections(resume_data, job_title))
