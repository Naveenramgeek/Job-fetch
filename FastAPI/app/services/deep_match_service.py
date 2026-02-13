import logging
from typing import Any

from sqlalchemy.orm import Session

from app.repos.user_repo import get_users_by_category
from app.repos.job_listing_repo import get_jobs_by_category_since
from app.repos.resume_repo import get_latest_by_user
from app.repos.user_job_match_repo import create as create_match, get_existing_match
from app.services.resume_matcher import llm_match

logger = logging.getLogger(__name__)
SINCE_HOURS = 2
MATCH_THRESHOLD = 75  # Only assign job to user if score > 75%


def _score_pair(resume_data: dict[str, Any], job_title: str, job_description: str) -> dict[str, Any]:
    """Get semantic match result. Expects match_score 0-1; we store as 0-100."""
    result = llm_match(resume_data, job_title, job_description)
    score = result.get("match_score", 0) * 100
    return {
        "match_score": round(score, 1),
        "match_reason": result.get("match_reason"),
        "resume_years_experience": result.get("resume_years_experience"),
        "required_years_experience": result.get("required_years_experience"),
        "hard_gate_blocked": bool(result.get("hard_gate_blocked")),
    }


def _log_score_distribution(scores: list[float], category_id: str) -> None:
    """Log score distribution: min, max, avg, and buckets below/above threshold."""
    if not scores:
        return
    min_s = min(scores)
    max_s = max(scores)
    avg_s = sum(scores) / len(scores)
    below = sum(1 for s in scores if s <= MATCH_THRESHOLD)
    above = len(scores) - below
    # Buckets: 0-50, 50-75, 75-90, 90-100
    b_0_50 = sum(1 for s in scores if s <= 50)
    b_50_75 = sum(1 for s in scores if 50 < s <= MATCH_THRESHOLD)
    b_75_90 = sum(1 for s in scores if MATCH_THRESHOLD < s <= 90)
    b_90_100 = sum(1 for s in scores if s > 90)
    logger.info(
        "Category %s score distribution: min=%.1f max=%.1f avg=%.1f | "
        "below_threshold=%d above_threshold=%d | buckets: 0-50=%d 50-75=%d 75-90=%d 90-100=%d",
        category_id, min_s, max_s, avg_s, below, above, b_0_50, b_50_75, b_75_90, b_90_100,
    )


def run_deep_match_for_category(db: Session, search_category_id: str) -> dict:
    """
    For a category: get users + jobs from last 2h. Score all user-job pairs.
    Returns {"users": int, "jobs": int, "scored": int}.
    """
    users = get_users_by_category(db, search_category_id)
    jobs = get_jobs_by_category_since(db, search_category_id, since_hours=SINCE_HOURS)
    if not users or not jobs:
        logger.debug("Category %s: users=%d jobs=%d (nothing to score)", search_category_id, len(users), len(jobs))
        return {"users": len(users), "jobs": len(jobs), "scored": 0}

    logger.info("Deep match category %s: %d users, %d jobs", search_category_id, len(users), len(jobs))
    scored = 0
    skipped_existing = 0
    skipped_low = 0
    all_scores: list[float] = []
    low_score_samples: list[tuple[str, float]] = []  # (job_title, score) for logging
    for user in users:
        resume = get_latest_by_user(db, user.id)
        resume_data = resume.parsed_data if resume and resume.parsed_data else {}
        for job in jobs:
            if get_existing_match(db, user.id, job.id):
                skipped_existing += 1
                continue
            result = _score_pair(
                resume_data,
                job.title or "",
                job.description or "",
            )
            score = result["match_score"]
            all_scores.append(score)
            if result.get("hard_gate_blocked"):
                skipped_low += 1
                if len(low_score_samples) < 5:
                    low_score_samples.append((job.title or "Unknown", score))
                continue
            if score <= MATCH_THRESHOLD:
                skipped_low += 1
                if len(low_score_samples) < 5:  # Log up to 5 sample low scores
                    low_score_samples.append((job.title or "Unknown", score))
                continue
            create_match(
                db,
                user_id=user.id,
                job_listing_id=job.id,
                match_score=score,
                match_reason=result.get("match_reason"),
                resume_years_experience=result.get("resume_years_experience"),
            )
            scored += 1

    _log_score_distribution(all_scores, search_category_id)
    if low_score_samples:
        samples_str = ", ".join(f"{t[:40]!r}={s:.1f}" for t, s in low_score_samples)
        logger.info("Skipped low-score samples (threshold=%d): %s", MATCH_THRESHOLD, samples_str)
    logger.info(
        "Category %s: scored=%d, skipped_existing=%d, skipped_low=%d",
        search_category_id, scored, skipped_existing, skipped_low,
    )
    return {"users": len(users), "jobs": len(jobs), "scored": scored}


def run_deep_match_all(db: Session) -> dict:
    """Run deep match for all categories that have users."""
    from app.repos.search_category_repo import get_all

    categories = get_all(db)
    total = {"users": 0, "jobs": 0, "scored": 0}
    for cat in categories:
        r = run_deep_match_for_category(db, cat.id)
        total["users"] += r["users"]
        total["jobs"] += r["jobs"]
        total["scored"] += r["scored"]
    return total


def run_deep_match_for_user(db: Session, user_id: str, since_hours: int = SINCE_HOURS) -> dict:
    """
    Run deep match only for one user, against jobs in the user's category.
    Useful for onboarding bootstrap runs without changing global scheduler behavior.
    """
    from app.repos.user_repo import get_by_id as get_user_by_id

    user = get_user_by_id(db, user_id)
    if not user or not user.search_category_id:
        logger.info("Deep match for user skipped: missing user/category user_id=%s", user_id)
        return {"users": 0, "jobs": 0, "scored": 0}

    jobs = get_jobs_by_category_since(db, user.search_category_id, since_hours=since_hours)
    if not jobs:
        return {"users": 1, "jobs": 0, "scored": 0}

    resume = get_latest_by_user(db, user.id)
    resume_data = resume.parsed_data if resume and resume.parsed_data else {}
    scored = 0
    skipped_existing = 0
    skipped_low = 0

    for job in jobs:
        if get_existing_match(db, user.id, job.id):
            skipped_existing += 1
            continue
        result = _score_pair(resume_data, job.title or "", job.description or "")
        score = result["match_score"]
        if result.get("hard_gate_blocked") or score <= MATCH_THRESHOLD:
            skipped_low += 1
            continue
        create_match(
            db,
            user_id=user.id,
            job_listing_id=job.id,
            match_score=score,
            match_reason=result.get("match_reason"),
            resume_years_experience=result.get("resume_years_experience"),
        )
        scored += 1

    logger.info(
        "Deep match user %s: jobs=%d scored=%d skipped_existing=%d skipped_low=%d",
        user.id, len(jobs), scored, skipped_existing, skipped_low,
    )
    return {"users": 1, "jobs": len(jobs), "scored": scored}
