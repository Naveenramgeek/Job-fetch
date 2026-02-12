import json
import logging
import re
from typing import Any

import boto3
from botocore.config import Config

from app.config import settings

logger = logging.getLogger(__name__)


def _call_bedrock_llm(prompt: str, timeout: float = 60.0) -> str:
    """Call Bedrock LLM via converse API and return response text."""
    try:
        client = boto3.client(
            "bedrock-runtime",
            region_name=settings.aws_region,
            config=Config(read_timeout=int(timeout), connect_timeout=10),
        )
        model_ids = [settings.bedrock_llm_model_id]
        # Common typo safety: "ministral" -> "mistral".
        if "ministral" in settings.bedrock_llm_model_id:
            model_ids.append(settings.bedrock_llm_model_id.replace("ministral", "mistral"))

        last_err = None
        response = None
        for model_id in model_ids:
            try:
                response = client.converse(
                    modelId=model_id,
                    messages=[
                        {
                            "role": "user",
                            "content": [{"text": prompt}],
                        }
                    ],
                    inferenceConfig={
                        "maxTokens": 1200,
                        "temperature": 0.2,
                    },
                )
                break
            except Exception as e:
                last_err = e
                logger.warning("Bedrock LLM model attempt failed: model=%s err=%s", model_id, e)
        if response is None and last_err is not None:
            raise last_err

        blocks = (response.get("output") or {}).get("message", {}).get("content", [])
        text = "".join(b.get("text", "") for b in blocks if isinstance(b, dict)).strip()
        logger.debug("Bedrock LLM response length=%d", len(text))
        return text
    except Exception as e:
        logger.warning("Bedrock LLM call failed: %s", e)
        raise


def is_llm_enabled() -> bool:
    """Whether Bedrock LLM is enabled."""
    return bool(settings.bedrock_llm_enabled and settings.bedrock_llm_model_id and settings.aws_region)


def llm_match_resume_job(
    resume_summary: str,
    job_title: str,
    job_description: str,
) -> tuple[float, str]:
    """
    Score resume vs job (0-1) using Bedrock LLM.
    Returns (match_score, match_reason).
    """
    prompt = f"""You are a strict resume-to-JD matcher. Use ONLY the provided resume text. Do not guess.
        If a detail is not explicitly in the resume, mark it as "unknown".

        TASK:
        Compare Candidate Resume vs Job Description and return ONLY JSON:
        {{"match_score": number, "match_reason": string, "breakdown": {{...}}}}

        RULES (IMPORTANT):
        1) Compute Years of Experience (YoE) FROM EXPERIENCE DATES:
        - Extract each role with start and end dates.
        - If "Present", use 2026-02.
        - Compute months per role (end-start). Sum ONLY overlapping months once (do not double-count).
        - YoE_years = total_months/12 rounded to 1 decimal.
        - If dates are missing for roles, YoE is "unknown".

        2) JD minimum YoE:
        - Extract required minimum years from JD (e.g., "5+ years" -> 5).
        - If JD minimum not found, set jd_min_yoe = "unknown".

        3) YoE scoring (0-1):
        - If YoE or jd_min_yoe is unknown: yoe_score = 0.6 (uncertainty penalty, not failure)
        - Else if YoE_years >= jd_min_yoe: yoe_score = 1.0
        - Else if YoE_years <= jd_min_yoe - 2.0: yoe_score = 0.0 (heavily penalize 2+ years under)
        - Else: yoe_score = (YoE_years / jd_min_yoe) * 0.8

        4) Technical Skills scoring:
        - Identify JD "must-have" skills.
        - For each must-have, label candidate as:
            "pro" (used in work/project), "mentioned" (listed only), or "missing".
        - tech_score = (#pro *1 + #mentioned*0.4 + #missing*0) / total_must_have

        5) Project Relevance scoring:
        - Find 1-3 resume projects that match JD challenges.
        - If none: project_score=0.2
        - If partial: 0.5
        - If strong direct matches: 1.0

        6) Work Impact/Seniority scoring:
        - Look for scope: ownership, leadership, scale, metrics.
        - junior-only signals -> low; senior ownership -> high.

        WEIGHTS:
        final_score = 0.35*yoe_score + 0.35*tech_score + 0.15*project_score + 0.15*impact_score

        EVIDENCE REQUIREMENT:
        In breakdown, include evidence snippets:
        - roles_used_for_yoe: [{{"role":"", "dates":"", "months":n}}]
        - must_have_table: [{{"skill":"", "status":"pro/mentioned/missing", "evidence":""}}]

        INPUTS:
        RESUME:
        <<<{resume_summary}>>>

        JOB TITLE:
        <<<{job_title}>>>

        JOB DESCRIPTION:
        <<<{job_description}>>>"""

    text = _call_bedrock_llm(prompt)
    score, reason = 0.5, "Could not parse LLM response"
    try:
        # Try direct JSON parse first.
        try:
            obj = json.loads(text)
        except Exception:
            obj = None

        # If model wraps JSON in prose/markdown, find score/reason via regex.
        if obj is None:
            score_match = re.search(r'"match_score"\s*:\s*([0-9]+(?:\.[0-9]+)?)', text, re.IGNORECASE)
            reason_match = re.search(r'"match_reason"\s*:\s*"([^"]+)"', text, re.IGNORECASE)
            if score_match:
                score = float(score_match.group(1))
            if reason_match:
                reason = reason_match.group(1)
        else:
            score = float(obj.get("match_score", 0.5))
            reason = str(obj.get("match_reason", reason))

        # Normalize score whether model returns 0-1 or 0-100.
        if score > 1.0:
            score = score / 100.0
        score = max(0, min(1, score))
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("Failed to parse match response: %s", e)
    return score, reason


