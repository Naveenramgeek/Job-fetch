import json
import logging
import re
from datetime import datetime
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)
from app.services.titan_embedding import cosine_similarity, embed_text_titan


MAX_RESUME_CHARS = 10000  # Soft cap for embedding input
HARD_GATE_MARGIN_YEARS = 1.0
SKILL_GATE_MARGIN_YEARS = 0.5
MIN_HYBRID_SCORE = 0.0
MAX_HYBRID_SCORE = 1.0

KNOWN_TECH_KEYWORDS = {
    "python", "java", "javascript", "typescript", "go", "golang", "c#", "c++",
    "fastapi", "django", "flask", "spring", "react", "angular", "node", "nodejs",
    "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "jenkins",
    "postgres", "postgresql", "mysql", "mongodb", "redis", "kafka", "spark",
    "snowflake", "airflow", "pytorch", "tensorflow", "scikit", "sql",
}


def _resume_to_full_text(resume_data: dict[str, Any]) -> str:
    """Convert resume to text for LLM matching. Experience + Projects only (job title match already done)."""
    if not resume_data:
        return ""
    parts = []

    if resume_data.get("experience"):
        parts.append("Experience:")
        for exp in resume_data["experience"]:
            if not isinstance(exp, dict):
                continue
            title = exp.get("title") or "Role"
            company = exp.get("company") or ""
            start = exp.get("start") or ""
            end = exp.get("end") or exp.get("duration") or ""
            dates = f" ({start} - {end})" if start or end else ""
            parts.append(f"  - {title} at {company}{dates}")
            for b in exp.get("bullets", []):
                if b:
                    parts.append(f"    • {b}")

    if resume_data.get("projects"):
        parts.append("\nProjects:")
        for proj in resume_data["projects"]:
            if not isinstance(proj, dict):
                continue
            name = proj.get("name") or "Project"
            parts.append(f"  - {name}")
            for b in proj.get("bullets", []):
                if b:
                    parts.append(f"    • {b}")

    text = "\n".join(parts).strip()
    if len(text) > MAX_RESUME_CHARS:
        text = text[:MAX_RESUME_CHARS] + "\n[truncated]"
    return text or json.dumps(resume_data)[:MAX_RESUME_CHARS]


def llm_match(
    resume_data: dict[str, Any],
    job_title: str,
    job_description: str,
    *,
    resume_embedding: list[float] | None = None,
    job_embedding: list[float] | None = None,
    job_location: str | None = None,
) -> dict[str, Any]:
    """
    Hybrid match score using hard metadata filters + Titan semantic similarity.
    Returns {"match_score": float 0-1, "match_reason": str}.
    """
    resume_text = _resume_to_full_text(resume_data)
    job_text = _job_to_full_text(job_title, job_description)
    resume_years = _compute_resume_total_years(resume_data)
    required_years = _extract_required_years_from_jd(job_description or "")

    if _is_hard_gate_blocked(resume_years, required_years, HARD_GATE_MARGIN_YEARS):
        return {
            "match_score": 0.0,
            "match_reason": (
                f"Hard gate: resume experience ({resume_years:.1f}y) is below "
                f"required experience ({required_years:.1f}y) minus margin ({HARD_GATE_MARGIN_YEARS:.1f}y)."
            ),
            "resume_years_experience": round(resume_years, 1) if resume_years is not None else None,
            "required_years_experience": required_years,
            "hard_gate_blocked": True,
        }

    if _is_location_hard_gate_blocked(resume_data, job_location):
        return {
            "match_score": 0.0,
            "match_reason": "Hard gate: location mismatch for non-remote role.",
            "resume_years_experience": round(resume_years, 1) if resume_years is not None else None,
            "required_years_experience": required_years,
            "hard_gate_blocked": True,
        }

    skill_year_reqs = _extract_required_skill_years_from_jd(job_description or "")
    missing_skill_year_gates = _evaluate_skill_year_gates(resume_data, skill_year_reqs)
    if missing_skill_year_gates:
        reasons = ", ".join(
            f"{skill}: {have:.1f}y/{need:.1f}y"
            for skill, need, have in missing_skill_year_gates
        )
        return {
            "match_score": 0.0,
            "match_reason": f"Hard gate: insufficient years for required skills ({reasons}).",
            "resume_years_experience": round(resume_years, 1) if resume_years is not None else None,
            "required_years_experience": required_years,
            "hard_gate_blocked": True,
        }

    semantic = _semantic_similarity_score(
        resume_text,
        job_text,
        resume_embedding=resume_embedding,
        job_embedding=job_embedding,
    )
    skill_cov = _skill_coverage_score(resume_data, job_description or "")
    years_fit = _years_fit_score(resume_years, required_years)
    score = round(
        max(MIN_HYBRID_SCORE, min(MAX_HYBRID_SCORE, semantic * 0.6 + skill_cov * 0.25 + years_fit * 0.15)),
        2,
    )
    reason = (
        f"Hybrid score: semantic={semantic:.2f}, skill_coverage={skill_cov:.2f}, years_fit={years_fit:.2f}."
    )
    return {
        "match_score": score,
        "match_reason": reason,
        "resume_years_experience": round(resume_years, 1) if resume_years is not None else None,
        "required_years_experience": required_years,
        "hard_gate_blocked": False,
    }


