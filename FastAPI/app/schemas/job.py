from pydantic import BaseModel, Field


class JobFetchParams(BaseModel):
    """Optional overrides; if not provided, use resume contact title/location."""

    search_term: str | None = None
    location: str | None = None
    results_wanted: int = 100
    hours_old: int = 2


class JobMatchResult(BaseModel):
    id: str
    title: str
    company: str
    location: str | None
    job_url: str
    description: str | None
    site: str | None
    posted_at: str | None
    created_at: str | None = None  # When job was collected (for age/freshness)
    match_score: float
    match_reason: str | None
    resume_years_experience: float | None = None
    applied_at: str | None = None


class JobStatusUpdate(BaseModel):
    status: str  # "applied" | "not_applied"


class TailoredResumeResponse(BaseModel):
    match_id: str
    job_title: str
    company: str
    latex: str


class TailorResumeFromJdRequest(BaseModel):
    job_description: str = Field(min_length=20, max_length=50000)
    job_title: str | None = Field(default=None, max_length=200)


class LatexRenderRequest(BaseModel):
    latex: str = Field(min_length=1, max_length=200000)