def llm_assign_category(resume_title: str, category_slugs: list[str]) -> str | None:
    """
    Pick the best matching category slug for the resume title, or None if none fit.
    """
    if not category_slugs:
        return None
    slugs_str = ", ".join(category_slugs)
    prompt = f"""Given this job title, pick the single best matching category from the list. Reply with ONLY the slug, or "none" if none fit well.

JOB TITLE: {resume_title}

CATEGORIES: {slugs_str}

Reply with exactly one slug from the list, or the word "none"."""

    text = _call_bedrock_llm(prompt).lower().strip()
    if "none" in text or not text:
        return None
    # Extract slug (model may add explanation)
    for slug in category_slugs:
        if slug in text or slug.replace("_", " ") in text:
            return slug
    return None


def llm_suggest_generic_slug(resume_title: str) -> tuple[str, str]:
    """
    Suggest a generic slug and display name for a job title (groups similar roles).
    Returns (slug, display_name).
    """
    if not resume_title or not resume_title.strip():
        return "general", "General"

    prompt = f"""Given this job title, suggest a generic slug (lowercase, underscores) that groups similar roles. Also suggest a clean display name.

Examples:
- "UX Designer", "UI/UX Lead" -> slug: ux_designer, display: UX Designer
- "DevOps Engineer" -> slug: devops_engineer, display: DevOps Engineer

JOB TITLE: {resume_title}

Respond with ONLY a JSON object: {{"slug": "...", "display_name": "..."}}"""

    text = _call_bedrock_llm(prompt)
    try:
        match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if match:
            obj = json.loads(match.group())
            slug = str(obj.get("slug", "general")).lower().strip()
            slug = re.sub(r"[^a-z0-9_]", "_", slug).strip("_") or "general"
            display = str(obj.get("display_name", resume_title)).strip() or resume_title
            return slug, display
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("Failed to parse slug response: %s", e)

    # Fallback: simple normalization
    raw = resume_title.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "_", raw).strip("_")[:30] or "general"
    return slug, resume_title.strip().title()