def _job_to_full_text(job_title: str, job_description: str) -> str:
    text = f"{job_title or ''}\n{job_description or ''}".strip()
    if len(text) > MAX_RESUME_CHARS:
        text = text[:MAX_RESUME_CHARS] + "\n[truncated]"
    return text


@lru_cache(maxsize=1024)
def _embed_cached(text: str) -> tuple[float, ...]:
    return tuple(embed_text_titan(text))


def _semantic_similarity_score(
    resume_text: str,
    job_text: str,
    *,
    resume_embedding: list[float] | None = None,
    job_embedding: list[float] | None = None,
) -> float:
    if not resume_text or not job_text:
        return 0.35
    try:
        # pgvector/SQLAlchemy may return numpy arrays; avoid truthiness checks on arrays.
        a = list(resume_embedding) if resume_embedding is not None else list(_embed_cached(resume_text))
        b = list(job_embedding) if job_embedding is not None else list(_embed_cached(job_text))
        cos = cosine_similarity(a, b)  # [-1, 1]
        # Normalize to [0, 1]
        return round(max(0.0, min(1.0, (cos + 1.0) / 2.0)), 2)
    except Exception as e:
        logger.warning("Embedding similarity failed, using keyword fallback: %s", e)
        return _fallback_keyword_score(resume_text, job_text)


def _is_location_hard_gate_blocked(resume_data: dict[str, Any], job_location: str | None) -> bool:
    if not job_location:
        return False
    jl = job_location.strip().lower()
    if not jl:
        return False
    if any(x in jl for x in ("remote", "anywhere", "work from home", "wfh")):
        return False
    resume_loc = ((resume_data.get("contact") or {}).get("location") or "").strip().lower()
    if not resume_loc:
        return False
    # Very conservative mismatch check to avoid false negatives.
    return (resume_loc not in jl) and (jl not in resume_loc)


def _fallback_keyword_score(resume_text: str, job_text: str) -> float:
    stopwords = {
        "and", "the", "with", "for", "from", "that", "this", "you", "your", "our", "are", "was", "were",
        "have", "has", "had", "into", "onto", "about", "over", "under", "than", "their", "them", "they",
        "will", "would", "could", "should", "must", "can", "across", "using", "use", "used", "build", "built",
        "experience", "project", "projects", "role", "team", "work", "worked", "developer", "engineer",
    }
    token_re = re.compile(r"[a-zA-Z][a-zA-Z0-9_+#.-]{1,}")
    resume_tokens = {t.lower() for t in token_re.findall(resume_text or "") if t.lower() not in stopwords}
    job_tokens = {t.lower() for t in token_re.findall(job_text or "") if t.lower() not in stopwords}
    if not resume_tokens or not job_tokens:
        return 0.35

    overlap = len(resume_tokens & job_tokens)
    coverage = overlap / max(len(job_tokens), 1)
    # Map coverage to practical range: [0.35, 0.92]
    score = 0.35 + min(coverage, 1.0) * 0.57
    return round(max(0.0, min(1.0, score)), 2)


