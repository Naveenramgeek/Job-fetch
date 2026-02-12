# ---------------------------
# Regex
# ---------------------------
from dataclasses import asdict
import re
from typing import Dict, List, Optional, Tuple

from .models import OtherBlock, ExperienceItem, EducationItem, ProjectItem


EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(\+?\d{1,3}[\s.-]?)?(\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}")
URL_RE = re.compile(r"(https?://\S+|www\.\S+|\bgithub\.com/\S+|\blinkedin\.com/\S+)", re.IGNORECASE)

MONTH = r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
DATE_TOKEN = rf"({MONTH}\s+\d{{4}}|\d{{4}}|Present)"
DATE_RANGE_RE = re.compile(rf"(?P<start>{DATE_TOKEN})\s*[-–to]+\s*(?P<end>{DATE_TOKEN})", re.IGNORECASE)

DEGREE_RE = re.compile(
    r"\b(MS|M\.S\.|Master|MTech|M\.Tech|MBA|PhD|Bachelors|Bachelor|B\.E\.|B\.Tech|BE|BS|B\.S\.)\b",
    re.IGNORECASE,
)

GPA_TOKEN_RE = re.compile(
    r"\b(C?GPA)\s*[:\-]?\s*(\d+(?:\.\d+)?)(?:\s*/\s*(\d+(?:\.\d+)?))?\b",
    re.IGNORECASE,
)

# bullets in resumes vary a lot
BULLET_CHARS = ("•", "-", "●", "◦", "▪", "–", "·", "o")
NUMBERED_BULLET_RE = re.compile(r"^\(?\d{1,3}[.)]\s+")

# ---------------------------
# Section aliases (expand as you learn)
# ---------------------------
SECTION_ALIASES = {
    "summary": ["summary", "professional summary", "profile", "objective"],
    "experience": [
        "experience", "work experience", "employment", "professional experience",
        "marketing experience", "relevant experience", "career history"
    ],
    "education": ["education", "academics", "academic background"],
    "skills": ["skills", "technical skills", "core skills", "tools", "technologies", "expertise", "technical expertise"],
    "projects": ["projects", "project experience", "academic projects", "key projects"],
    "certifications": [
        "certifications", "certificates", "licenses",
        "achievements", "awards",
        "certifications and awards", "certifications & awards", "certifications & achievements"
    ],
}

CANONICAL_SECTIONS = set(SECTION_ALIASES.keys())

# ---------------------------
# Text extraction + normalization
# ---------------------------
def normalize_text(text: str) -> str:
    text = text.replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    # fix hyphenated line breaks: "engi-\nneer" -> "engineer"
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    return text.strip()


def normalize_inline_text(text: str) -> str:
    """Collapse wrapped/newline text into a single line."""
    if not text:
        return ""
    text = text.replace("\r", " ").replace("\n", " ")
    return re.sub(r"\s{2,}", " ", text).strip()


def extract_text_from_pdf(pdf_path: str, ocr_fallback: bool = True) -> str:
    try:
        import pdfplumber
    except ImportError as e:
        raise RuntimeError("Missing dependency: pdfplumber. Install: pip install pdfplumber") from e

    pages: List[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")

    text = "\n".join(pages).strip()

    if ocr_fallback and (len(text) < 400 or _looks_like_scanned_pdf(pages)):
        try:
            import pytesseract
            from pdf2image import convert_from_path
        except ImportError as e:
            raise RuntimeError(
                "OCR fallback needs: pytesseract + pdf2image (+ poppler). "
                "Install: pip install pytesseract pdf2image ; brew install tesseract poppler"
            ) from e

        images = convert_from_path(pdf_path, dpi=300)
        text = "\n".join(pytesseract.image_to_string(img) for img in images).strip()

    return normalize_text(text)


def _looks_like_scanned_pdf(text_pages: List[str]) -> bool:
    low = sum(1 for t in text_pages if len((t or "").strip()) < 40)
    return low >= max(1, int(0.6 * len(text_pages)))


# ---------------------------
# Contact extraction (deterministic)
# ---------------------------
def _first_match(rx: re.Pattern, text: str) -> Optional[str]:
    m = rx.search(text)
    return m.group(0) if m else None


def extract_contact(text: str) -> Dict[str, Optional[str]]:
    email = _first_match(EMAIL_RE, text)
    phone = _first_match(PHONE_RE, text)
    urls = URL_RE.findall(text)

    linkedin = next((u for u in urls if "linkedin.com" in u.lower()), None)
    github = next((u for u in urls if "github.com" in u.lower()), None)

    # Name heuristic: first non-empty line that doesn't look like contact/link/heading
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    name = None
    for l in lines[:12]:
        if EMAIL_RE.search(l) or PHONE_RE.search(l) or "linkedin" in l.lower() or "github" in l.lower():
            continue
        if match_heading(l.lower()):
            continue
        if 1 <= len(l.split()) <= 5 and re.search(r"[A-Za-z]", l):
            name = l
            break

    return {
        "name": name,
        "email": email,
        "phone": phone,
        "linkedin": linkedin,
        "github": github,
        "location": None,  # don't guess
        "title": None,  # e.g. Software Engineer, Sr DevOps Engineer; used for job fetching
    }


# ---------------------------
# Heading detection + section splitting
# ---------------------------
def normalize_heading(s: str) -> str:
    s = s.lower().strip()
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z\s]", "", s)
    s = re.sub(r"\s{2,}", " ", s).strip()
    return s


