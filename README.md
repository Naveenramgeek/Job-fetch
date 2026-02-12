# JobFetch

AI-assisted job discovery, matching, and resume tailoring platform.

JobFetch combines a FastAPI backend, Angular frontend, and PostgreSQL storage to provide:
- Authenticated resume parsing and management
- Matched job listings with status tracking
- AI resume tailoring from either saved jobs or pasted job descriptions
- Admin operations for users, categories, and pipeline controls

---

## System Design at a Glance

```mermaid
flowchart LR
    U[End User] --> UI[Angular SPA UI]
    A[Admin User] --> UI

    UI -->|JWT + REST| API[FastAPI API Layer]
    API --> DB[(PostgreSQL)]

    API --> RP[Resume Parser Module]
    API --> LLM[LLM Client + Titan Embeddings]
    API --> SCH[Pipeline Scheduler]
    SCH --> COL[Job Collector / Fetcher]
    COL --> EXT[External Job Sites]
    COL --> DB

    LLM --> AWS[AWS Bedrock Models]

    CI[GitHub Actions CI] --> API
    CI --> UI
```

---

## Architecture Principles

- **Layered backend architecture**: routers -> services -> repositories -> database.
- **Separation of concerns**: auth, resume, jobs, and admin domains are isolated.
- **Resilience by fallback**: resume tailoring falls back to deterministic structured generation when LLM calls fail.
- **Security-first defaults**: JWT auth, route guards, request rate limiting, and production placeholder checks.
- **Test and quality gates**: backend coverage gate at 90% in CI.

---

## Backend Component Architecture

```mermaid
flowchart TB
    subgraph API["FastAPI App"]
      M["main.py (middleware, health, startup)"]
      R1["auth router"]
      R2["resume router"]
      R3["jobs router"]
      R4["admin router"]
    end

    subgraph Services
      S1["resume_tailor_service"]
      S2["resume_matcher / deep_match_service"]
      S3["job_collector / job_fetcher"]
      S4["pipeline_scheduler"]
      S5["latex_render_service"]
      S6["llm_client / titan_embedding"]
    end

    subgraph Repositories
      Q1["user_repo"]
      Q2["resume_repo"]
      Q3["job_listing_repo"]
      Q4["user_job_match_repo"]
      Q5["admin_repo"]
      Q6["search_category_repo"]
    end

    subgraph Persistence
      D[(PostgreSQL)]
    end

    M --> R1
    M --> R2
    M --> R3
    M --> R4

    R3 --> S1
    R3 --> S2
    R3 --> S3
    R3 --> S4
    R3 --> S5
    R3 --> S6

    R1 --> Q1
    R2 --> Q2
    R3 --> Q3
    R3 --> Q4
    R4 --> Q1
    R4 --> Q5
    R4 --> Q6
    Q1 --> D
    Q2 --> D
    Q3 --> D
    Q4 --> D
    Q5 --> D
    Q6 --> D
```

---

## Core Runtime Flows

### 1) Resume Parse and Save

```mermaid
sequenceDiagram
    participant UI as Angular UI
    participant API as FastAPI
    participant PARSER as parser.resume_parser
    participant DB as PostgreSQL

    UI->>API: POST /parse (PDF, JWT)
    API->>API: validate file + rate limit
    API->>PARSER: build_resume_object()
    PARSER-->>API: structured resume JSON
    UI->>API: POST/PUT /resume
    API->>DB: persist latest resume
    DB-->>API: saved
    API-->>UI: response
```

### 2) Tailor Resume from Job Description

```mermaid
sequenceDiagram
    participant UI as Angular UI
    participant API as jobs router
    participant RS as resume_tailor_service
    participant LLM as Bedrock LLM
    participant PDF as latex_render_service

    UI->>API: POST /jobs/tailor-resume-from-jd
    API->>RS: generate_tailored_latex()
    RS->>LLM: generate structured sections
    LLM-->>RS: tailored sections
    RS-->>API: LaTeX output
    UI->>API: POST /jobs/render-latex-pdf
    API->>PDF: compile LaTeX
    PDF-->>API: PDF bytes
    API-->>UI: preview/download
```

### 3) Job Collection Pipeline

