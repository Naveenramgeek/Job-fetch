import logging

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_admin, get_current_user_full_access
from app.models.user import User
from app.repos.user_job_match_repo import get_matches_for_user, update_status, delete_match, get_match_for_user
from app.repos.resume_repo import get_latest_by_user
from app.schemas.job import (
    JobMatchResult,
    JobStatusUpdate,
    TailoredResumeResponse,
    TailorResumeFromJdRequest,
    LatexRenderRequest,
)
from app.services.job_collector import run_collector
from app.services.deep_match_service import run_deep_match_all
from app.services.resume_tailor_service import generate_tailored_latex
from app.services.latex_render_service import render_latex_to_pdf_bytes
from app.services.pipeline_scheduler import (
    start_scheduler,
    stop_scheduler,
    get_status as get_pipeline_status,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])


def _match_to_result(m) -> JobMatchResult:
    j = m.job_listing
    score = (m.match_score / 100.0) if m.match_score and m.match_score > 1 else (m.match_score or 0)
    applied_at = m.applied_at.isoformat() if m.applied_at else None
    created_at = j.created_at.isoformat() if j.created_at else None
    return JobMatchResult(
        id=m.id,
        title=j.title or "Unknown",
        company=j.company or "Unknown",
        location=j.location,
        job_url=j.job_url or "",
        description=(j.description or "")[:2000] or None,
        site=None,
        posted_at=j.posted_at,
        created_at=created_at,
        match_score=score,
        match_reason=m.match_reason,
        resume_years_experience=m.resume_years_experience,
        applied_at=applied_at,
    )


@router.post("/run-pipeline")
def run_pipeline(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_admin),
):
    """Manually trigger the collector + deep match pipeline once. Admin only."""
    from app.repos.search_category_repo import seed_default_categories

    from app.repos.job_listing_repo import delete_unmatched as delete_unmatched_job_listings

    logger.info("Pipeline (one-shot) triggered by admin %s", user.email)
    try:
        seed_default_categories(db)
        collector_result = run_collector(db)
        deep_result = run_deep_match_all(db)
        cleanup_count = delete_unmatched_job_listings(db)
        logger.info("Pipeline done: collector=%s deep_match=%s cleanup_unmatched=%d", collector_result, deep_result, cleanup_count)
        return {
            "collector": collector_result,
            "deep_match": deep_result,
            "cleanup_unmatched": cleanup_count,
        }
    except Exception as e:
        logger.exception("Pipeline (one-shot) failed for admin=%s: %s", user.email, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Pipeline run failed. Check server logs for details.",
        ) from e


@router.post("/start-pipeline")
def start_pipeline_recurring(user: User = Depends(get_current_admin)):
    """Start the job pipeline to run now and then every 2 hours. Admin only."""
    logger.info("Start recurring pipeline requested by admin %s", user.email)
    ok, message = start_scheduler()
    if not ok:
        return {"started": False, "message": message}
    return {"started": True, "message": message}


@router.post("/stop-pipeline")
def stop_pipeline_recurring(user: User = Depends(get_current_admin)):
    """Stop the recurring job pipeline. Admin only."""
    logger.info("Stop recurring pipeline requested by admin %s", user.email)
    ok, message = stop_scheduler()
    return {"stopped": ok, "message": message}


@router.get("/pipeline-status")
def pipeline_status(user: User = Depends(get_current_admin)):
    """Return whether the recurring pipeline is running and last/next run times. Admin only."""
    return get_pipeline_status()


@router.get("/matched", response_model=list[JobMatchResult])
def get_matched_jobs(
    status: str = "pending",
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_full_access),
):
    """
    Return jobs matched to this user by the pipeline (broad + deep match).
    status: pending (active), applied, or not_applied.
    """
    matches = get_matches_for_user(db, user.id, status=status, limit=limit)
    logger.debug("GET /jobs/matched user=%s status=%s count=%d", user.id, status, len(matches))
    return [_match_to_result(m) for m in matches if m.job_listing]


@router.get("/applied", response_model=list[JobMatchResult])
def get_applied_jobs(
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_full_access),
):
    """Return jobs this user marked as applied."""
    matches = get_matches_for_user(db, user.id, status="applied", limit=limit)
    return [_match_to_result(m) for m in matches if m.job_listing]


@router.get("", response_model=dict)
def get_jobs(
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_full_access),
):
    """Return both active (pending) and applied jobs in one call."""
    active = get_matches_for_user(db, user.id, status="pending", limit=limit)
    applied = get_matches_for_user(db, user.id, status="applied", limit=limit)
    return {
        "active": [_match_to_result(m) for m in active if m.job_listing],
        "applied": [_match_to_result(m) for m in applied if m.job_listing],
    }


@router.delete("/matches/{match_id}")
def delete_job_match(
    match_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_full_access),
):
    """Delete a job from the user's list (e.g. old/stale jobs)."""
    if delete_match(db, match_id, user.id):
        return {"deleted": True}
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job match not found")


@router.patch("/matches/{match_id}", response_model=JobMatchResult | None)
def update_job_status(
    match_id: str,
    body: JobStatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_full_access),
):
    """
    Mark a job as applied or not_applied. Removes from active list.
    """
    if body.status not in ("applied", "not_applied"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="status must be applied or not_applied")
    match = update_status(db, match_id, user.id, body.status)
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job match not found")
    logger.info("Job status updated: user=%s match=%s status=%s", user.id, match_id, body.status)
    return _match_to_result(match)


@router.post("/matches/{match_id}/tailor-resume", response_model=TailoredResumeResponse)
def tailor_resume_for_match(
    match_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_full_access),
):
    """Generate a tailored LaTeX resume for a specific matched job."""
    match = get_match_for_user(db, match_id, user.id)
    if not match or not match.job_listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job match not found")

    resume = get_latest_by_user(db, user.id)
    if not resume or not resume.parsed_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No saved resume found")

    job = match.job_listing
    latex = generate_tailored_latex(
        resume_data=resume.parsed_data or {},
        job_title=job.title or "",
        job_description=job.description or "",
    )

    return TailoredResumeResponse(
        match_id=match_id,
        job_title=job.title or "Unknown",
        company=job.company or "Unknown",
        latex=latex,
    )


@router.post("/tailor-resume-from-jd", response_model=TailoredResumeResponse)
def tailor_resume_from_jd(
    body: TailorResumeFromJdRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_full_access),
):
    """Generate tailored LaTeX resume from user-provided JD text using saved resume."""
    resume = get_latest_by_user(db, user.id)
    if not resume or not resume.parsed_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No saved resume found")
    if not body.job_description or not body.job_description.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Job description is required")

    job_title = (body.job_title or "").strip() or "Custom Job Description"
    latex = generate_tailored_latex(
        resume_data=resume.parsed_data or {},
        job_title=job_title,
        job_description=body.job_description.strip(),
    )

    return TailoredResumeResponse(
        match_id="manual_jd",
        job_title=job_title,
        company="Custom JD",
        latex=latex,
    )


@router.post("/render-latex-pdf")
def render_latex_pdf(
    body: LatexRenderRequest,
    user: User = Depends(get_current_user_full_access),
):
    """Render provided LaTeX to PDF bytes for in-app preview."""
    try:
        pdf = render_latex_to_pdf_bytes(body.latex or "")
    except Exception as e:
        logger.warning("LaTeX PDF render failed for user=%s: %s", user.id, e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="PDF generation failed. Please check LaTeX syntax.") from e
    return Response(content=pdf, media_type="application/pdf")