def _extract_resume_skill_tokens(resume_data: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    skills = resume_data.get("skills") or {}
    if isinstance(skills, dict):
        for key, value in skills.items():
            tokens.update(_normalize_skill_tokens(str(key)))
            tokens.update(_normalize_skill_tokens(json.dumps(value)))

    for exp in resume_data.get("experience") or []:
        if not isinstance(exp, dict):
            continue
        tokens.update(_normalize_skill_tokens(str(exp.get("title") or "")))
        for b in exp.get("bullets", []) or []:
            tokens.update(_normalize_skill_tokens(str(b or "")))
    return tokens


def _normalize_skill_tokens(text: str) -> set[str]:
    raw = [t.lower().strip(".,;:()[]{}") for t in re.findall(r"[A-Za-z][A-Za-z0-9+#.-]{1,}", text or "")]
    out = {t for t in raw if t}
    return {t for t in out if t in KNOWN_TECH_KEYWORDS}


def _extract_jd_required_skills(job_description: str) -> set[str]:
    tokens = _normalize_skill_tokens(job_description or "")
    return tokens


def _skill_coverage_score(resume_data: dict[str, Any], job_description: str) -> float:
    req = _extract_jd_required_skills(job_description)
    if not req:
        return 0.7
    have = _extract_resume_skill_tokens(resume_data)
    overlap = len(req & have)
    return round(overlap / max(len(req), 1), 2)


def _years_fit_score(resume_years: float | None, required_years: float | None) -> float:
    if required_years is None:
        return 0.75
    if resume_years is None:
        return 0.3
    if resume_years >= required_years:
        return 1.0
    return round(max(0.0, resume_years / max(required_years, 0.1)), 2)


def _parse_date_token_to_year_month(token: str | None) -> tuple[int, int] | None:
    if not token:
        return None
    value = token.strip()
    if not value:
        return None
    if value.lower() == "present":
        now = datetime.utcnow()
        return now.year, now.month

    month_names = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
    }
    m = re.match(r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+(\d{4})$", value, re.IGNORECASE)
    if m:
        return int(m.group(2)), month_names[m.group(1).lower()]
    m = re.match(r"^(\d{4})$", value)
    if m:
        # Year-only tokens are mapped to Jan for start and Dec for end by caller.
        return int(m.group(1)), 1
    return None


def _year_month_to_index(year: int, month: int) -> int:
    return year * 12 + (month - 1)


def _compute_resume_total_years(resume_data: dict[str, Any]) -> float | None:
    experiences = resume_data.get("experience") or []
    intervals: list[tuple[int, int]] = []
    for exp in experiences:
        if not isinstance(exp, dict):
            continue
        start_raw = exp.get("start")
        end_raw = exp.get("end") or exp.get("duration")
        start = _parse_date_token_to_year_month(start_raw) if isinstance(start_raw, str) else None
        end = _parse_date_token_to_year_month(end_raw) if isinstance(end_raw, str) else None

        # Try extracting range from duration string when explicit start/end are absent.
        if (not start or not end) and isinstance(exp.get("duration"), str):
            m = re.search(
                r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|\d{4})\s*[-–to]+\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|Present|\d{4})\s*(\d{4})?",
                exp["duration"],
                re.IGNORECASE,
            )
            if m:
                # Keep parser conservative; date fields should already be present in most cases.
                pass

        if not start or not end:
            continue

        start_idx = _year_month_to_index(start[0], start[1])
        end_month = end[1]
        if isinstance(end_raw, str) and re.fullmatch(r"\d{4}", end_raw.strip()):
            end_month = 12
        end_idx = _year_month_to_index(end[0], end_month)
        if end_idx < start_idx:
            continue
        intervals.append((start_idx, end_idx))

    if not intervals:
        return None

    intervals.sort(key=lambda x: x[0])
    merged: list[tuple[int, int]] = []
    for start, end in intervals:
        if not merged or start > merged[-1][1] + 1:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))

    total_months = sum((end - start + 1) for start, end in merged)
    return round(total_months / 12.0, 1)