```mermaid
flowchart LR
    T[Scheduler Tick] --> RUN[run_pipeline_once]
    RUN --> FETCH[Fetch jobs from sites]
    FETCH --> DEDUP[Deduplicate + normalize]
    DEDUP --> SCORE[Resume/job matching]
    SCORE --> STORE[Store listings + user matches]
    STORE --> UI[Dashboard refresh]
```

---

## Data Model (Logical ER)

```mermaid
erDiagram
    USER ||--o{ RESUME : has
    USER ||--o{ USER_JOB_MATCH : tracks
    JOB_LISTING ||--o{ USER_JOB_MATCH : mapped_to
    SEARCH_CATEGORY ||--o{ JOB_LISTING : groups

    USER {
      string id PK
      string email
      string password_hash
      bool is_admin
    }

    RESUME {
      string id PK
      string user_id FK
      json structured_data
      datetime created_at
    }

    SEARCH_CATEGORY {
      string id PK
      string title
      string slug
    }

    JOB_LISTING {
      string id PK
      string category_id FK
      string title
      string company
      string url
      datetime created_at
    }

    USER_JOB_MATCH {
      string id PK
      string user_id FK
      string job_listing_id FK
      float match_score
      string status
      datetime applied_at
    }
```

---

## Repository Layout

```text
JobFetchAgent/
├── FastAPI/
│   ├── app/
│   │   ├── core/          # security, rate limiter
│   │   ├── models/        # SQLAlchemy entities
│   │   ├── repos/         # DB access layer
│   │   ├── routers/       # API endpoints by domain
│   │   ├── services/      # business + integration logic
│   │   ├── scripts/       # operational scripts
│   │   └── main.py        # app wiring, middleware, health
│   ├── tests/             # backend tests (pytest)
│   ├── pytest.ini
│   └── requirements.txt
├── parser/                # resume parsing pipeline
├── ui/                    # Angular frontend
│   └── src/app/features/  # auth, dashboard, resume, admin, etc.
└── .github/workflows/     # CI/CD workflows
```

---

## API Surface (High Level)

- **Auth**: register, login, forgot-password, change-password, me/profile, delete account.
- **Resume**: get/update latest structured resume.
- **Jobs**: matched/applied lists, status changes, skip/delete, pipeline control, tailoring + PDF rendering.
- **Admin**: stats, users CRUD, category seed/list, job listing management.
- **Health**: liveness/readiness endpoints.

---

## Security Design

- JWT token-based auth with guarded routes.
- Password hashing and temporary-password rotation flow.
- Endpoint-specific in-memory rate limiting:
  - auth endpoints
  - parse endpoint
  - tailoring endpoints
  - PDF render endpoint
- Startup safety checks to reject placeholder secrets in production mode.

---

## Reliability and Operability

- Global exception handling for stable error responses.
- Ready/live probes for platform health checks.
- Pipeline scheduler controls exposed via API and admin UI.
- Operational scripts for DB init, migration, admin promotion, and pipeline execution.

---

## Testing and Quality Gates

- Backend test framework: `pytest`
- Coverage: `pytest-cov`
- Gate: `--cov-fail-under=90`
- CI workflow runs:
  - Backend tests with coverage artifact upload
  - Frontend production build validation

---

## CI/CD

- **CI**: `/.github/workflows/ci.yml`
  - Runs on push/PR to `main`
  - Validates backend + frontend
- **Deploy**: `/.github/workflows/deploy.yml`
  - Manual trigger
  - SSH-based deployment template (with secrets)

Recommended branch policy:
- Protect `main`
- Require PRs + passing checks + review
- Disable bypass for all users/admins

---

## Local Development Quick Start

See `SETUP.md` for full setup details.

Backend:
```bash
python -m venv venv
source venv/bin/activate
pip install -r FastAPI/requirements.txt
uvicorn FastAPI.app.main:app --reload --reload-dir FastAPI/app --reload-dir parser
```

Frontend:
```bash
cd ui
npm install
npm start
```

---

## Environment Variables

Use `FastAPI/.env.example` as the template. Do not commit real secrets.

Critical vars:
- `DATABASE_URL`
- `SECRET_KEY`
- `APP_ENV`
- `CORS_ALLOW_ORIGINS`
- Bedrock/Titan settings

---

## License and Ownership

© 2026 Naveen Vemula. All rights reserved.