def match_heading(line_lower: str) -> Optional[str]:
    """
    Returns canonical section name if line matches known aliases; else None.
    """
    norm = normalize_heading(line_lower)
    for canon, aliases in SECTION_ALIASES.items():
        for a in aliases:
            if norm == normalize_heading(a):
                return canon
    return None


def is_heading_like(line: str) -> bool:
    """
    Heuristic for unknown headings:
    - Mostly uppercase or Title Case
    - short-ish
    - few punctuation
    Examples: "CERTIFICATIONS & AWARDS", "MARKETING EXPERIENCE", "TECHNICAL EXPERTISE"
    """
    s = line.strip()
    if not s:
        return False
    if len(s) > 70:
        return False
    # if contains too many digits, likely not a heading
    if sum(ch.isdigit() for ch in s) >= 4:
        return False
    letters = [ch for ch in s if ch.isalpha()]
    if not letters:
        return False
    upper_ratio = sum(ch.isupper() for ch in letters) / max(1, len(letters))
    # allow Title Case too
    looks_title = (len(s.split()) <= 6 and all(w[:1].isupper() for w in s.split() if w[:1].isalpha()))
    return upper_ratio >= 0.65 or looks_title


def split_sections_with_unknowns(text: str) -> Tuple[Dict[str, str], List[OtherBlock]]:
    lines = text.splitlines()

    # Pass 1: find ONLY recognized headings with their indices
    recognized: List[Tuple[int, str, str]] = []  # (idx, raw_heading, canon)
    for i, raw in enumerate(lines):
        line = raw.strip()
        if not line:
            continue
        canon = match_heading(line.lower())
        if canon:
            recognized.append((i, line, canon))

    if not recognized:
        body = normalize_text(text)
        return {"unknown": body}, [OtherBlock(heading=None, source_section=None, reason="no_headings_found", text=body)]

    recognized.sort(key=lambda x: x[0])

    sections: Dict[str, str] = {}
    other_blocks: List[OtherBlock] = []

    # Anything before the first recognized heading becomes "other" (usually header/contact)
    first_idx = recognized[0][0]
    preface = normalize_text("\n".join(lines[:first_idx]).strip())
    if preface:
        other_blocks.append(OtherBlock(
            heading="Header",
            source_section=None,
            reason="content_before_first_heading",
            text=preface
        ))

    # Pass 2: extract each recognized section body
    for k, (start_idx, raw_heading, canon) in enumerate(recognized):
        end_idx = recognized[k + 1][0] if k + 1 < len(recognized) else len(lines)
        body = normalize_text("\n".join(lines[start_idx + 1 : end_idx]).strip())
        if not body:
            continue
        if canon not in sections:
            sections[canon] = body
        else:
            sections[canon] = normalize_text(sections[canon] + "\n\n" + body)

    # Pass 3 (optional): find unknown headings ONLY outside recognized sections
    # In this resume, it's not needed; UI fallback is handled by "other" + parse failures.

    return sections, other_blocks


