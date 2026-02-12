import logging
import sys
import tempfile
from pathlib import Path

# Ensure repo root is on path so "parser" resolves (parser lives outside FastAPI)
_repo_root = Path(__file__).resolve().parents[2]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from fastapi import Depends, FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from parser.resume_parser import build_resume_object

from app.config import settings
from app.core.rate_limiter import rate_limiter
from app.database import init_db, engine
from app.dependencies import get_current_user_full_access
from app.logging_config import setup_logging
from app.routers import admin, auth, resume, jobs

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="JobFetch API",
    description="Auth, resume parsing, job tracking.",
    version="1.0.0",
)

cors_origins = [o.strip() for o in settings.cors_allow_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(resume.router)
app.include_router(jobs.router)
app.include_router(admin.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):
    logger.exception("Unhandled server error on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.middleware("http")
async def apply_rate_limits(request, call_next):
    path = request.url.path
    if request.method == "OPTIONS":
        return await call_next(request)

    client_ip = request.client.host if request.client else "unknown"
    limit = None
    window = 60
    if path in {"/auth/login", "/auth/register", "/auth/forgot-password"}:
        limit = settings.rate_limit_auth_per_min
    elif path == "/parse":
        limit = settings.rate_limit_parse_per_min
    elif path in {"/jobs/tailor-resume-from-jd"} or path.endswith("/tailor-resume"):
        limit = settings.rate_limit_tailor_per_min
    elif path == "/jobs/render-latex-pdf":
        limit = settings.rate_limit_pdf_render_per_min

    if limit is not None and limit > 0:
        key = f"{client_ip}:{path}"
        allowed, retry_after = rate_limiter.allow(key, limit=limit, window_seconds=window)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please retry shortly."},
                headers={"Retry-After": str(retry_after)},
            )

    return await call_next(request)


@app.get("/health/live")
def health_live():
    return {"status": "ok"}


@app.get("/health/ready")
def health_ready():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception:
        logger.exception("Readiness check failed")
        return JSONResponse(status_code=503, content={"status": "not_ready"})


@app.on_event("startup")
def on_startup():
    logger.info("Starting JobFetch API")
    env = (settings.app_env or "development").lower()
    if env in {"production", "prod"}:
        if settings.secret_key == "replace-with-a-long-random-secret-key":
            raise RuntimeError("SECRET_KEY placeholder is not allowed in production")
        if "username:password@" in settings.database_url:
            raise RuntimeError("DATABASE_URL placeholder credentials are not allowed in production")
    else:
        if settings.secret_key == "replace-with-a-long-random-secret-key":
            logger.warning("SECRET_KEY is using placeholder default. Set SECRET_KEY in .env for secure deployments.")
        if "username:password@" in settings.database_url:
            logger.warning("DATABASE_URL appears to use placeholder credentials. Set DATABASE_URL in .env.")
    init_db()


@app.get("/")
def root():
    return {"message": "Resume Parser API. POST a PDF to /parse to get structured resume data."}


@app.post("/parse")
async def parse_resume(
    file: UploadFile = File(..., description="Resume PDF file"),
    ocr_fallback: bool = True,
    _user=Depends(get_current_user_full_access),
):
    """Upload a resume PDF and receive structured data. Requires authentication."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF (.pdf)")

    logger.info("Parsing resume: %s", file.filename)
    suffix = Path(file.filename).suffix or ".pdf"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            max_bytes = settings.max_resume_upload_mb * 1024 * 1024
            if len(content) > max_bytes:
                raise HTTPException(status_code=413, detail=f"File too large. Max allowed is {settings.max_resume_upload_mb}MB.")
            # Basic PDF magic bytes check to reject disguised uploads.
            if not content.startswith(b"%PDF"):
                raise HTTPException(status_code=400, detail="Invalid PDF file content.")
            tmp.write(content)
            tmp_path = tmp.name
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to save upload")
        raise HTTPException(status_code=500, detail="Failed to save upload")

    try:
        data = build_resume_object(tmp_path, ocr_fallback=ocr_fallback)
        for key in ("raw_sections", "raw_text"):
            data.pop(key, None)
        logger.info("Parsed resume: %d experience, %d education", len(data.get("experience", [])), len(data.get("education", [])))
        return data
    except Exception:
        logger.exception("Resume parse failed")
        raise HTTPException(status_code=422, detail="Resume parsing failed. Please check the PDF format.")
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)