def llm_generate_tailored_resume_latex(
    resume_data: dict,
    job_title: str,
    job_description: str,
    latex_template: str,
    tailoring_instructions: str,
) -> str:
    """
    Generate a tailored LaTeX resume based on resume JSON + job description.
    Returns only LaTeX content.
    """
    resume_json = json.dumps(resume_data, indent=2, ensure_ascii=False)
    prompt = (
        "You are tailoring a resume for a job.\n"
        "Use the user's source resume JSON and the target job information.\n\n"
        "CRITICAL OUTPUT RULES:\n"
        "1) Return ONLY valid LaTeX code. No markdown fences. No explanations.\n"
        "2) Keep the same LaTeX structure/macros as the provided template.\n"
        "3) Fill placeholders with truthful content from resume JSON.\n"
        "4) Integrate relevant job keywords naturally.\n"
        "5) Keep bullets concise and impact-focused with concrete metrics when available.\n\n"
        "Tailoring instructions:\n"
        f"{tailoring_instructions}\n\n"
        "Job title:\n"
        f"{job_title}\n\n"
        "Job description:\n"
        f"{job_description}\n\n"
        "Source resume JSON:\n"
        f"{resume_json}\n\n"
        "LaTeX template to preserve:\n"
        f"{latex_template}\n"
    )
    text = _call_bedrock_llm(prompt, timeout=120.0).strip()
    # Strip common markdown wrappers if model still returns them.
    text = re.sub(r"^```(?:latex)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def llm_generate_tailored_resume_sections(
    resume_data: dict,
    job_title: str,
    job_description: str,
    tailoring_instructions: str,
) -> dict:
    """
    Generate tailored resume sections as structured JSON.
    The backend renders final LaTeX deterministically.
    """
    resume_json = json.dumps(resume_data, indent=2, ensure_ascii=False)
    source_experiences = [e for e in (resume_data.get("experience") or []) if isinstance(e, dict)]
    source_projects = [p for p in (resume_data.get("projects") or []) if isinstance(p, dict)]
    source_exp_count = len(source_experiences)
    source_proj_count = len(source_projects)

    def _extract_json(text: str) -> dict[str, Any]:
        clean = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE).strip()
        clean = re.sub(r"\s*```$", "", clean).strip()
        try:
            return json.loads(clean)
        except Exception:
            m = re.search(r"\{[\s\S]*\}", clean)
            if m:
                return json.loads(m.group(0))
            raise

    def _normalize_key(*vals: Any) -> str:
        s = " ".join(str(v or "") for v in vals).strip().lower()
        s = re.sub(r"\s+", " ", s)
        return s

    source_exp_keys = {
        _normalize_key(e.get("title") or e.get("role"), e.get("company") or e.get("organization"))
        for e in source_experiences
    }
    source_exp_keys = {k for k in source_exp_keys if k}

    def _validate_sections(obj: Any) -> tuple[bool, str]:
        if not isinstance(obj, dict):
            return False, "root must be a JSON object"

        summary = obj.get("summary_lines")
        exp = obj.get("experience")
        proj = obj.get("projects")
        skills = obj.get("skills")

        if not isinstance(summary, list) or len(summary) < 3:
            return False, "summary_lines must contain 3 lines"
        if not isinstance(exp, list):
            return False, "experience must be a list"
        if source_exp_count > 0 and len(exp) < source_exp_count:
            return False, f"experience must include all source experiences ({source_exp_count})"
        if not isinstance(proj, list):
            return False, "projects must be a list"
        if source_proj_count > 0 and len(proj) < min(3, source_proj_count):
            return False, f"projects should include at least {min(3, source_proj_count)} source projects"
        if not isinstance(skills, dict):
            return False, "skills must be an object"

        llm_exp_keys = set()
        for i, item in enumerate(exp, start=1):
            if not isinstance(item, dict):
                return False, f"experience[{i}] must be an object"
            title = str(item.get("title") or "").strip()
            company = str(item.get("company") or "").strip()
            bullets = item.get("bullets")
            if not title or not company:
                return False, f"experience[{i}] needs title and company"
            if not isinstance(bullets, list) or len([b for b in bullets if str(b or "").strip()]) < 2:
                return False, f"experience[{i}] must have at least 2 bullets"
            llm_exp_keys.add(_normalize_key(title, company))

        if source_exp_keys and not source_exp_keys.issubset(llm_exp_keys):
            missing = sorted(source_exp_keys - llm_exp_keys)
            return False, f"missing source experiences: {missing[:3]}"

        return True, ""

    base_prompt = f"""You are tailoring a resume for a job.
Return ONLY valid JSON (no markdown, no prose) with this exact shape:
{{
  "summary_lines": ["line 1", "line 2", "line 3"],
  "experience": [
    {{
      "title": "...",
      "company": "...",
      "location": "...",
      "date_range": "...",
      "bullets": ["...", "...", "..."]
    }}
  ],
  "projects": [
    {{
      "name": "...",
      "date": "...",
      "tech_stack": "...",
      "bullets": ["...", "..."]
    }}
  ],
  "skills": {{
    "languages": "...",
    "frameworks": "...",
    "cloud_devops": "...",
    "databases": "...",
    "tools": "..."
  }}
}}

Rules:
- Use only truthful information from source resume.
- Rewrite summary/experience/projects/skills for the target JD.
- Keep bullets concise and impact-oriented.
- You MUST include ALL source experience entries ({source_exp_count} total) in reverse-chronological order.
- For each experience, include title/company/location/date_range and 2-4 bullets.
- Include up to 3 most relevant projects; do not invent projects.
- Preserve technical specificity.

Tailoring instructions:
{tailoring_instructions}

Job title:
{job_title}

Job description:
{job_description}

Source resume JSON:
{resume_json}
"""
    prompt = base_prompt
    last_error = "unknown error"
    for attempt in range(3):
        text = _call_bedrock_llm(prompt, timeout=120.0).strip()
        try:
            obj = _extract_json(text)
        except Exception as e:
            last_error = f"json parse failed: {e}"
            prompt = (
                f"{base_prompt}\n\n"
                "Your previous answer was invalid JSON. "
                "Return ONLY a valid JSON object with no surrounding text."
            )
            continue

        ok, reason = _validate_sections(obj)
        if ok:
            return obj

        last_error = reason
        prompt = (
            f"{base_prompt}\n\n"
            "Your previous response failed validation.\n"
            f"Validation error: {reason}\n"
            "Fix it and return the FULL corrected JSON only."
        )
        logger.warning("Tailor sections validation failed attempt=%d reason=%s", attempt + 1, reason)

    raise ValueError(f"LLM tailored sections validation failed after retries: {last_error}")