# ---------------------------
# Bullet utilities
# ---------------------------
def is_bullet(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    return s.startswith(BULLET_CHARS) or bool(NUMBERED_BULLET_RE.match(s))


def clean_bullet(s: str) -> str:
    s = s.strip()
    s = s.lstrip("".join(BULLET_CHARS)).strip()
    s = NUMBERED_BULLET_RE.sub("", s).strip()
    # common PDF artifacts
    s = s.replace(" mplemented", " implemented").replace("mplemented", "implemented")
    return normalize_inline_text(s)


def parse_date_range(duration: str) -> Tuple[Optional[str], Optional[str]]:
    if not duration:
        return None, None
    m = DATE_RANGE_RE.search(duration)
    if not m:
        return None, None
    return m.group("start"), m.group("end")


# ---------------------------
# Experience parsing (multi-format)
# ---------------------------

# Style A (your resume): "Software Engineer II (Software AG) Jan 2024 – Jun 2024"
EXP_HDR_PAREN_SINGLE = re.compile(
    rf"^(?P<title>.+?)\s*\((?P<company>.+?)\)\s+(?P<duration>{DATE_TOKEN}\s*[-–to]+\s*{DATE_TOKEN})\s*$",
    re.IGNORECASE,
)

# Style A2: "Software Engineer II (Software AG)" then next line "Jan 2024 – Jun 2024"
EXP_HDR_PAREN = re.compile(r"^(?P<title>.+?)\s*\((?P<company>.+?)\)\s*$", re.IGNORECASE)

# Style B (res.pdf): "Title, Company | Location Jan 2019 - Present"
EXP_HDR_PIPE_SINGLE = re.compile(
    rf"^(?P<title>[^,|]+)\s*,\s*(?P<company>[^|]+)\s*\|\s*(?P<location>.+?)\s+(?P<duration>{DATE_TOKEN}\s*[-–to]+\s*{DATE_TOKEN})\s*$",
    re.IGNORECASE,
)

# Style B2 split date: "... Jan 2019 -" next line "Present"
EXP_HDR_PIPE_SPLIT = re.compile(
    rf"^(?P<title>[^,|]+)\s*,\s*(?P<company>[^|]+)\s*\|\s*(?P<location>.+?)\s+(?P<start>{MONTH}\s+\d{{4}})\s*[-–]\s*$",
    re.IGNORECASE,
)

def parse_experience(section_text: str) -> List[ExperienceItem]:
    lines = [l.rstrip() for l in section_text.splitlines()]
    items: List[ExperienceItem] = []

    current: Optional[ExperienceItem] = None
    bullets: List[str] = []

    def flush():
        nonlocal current, bullets
        if current:
            current.bullets = bullets[:]
            items.append(current)
        current = None
        bullets = []

    i = 0
    while i < len(lines):
        raw = lines[i].strip()
        if not raw:
            i += 1
            continue

        if is_bullet(raw):
            if current:
                bullets.append(clean_bullet(raw))
            i += 1
            continue

        m = EXP_HDR_PAREN_SINGLE.match(raw)
        if m:
            flush()
            duration = m.group("duration").strip()
            start, end = parse_date_range(duration)
            current = ExperienceItem(
                title=m.group("title").strip(),
                company=m.group("company").strip(),
                location=None,
                duration=duration,
                start=start,
                end=end,
                bullets=[],
            )
            i += 1
            continue

        m = EXP_HDR_PIPE_SINGLE.match(raw)
        if m:
            flush()
            duration = m.group("duration").strip()
            start, end = parse_date_range(duration)
            current = ExperienceItem(
                title=m.group("title").strip(),
                company=m.group("company").strip(),
                location=m.group("location").strip(),
                duration=duration,
                start=start,
                end=end,
                bullets=[],
            )
            i += 1
            continue

        m = EXP_HDR_PIPE_SPLIT.match(raw)
        if m:
            flush()
            start = m.group("start").strip()
            end = None
            if i + 1 < len(lines):
                nxt = lines[i + 1].strip()
                if re.fullmatch(rf"{DATE_TOKEN}", nxt, re.IGNORECASE):
                    end = nxt
                    i += 1
            duration = f"{start} - {end}" if end else f"{start} -"
            current = ExperienceItem(
                title=m.group("title").strip(),
                company=m.group("company").strip(),
                location=m.group("location").strip(),
                duration=duration,
                start=start,
                end=end,
                bullets=[],
            )
            i += 1
            continue

        m = EXP_HDR_PAREN.match(raw)
        if m:
            nxt1 = lines[i + 1].strip() if i + 1 < len(lines) else ""
            nxt2 = lines[i + 2].strip() if i + 2 < len(lines) else ""
            dr_line = nxt1 if DATE_RANGE_RE.search(nxt1) else (nxt2 if DATE_RANGE_RE.search(nxt2) else None)
            if dr_line:
                flush()
                duration = DATE_RANGE_RE.search(dr_line).group(0)
                start, end = parse_date_range(duration)
                current = ExperienceItem(
                    title=m.group("title").strip(),
                    company=m.group("company").strip(),
                    location=None,
                    duration=duration,
                    start=start,
                    end=end,
                    bullets=[],
                )
                i += 2 if dr_line == nxt1 else 3
                continue

        # Continuation: append to last bullet if we're inside bullets
        if current and bullets:
            bullets[-1] = clean_bullet(bullets[-1] + " " + raw)
        elif current:
            # Some PDFs lose bullet glyphs; keep strong sentence-like lines as bullets.
            if len(raw) >= 25 and re.search(r"[A-Za-z]", raw):
                bullets.append(clean_bullet(raw))

        i += 1

    flush()
    return [x for x in items if x.title and x.company]


# ---------------------------
# Projects parsing
# ---------------------------
def parse_projects(section_text: str) -> List[ProjectItem]:
    lines = [l.rstrip() for l in section_text.splitlines()]
    projects: List[ProjectItem] = []
    current_name: Optional[str] = None
    bullets: List[str] = []

    def flush():
        nonlocal current_name, bullets
        if current_name and bullets:
            projects.append(ProjectItem(name=current_name, bullets=bullets[:]))
        current_name = None
        bullets = []

    for raw in lines:
        line = raw.strip()
        if not line:
            continue

        if is_bullet(line):
            if current_name:
                bullets.append(clean_bullet(line))
            continue

        # likely a new project name (short, not a date)
        if len(line) <= 90 and not DATE_RANGE_RE.search(line) and not match_heading(line.lower()):
            if current_name and bullets:
                flush()
            current_name = line
            continue

        if current_name and bullets:
            bullets[-1] = clean_bullet(bullets[-1] + " " + line)

    flush()
    return projects


# ---------------------------
# Education parsing (handles GPA + duration on same line or next line)
# ---------------------------
def extract_gpa_from_text(text: str) -> Optional[str]:
    m = GPA_TOKEN_RE.search(text)
    if not m:
        return None
    val = m.group(2)
    scale = m.group(3)
    return f"{val}/{scale}" if scale else val


def strip_gpa(text: str) -> str:
    return GPA_TOKEN_RE.sub("", text)


def strip_duration(text: str) -> Tuple[str, Optional[str]]:
    dr = DATE_RANGE_RE.search(text)
    if not dr:
        return text, None
    duration = dr.group(0)
    cleaned = text.replace(duration, " ").strip(" -–|,")
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned, duration


def parse_education(section_text: str) -> List[EducationItem]:
    """
    Common patterns:
      A) "MS in CS GPA: 3.8/4 Aug 2024 – Dec 2025"
      B) "MS in CS GPA: 3.8/4" next line "University ... Aug 2024 – Dec 2025"
      C) Single line "Bachelor ... University | City, ST March 2024"
    We extract GPA + duration wherever they appear, and keep degree clean.
    """
    lines = [l.strip() for l in section_text.splitlines() if l.strip()]
    out: List[EducationItem] = []
    i = 0

    # single-line graduation date variant: "... | Salt Lake City, UT March 2024"
    EDU_GRAD_LINE_RE = re.compile(
        r"^(?P<degree>.+?)\s*,\s*(?P<inst>.+?)\s*\|\s*(?P<loc>.+?)\s+(?P<grad>(" + MONTH + r")\s+\d{4}|\d{4})\s*$",
        re.IGNORECASE,
    )

    while i < len(lines):
        line = lines[i]

        mgrad = EDU_GRAD_LINE_RE.match(line)
        if mgrad:
            out.append(EducationItem(
                degree=mgrad.group("degree").strip(),
                institution=mgrad.group("inst").strip(),
                location=mgrad.group("loc").strip(),
                duration=None,
                start=None,
                end=None,
                graduation=mgrad.group("grad").strip(),
                gpa=extract_gpa_from_text(line),
            ))
            i += 1
            continue

        if DEGREE_RE.search(line):
            degree_line = line

            gpa = extract_gpa_from_text(degree_line)
            deg_wo_gpa = strip_gpa(degree_line)
            deg_clean, duration_from_degree = strip_duration(deg_wo_gpa)
            deg_clean = deg_clean.strip(" -–|,")
            deg_clean = re.sub(r"\s{2,}", " ", deg_clean).strip()

            institution = None
            location = None
            duration = duration_from_degree
            start = end = None

            # Pair next line as institution (+ duration if not found yet)
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                if not match_heading(next_line.lower()):
                    inst_line = next_line
                    if not duration:
                        inst_line, duration_from_inst = strip_duration(inst_line)
                        duration = duration_from_inst
                    inst_line = inst_line.strip(" -–|,")
                    institution = inst_line if inst_line else None
                    i += 1  # consume paired line

            if duration:
                start, end = parse_date_range(duration)

            out.append(EducationItem(
                degree=deg_clean if deg_clean else None,
                institution=institution,
                location=location,
                duration=duration,
                start=start,
                end=end,
                graduation=None,
                gpa=gpa,
            ))
            i += 1
            continue

        i += 1

    return out


# ---------------------------
# Skills + Certifications
# ---------------------------
def parse_skills(section_text: str) -> Dict[str, List[str]]:
    groups: Dict[str, List[str]] = {}
    lines = [l.strip() for l in section_text.splitlines() if l.strip()]

    for line in lines:
        if ":" in line:
            k, v = line.split(":", 1)
            key = k.strip()
            vals = [x.strip().strip(".") for x in v.split(",") if x.strip()]
            if key and vals:
                groups[key] = vals

    if not groups and section_text.strip():
        vals = [x.strip().strip(".") for x in section_text.replace("\n", ",").split(",") if x.strip()]
        groups["skills"] = vals

    return groups


def parse_certifications(section_text: str) -> List[str]:
    bullets = []
    for l in section_text.splitlines():
        s = l.strip()
        if not s:
            continue
        if is_bullet(s):
            bullets.append(clean_bullet(s))
    if bullets:
        return bullets
    return [l.strip() for l in section_text.splitlines() if l.strip()]


# ---------------------------
# "Other" blocks generator (so UI can fix misses)
# ---------------------------
def build_other_blocks(
    sections: Dict[str, str],
    unknown_heading_blocks: List[OtherBlock],
    experience_items: List[ExperienceItem],
    education_items: List[EducationItem],
    project_items: List[ProjectItem],
    skills_groups: Dict[str, List[str]],
    certifications: List[str],
) -> List[OtherBlock]:
    others: List[OtherBlock] = []
    others.extend(unknown_heading_blocks)

    # If a known section exists but parser produced nothing meaningful, keep raw as other
    if sections.get("experience") and len(experience_items) == 0:
        others.append(OtherBlock(
            heading="Experience",
            source_section="experience",
            reason="experience_parse_failed",
            text=sections["experience"],
        ))

    if sections.get("education") and len(education_items) == 0:
        others.append(OtherBlock(
            heading="Education",
            source_section="education",
            reason="education_parse_failed",
            text=sections["education"],
        ))

    if sections.get("projects") and len(project_items) == 0:
        others.append(OtherBlock(
            heading="Projects",
            source_section="projects",
            reason="projects_parse_failed",
            text=sections["projects"],
        ))

    if sections.get("skills") and (not skills_groups or (len(skills_groups) == 1 and "skills" in skills_groups and len(skills_groups["skills"]) == 0)):
        others.append(OtherBlock(
            heading="Skills",
            source_section="skills",
            reason="skills_parse_failed",
            text=sections["skills"],
        ))

    # Certifications: if heading exists but empty output
    if sections.get("certifications") and len(certifications) == 0:
        others.append(OtherBlock(
            heading="Certifications",
            source_section="certifications",
            reason="certifications_parse_failed",
            text=sections["certifications"],
        ))

    return others


# ---------------------------
# Build final object
# ---------------------------
def build_resume_object(pdf_path: str, ocr_fallback: bool = True) -> Dict:
    raw_text = extract_text_from_pdf(pdf_path, ocr_fallback=ocr_fallback)
    contact = extract_contact(raw_text)

    sections, unknown_heading_blocks = split_sections_with_unknowns(raw_text)

    summary = normalize_inline_text(sections.get("summary") or "")
    exp_items = parse_experience(sections.get("experience", ""))
    edu_items = parse_education(sections.get("education", ""))
    proj_items = parse_projects(sections.get("projects", ""))
    skills = parse_skills(sections.get("skills", ""))
    certs = parse_certifications(sections.get("certifications", "")) if sections.get("certifications") else []

    other_blocks = build_other_blocks(
        sections=sections,
        unknown_heading_blocks=unknown_heading_blocks,
        experience_items=exp_items,
        education_items=edu_items,
        project_items=proj_items,
        skills_groups=skills,
        certifications=certs,
    )

    return {
        "contact": contact,
        "summary": summary or None,
        "experience": [asdict(x) for x in exp_items],
        "projects": [asdict(x) for x in proj_items],
        "education": [asdict(x) for x in edu_items],
        "skills": skills,
        "certifications": certs,
        "other": [asdict(x) for x in other_blocks],  # ✅ always include
        "raw_sections": sections,                    # keep for debugging/LLM repair
        "raw_text": raw_text,                        # keep for debugging/LLM repair
    }
