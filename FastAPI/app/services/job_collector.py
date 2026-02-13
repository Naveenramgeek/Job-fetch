import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from sqlalchemy.orm import Session

from app.config import settings
from app.models.job_listing import compute_job_hash
from app.repos.search_category_repo import get_all, get_by_id as get_category_by_id, get_categories_with_active_users
from app.repos.job_listing_repo import batch_upsert
from app.services.job_fetcher import fetch_and_deduplicate_jobs

logger = logging.getLogger(__name__)

# Shared list for thread results; protected by lock
_shared_results: list[dict] = []
_lock = threading.Lock()


def _fetch_for_category(
    category_slug: str,
    category_id: str,
    results_wanted: int | None = None,
    hours_old: int | None = None,
) -> list[dict]:
    """Fetch jobs for one category. Called in worker thread."""
    wanted = results_wanted if results_wanted is not None else settings.job_results_wanted
    hours = hours_old if hours_old is not None else settings.job_hours_old
    try:
        df = fetch_and_deduplicate_jobs(
            search_term=category_slug.replace("_", " ").title(),
            location=settings.job_location,
            results_wanted=wanted,
            hours_old=hours,
        )
    except Exception as e:
        logger.warning("Fetch failed for category %s: %s", category_slug, e)
        return []
    if df is None or df.empty:
        return []
    rows = []
    for _, r in df.iterrows():
        title = str(r.get("title") or "Unknown Title")
        company = str(r.get("company") or r.get("company_name") or "Unknown Company")
        job_url = str(r.get("job_url") or "")
        if not job_url:
            continue
        desc = r.get("description") or r.get("job_description") or r.get("desc")
        if desc is None or (isinstance(desc, float) and str(desc) == "nan"):
            desc = ""
        rows.append({
            "title": title,
            "company": company,
            "job_url": job_url,
            "description": str(desc),
            "location": r.get("location"),
            "posted_at": r.get("posted_at") or r.get("date_posted"),
            "search_category_id": category_id,
            "job_hash": compute_job_hash(title, company, job_url),
        })
    return rows


def _append_to_shared(rows: list[dict]) -> None:
    with _lock:
        _shared_results.extend(rows)


def run_collector(
    db: Session,
    *,
    category_ids: list[str] | None = None,
    results_wanted: int | None = None,
    hours_old: int | None = None,
) -> dict:
    """
    Run the full collector: fetch only categories with active users, spawn threads, dedupe, upsert.
    Returns {"total_fetched": int, "total_deduped": int, "inserted": int, "categories": int}.
    """
    global _shared_results
    _shared_results = []

    if category_ids:
        categories = []
        seen: set[str] = set()
        for category_id in category_ids:
            if not category_id or category_id in seen:
                continue
            seen.add(category_id)
            cat = get_category_by_id(db, category_id)
            if cat:
                categories.append(cat)
        if not categories:
            return {"total_fetched": 0, "total_deduped": 0, "inserted": 0, "categories": 0}
    else:
        categories = get_categories_with_active_users(db)
        if not categories:
            all_cats = get_all(db)
            if not all_cats:
                logger.warning("No search categories. Seed them first.")
            else:
                logger.info(
                    "No categories with active users; skipping scrape. "
                    "Total categories=%d (scrape only runs for categories in use)",
                    len(all_cats),
                )
            return {"total_fetched": 0, "total_deduped": 0, "inserted": 0, "categories": 0}

    logger.info("Fetching jobs for %d categories with active users: %s", len(categories), [c.slug for c in categories])

    with ThreadPoolExecutor(max_workers=min(len(categories), 8)) as executor:
        if results_wanted is None and hours_old is None:
            futures = {executor.submit(_fetch_for_category, c.slug, c.id): c for c in categories}
        else:
            futures = {
                executor.submit(_fetch_for_category, c.slug, c.id, results_wanted, hours_old): c
                for c in categories
            }
        for future in as_completed(futures):
            cat = futures[future]
            try:
                rows = future.result()
                _append_to_shared(rows)
            except Exception as e:
                logger.exception("Thread failed for %s: %s", cat.slug, e)

    total_fetched = len(_shared_results)
    if total_fetched == 0:
        return {"total_fetched": 0, "total_deduped": 0, "inserted": 0, "categories": len(categories)}

    # Global deduplication: drop duplicates by title + company
    df = pd.DataFrame(_shared_results)
    df["title_clean"] = df["title"].astype(str).str.lower().str.strip()
    df["company_clean"] = df["company"].astype(str).str.lower().str.strip()
    df = df.drop_duplicates(subset=["title_clean", "company_clean"], keep="first")
    df = df.drop(columns=["title_clean", "company_clean"])
    deduped = df.to_dict("records")
    total_deduped = len(deduped)

    # Batch upsert per category (ON CONFLICT job_hash DO NOTHING)
    inserted = 0
    by_category: dict[str, list[dict]] = {}
    for r in deduped:
        cid = r.get("search_category_id")
        if cid:
            by_category.setdefault(cid, []).append(r)
    for cid, rows in by_category.items():
        n = batch_upsert(db, rows, cid)
        inserted += n

    logger.info(
        "Collector done: fetched=%d, deduped=%d, inserted=%d",
        total_fetched, total_deduped, inserted,
    )
    return {
        "total_fetched": total_fetched,
        "total_deduped": total_deduped,
        "inserted": inserted,
        "categories": len(categories),
    }
