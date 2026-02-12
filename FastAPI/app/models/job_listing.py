import hashlib
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


def compute_job_hash(title: str, company: str, job_url: str) -> str:
    """Compute deterministic hash for deduplication and ON CONFLICT."""
    key = f"{str(title or '').strip().lower()}|{str(company or '').strip().lower()}|{str(job_url or '').strip()}"
    return hashlib.sha256(key.encode()).hexdigest()


class JobListing(Base):
    """Raw scraped jobs from boards - not user-specific."""

    __tablename__ = "job_listings"

    id = Column(String, primary_key=True, index=True)
    job_hash = Column(String, unique=True, nullable=False, index=True)
    search_category_id = Column(String, ForeignKey("search_categories.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    company = Column(String, nullable=False)
    location = Column(String)
    job_url = Column(String, nullable=False)
    description = Column(Text)
    posted_at = Column(String)
    extra_data = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    search_category = relationship("SearchCategory", back_populates="job_listings")
    user_matches = relationship(
        "UserJobMatch",
        back_populates="job_listing",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
