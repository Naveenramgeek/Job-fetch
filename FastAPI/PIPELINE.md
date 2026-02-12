# Job Collector Pipeline

This document describes the 5-step job fetching and matching pipeline.

## Step 1: Canonical Search Categories (`search_categories` table)

- **Table**: `search_categories` — source of truth for what we scrape
- **Example slugs**: `software_engineer`, `data_scientist`, `mechanical_engineer`, `product_manager`
- **Seeding**: Run `seed_default_categories(db)` on startup or first use
- Add/remove categories in the DB; the collector uses whatever is in the table

## Step 2: Multi-Threaded Collector (configured interval)

- **Script**: `python -m app.scripts.run_collector_pipeline --once` (one run)
- **Script**: `python -m app.scripts.run_collector_pipeline` (runs every `PIPELINE_INTERVAL_SECONDS`)
- **API**: `POST /jobs/run-pipeline` — manually trigger

**Logic**:
1. Pull all rows from `search_categories`
2. Spawn one thread per category via `ThreadPoolExecutor`
3. Each thread calls `fetch_and_deduplicate_jobs` (jobspy) and appends to a shared list
4. Global deduplication with Pandas: `drop_duplicates(subset=["title", "company"])`
5. Batch upsert to `job_listings` using `ON CONFLICT (job_hash) DO NOTHING`

## Step 3: Batch Upsert to Postgres

- **Table**: `job_listings` — raw scraped jobs, not user-specific
- **Key**: `job_hash` = SHA256(title|company|job_url) for deduplication
- `ON CONFLICT (job_hash) DO NOTHING` — ignores duplicates across runs

## Step 4: User-to-Job Mapping (Broad Match)

- **User tagging**: When a user saves/updates a resume, an LLM assigns them to a canonical category (`search_category_id` on `users`)
- **Filter**: For each user, we pull jobs from `job_listings` using configured freshness (`JOB_HOURS_OLD`) that match their `search_category_id`
- These User-Job pairs are queued for deep match scoring

## Step 5: Deep Match (Bedrock LLM Scoring)

- Iterate through User-Job pairs from Step 4
- **LLM prompt** (conceptually): *"User A's resume (Backend Specialist) vs Job X (Senior Frontend Lead). Score 0–100."*
- Store results in `user_job_matches` (user_id, job_listing_id, match_score, match_reason)
- **API**: `GET /jobs/matched` — returns the current user's scored jobs

## Flow Summary

```
search_categories → [ThreadPool] fetch jobs → Pandas dedup → ON CONFLICT upsert → job_listings
                                                                                      ↓
users (search_category_id) ← LLM assign on resume save
                                                                                      ↓
user_job_matches ← LLM score (user, job) pairs for configured recent jobs per category
```

## LLM (AWS Bedrock)

Bedrock is used for ranking and resume tailoring when `BEDROCK_LLM_ENABLED=true`.
Configure `BEDROCK_LLM_MODEL_ID` and `AWS_REGION` in `.env`.

- **Resume–job matching**: `app/services/resume_matcher.py` → `app/services/llm_client.llm_match_resume_job`
- **User category assignment**: `app/services/user_category_service.py`
  - Keyword match first; if no match, `llm_assign_category` maps to existing, or `llm_suggest_generic_slug` creates new category
- **Fallback**: If Bedrock is disabled or fails, deterministic keyword fallback scoring is used.