def _extract_required_years_from_jd(job_description: str) -> float | None:
    if not job_description:
        return None
    text = " ".join(job_description.split())

    patterns = [
        r"(\d+(?:\.\d+)?)\s*\+\s*years?\s+of\s+experience",
        r"minimum\s+of\s+(\d+(?:\.\d+)?)\s+years?",
        r"at\s+least\s+(\d+(?:\.\d+)?)\s+years?",
        r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s+years?\s+of\s+experience",
        r"(\d+(?:\.\d+)?)\s+years?\s+of\s+experience",
        r"(\d+(?:\.\d+)?)\s+years?\s+experience",
    ]

    candidates: list[float] = []
    for p in patterns:
        for m in re.finditer(p, text, flags=re.IGNORECASE):
            if m.lastindex and m.lastindex >= 2:
                # Range like 3-5 years -> use lower bound as minimum.
                candidates.append(float(m.group(1)))
            else:
                candidates.append(float(m.group(1)))
    if not candidates:
        return None
    return round(max(candidates), 1)


def _extract_required_skill_years_from_jd(job_description: str) -> dict[str, float]:
    if not job_description:
        return {}
    req: dict[str, float] = {}
    text = " ".join(job_description.split())

    patterns = [
        # "7 years of Java", "at least 3 years of Python"
        r"(?:at\s+least\s+|minimum\s+of\s+)?(\d+(?:\.\d+)?)\s*\+?\s*years?\s+of\s+([A-Za-z][A-Za-z0-9+#.\-/]{1,30})",
        # "Java (7+ years)"
        r"([A-Za-z][A-Za-z0-9+#.\-/]{1,30})\s*\(\s*(\d+(?:\.\d+)?)\s*\+?\s*years?\s*\)",
    ]
    for idx, p in enumerate(patterns):
        for m in re.finditer(p, text, re.IGNORECASE):
            if idx == 1:
                skill_phrase = m.group(1).strip().lower()
                years = float(m.group(2))
            else:
                years = float(m.group(1))
                skill_phrase = m.group(2).strip().lower()
            skills = _normalize_skill_tokens(skill_phrase)
            for s in skills:
                req[s] = max(req.get(s, 0.0), years)
    return req


def _compute_resume_skill_years(resume_data: dict[str, Any], skill: str) -> float:
    experiences = resume_data.get("experience") or []
    intervals: list[tuple[int, int]] = []
    skill_l = (skill or "").lower()
    for exp in experiences:
        if not isinstance(exp, dict):
            continue
        corpus = " ".join(
            [
                str(exp.get("title") or ""),
                str(exp.get("company") or ""),
                " ".join(str(b or "") for b in (exp.get("bullets") or [])),
            ]
        ).lower()
        if skill_l not in corpus:
            continue

        start_raw = exp.get("start")
        end_raw = exp.get("end") or exp.get("duration")
        start = _parse_date_token_to_year_month(start_raw) if isinstance(start_raw, str) else None
        end = _parse_date_token_to_year_month(end_raw) if isinstance(end_raw, str) else None
        if not start or not end:
            continue
        start_idx = _year_month_to_index(start[0], start[1])
        end_month = end[1]
        if isinstance(end_raw, str) and re.fullmatch(r"\d{4}", end_raw.strip()):
            end_month = 12
        end_idx = _year_month_to_index(end[0], end_month)
        if end_idx >= start_idx:
            intervals.append((start_idx, end_idx))

    if not intervals:
        return 0.0

    intervals.sort(key=lambda x: x[0])
    merged: list[tuple[int, int]] = []
    for start, end in intervals:
        if not merged or start > merged[-1][1] + 1:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    total_months = sum((end - start + 1) for start, end in merged)
    return round(total_months / 12.0, 1)


def _evaluate_skill_year_gates(resume_data: dict[str, Any], required: dict[str, float]) -> list[tuple[str, float, float]]:
    failures: list[tuple[str, float, float]] = []
    for skill, needed in required.items():
        have = _compute_resume_skill_years(resume_data, skill)
        if have < (needed - SKILL_GATE_MARGIN_YEARS):
            failures.append((skill, needed, have))
    return failures


def _is_hard_gate_blocked(resume_years: float | None, required_years: float | None, margin: float) -> bool:
    if resume_years is None or required_years is None:
        return False
    return resume_years < (required_years - margin)
