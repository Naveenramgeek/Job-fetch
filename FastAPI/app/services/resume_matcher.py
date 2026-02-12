import json
import logging
import re
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)
from app.services.llm_client import is_llm_enabled, llm_match_resume_job


MAX_RESUME_CHARS = 10000  # Soft cap for LLM input
HARD_GATE_MARGIN_YEARS = 1.0


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


def llm_match(resume_data: dict[str, Any], job_title: str, job_description: str) -> dict[str, Any]:
    """
    Score resume vs job using Bedrock LLM.
    Returns {"match_score": float 0-1, "match_reason": str}.
    """
    resume_text = _resume_to_full_text(resume_data)
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

    if is_llm_enabled():
        try:
            score, reason = llm_match_resume_job(resume_text, job_title or "", job_description or "")
            return {
                "match_score": round(score, 2),
                "match_reason": reason,
                "resume_years_experience": round(resume_years, 1) if resume_years is not None else None,
                "required_years_experience": required_years,
                "hard_gate_blocked": False,
            }
        except Exception as e:
            logger.warning("Bedrock LLM ranking failed: %s", e)

    # Deterministic fallback when LLM is unavailable.
    score = _fallback_keyword_score(resume_text, f"{job_title or ''}\n{job_description or ''}")
    return {
        "match_score": score,
        "match_reason": "Fallback similarity score (LLM unavailable).",
        "resume_years_experience": round(resume_years, 1) if resume_years is not None else None,
        "required_years_experience": required_years,
        "hard_gate_blocked": False,
    }


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


def _is_hard_gate_blocked(resume_years: float | None, required_years: float | None, margin: float) -> bool:
    if resume_years is None or required_years is None:
        return False
    return resume_years < (required_years - margin)
