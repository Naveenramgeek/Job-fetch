import logging
import re
from typing import Any

from sqlalchemy.orm import Session

from app.repos.search_category_repo import get_all, get_by_slug, create as create_category
from app.repos.user_repo import update
from app.repos.resume_repo import get_latest_by_user
from app.services.llm_client import is_llm_enabled, llm_assign_category as llm_assign_category_call, llm_suggest_generic_slug as llm_suggest_slug_call

logger = logging.getLogger(__name__)


def _extract_title_from_resume(resume_data: dict[str, Any]) -> tuple[str, str]:
    """Extract job title from resume. Returns (lowercase for matching, raw for display)."""
    if not resume_data:
        return "", ""
    contact = resume_data.get("contact") or {}
    title = (contact.get("title") or "").strip()
    if not title:
        experiences = resume_data.get("experience") or []
        if experiences:
            exp = experiences[0] if isinstance(experiences[0], dict) else {}
            title = (exp.get("title") or "").strip()
    return title.lower(), title


def _keyword_assign_category(resume_data: dict[str, Any], category_slugs: list[str]) -> str | None:
    """
    Try to match resume to an existing canonical category.
    Returns slug if matched, None if no match.
    """
    title, _ = _extract_title_from_resume(resume_data)

    mapping = {
        "software": "software_engineer",
        "developer": "software_engineer",
        "engineer": "software_engineer",
        "data": "data_scientist",
        "scientist": "data_scientist",
        "mechanical": "mechanical_engineer",
        "product": "product_manager",
        "pm ": "product_manager",
    }
    for kw, slug in mapping.items():
        if kw in title and slug in category_slugs:
            return slug
    return None


def _suggest_generic_slug_from_title(resume_title: str) -> tuple[str, str]:
    """
    Fallback slug suggestion from title when LLM is unavailable.
    E.g., "UX Designer", "UI/UX Lead" -> "ux_designer"; "DevOps Engineer" -> "devops_engineer"
    """
    if not resume_title or not resume_title.strip():
        return "general", "General"

    # Normalize: lowercase, replace non-alphanumeric with underscore, collapse
    raw = resume_title.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "_", raw).strip("_")
    if not slug:
        return "general", "General"

    # Avoid overly long slugs; take first 2-3 meaningful parts
    parts = [p for p in slug.split("_") if len(p) > 1][:3]
    slug = "_".join(parts) if parts else "general"
    display = resume_title.strip().title()
    return slug, display


def assign_user_category(db: Session, user_id: str, resume_data: dict[str, Any] | None = None) -> str | None:
    """
    Assign user to a canonical search category.
    If resume title matches an existing category, use it. Otherwise, LLM suggests
    a generic slug; we get-or-create that category and assign the user.
    Returns the assigned category slug, or None if assignment failed.
    """
    # Ensure at least default categories exist
    categories = get_all(db)
    slugs = [c.slug for c in categories]

    if resume_data is None:
        resume = get_latest_by_user(db, user_id)
        resume_data = resume.parsed_data if resume and resume.parsed_data else {}

    slug = _keyword_assign_category(resume_data, slugs)

    if not slug and is_llm_enabled() and slugs:
        # Try LLM to map to existing category
        _, raw_title = _extract_title_from_resume(resume_data)
        try:
            slug = llm_assign_category_call(raw_title or "Unknown", slugs)
        except Exception as e:
            logger.warning("LLM assign category failed: %s", e)

    if slug:
        # Matched existing canonical category
        cat = get_by_slug(db, slug)
    else:
        # No exact match: LLM suggests generic slug, else use deterministic fallback.
        _, raw_title = _extract_title_from_resume(resume_data)
        if is_llm_enabled():
            try:
                suggested_slug, display_name = llm_suggest_slug_call(raw_title or "Unknown")
            except Exception as e:
                logger.warning("LLM suggest slug failed: %s, using fallback", e)
                suggested_slug, display_name = _suggest_generic_slug_from_title(raw_title or "Unknown")
        else:
            suggested_slug, display_name = _suggest_generic_slug_from_title(raw_title or "Unknown")
        slug = suggested_slug
        cat = get_by_slug(db, slug)
        if not cat:
            cat = create_category(db, slug=slug, display_name=display_name)
            logger.info("Created new category %s for title %r", slug, raw_title)

    if not cat:
        return None
    update(db, user_id, search_category_id=cat.id)
    logger.info("Assigned user %s to category %s", user_id, slug)
    return slug
