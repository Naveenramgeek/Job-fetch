import logging

import pandas as pd

from app.config import settings

try:
    from jobspy import scrape_jobs
except ImportError:
    scrape_jobs = None

logger = logging.getLogger(__name__)


def _site_names_from_settings() -> list[str]:
    raw = settings.job_site_names or ""
    names = [s.strip() for s in raw.split(",") if s.strip()]
    return names or ["indeed", "linkedin", "zip_recruiter", "google"]


def fetch_and_deduplicate_jobs(
    search_term: str = "Software Engineer",
    location: str = "United States",
    results_wanted: int = 100,
    hours_old: int = 2,
) -> pd.DataFrame | None:
    """
    Fetches jobs from multiple boards and removes duplicates within the batch.
    Returns a DataFrame with columns including title, company, job_url, description, etc.
    """
    if scrape_jobs is None:
        raise RuntimeError("jobspy is not installed. pip install python-jobspy")

    logger.info("Fetching jobs: term=%r, location=%r, results_wanted=%d", search_term, location, results_wanted)
    try:
        jobs = scrape_jobs(
            site_name=_site_names_from_settings(),
            search_term=search_term,
            location=location,
            results_wanted=results_wanted,
            hours_old=hours_old,
            country_indeed=settings.job_country_indeed,
            linkedin_fetch_description=True,
        )
    except Exception as e:
        logger.exception("Scraping error")
        raise RuntimeError(f"Scraping error: {e}") from e

    if jobs is None or jobs.empty:
        logger.warning("No jobs returned for %r", search_term)
        return None

    unique_jobs = jobs.copy()
    unique_jobs.columns = [str(c).lower() for c in unique_jobs.columns]
    if "company_name" in unique_jobs.columns and "company" not in unique_jobs.columns:
        unique_jobs["company"] = unique_jobs["company_name"]
    if "date_posted" in unique_jobs.columns and "posted_at" not in unique_jobs.columns:
        unique_jobs["posted_at"] = unique_jobs["date_posted"]
    # Ensure description column exists (jobspy may use "description" or "job_description" etc.)
    if "description" not in unique_jobs.columns:
        if "job_description" in unique_jobs.columns:
            unique_jobs["description"] = unique_jobs["job_description"]
        else:
            unique_jobs["description"] = ""
    unique_jobs["company"] = unique_jobs["company"].fillna("Unknown Company")
    unique_jobs["title"] = unique_jobs["title"].fillna("Unknown Title")
    unique_jobs["title_clean"] = unique_jobs["title"].astype(str).str.lower().str.strip()
    unique_jobs["company_clean"] = unique_jobs["company"].astype(str).str.lower().str.strip()
    unique_jobs = unique_jobs.drop_duplicates(
        subset=["title_clean", "company_clean"],
        keep="first",
    )
    unique_jobs = unique_jobs.drop(columns=["title_clean", "company_clean"]).reset_index(drop=True)
    logger.info("Fetched %d unique jobs for %r", len(unique_jobs), search_term)
    return unique_jobs
