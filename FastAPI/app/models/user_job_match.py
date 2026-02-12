from sqlalchemy import Column, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class UserJobMatch(Base):
    """User-job pair with LLM match score (deep match result)."""

    __tablename__ = "user_job_matches"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_listing_id = Column(String, ForeignKey("job_listings.id", ondelete="CASCADE"), nullable=False)
    match_score = Column(Float, nullable=False)
    match_reason = Column(String)
    resume_years_experience = Column(Float)
    status = Column(String, default="pending")  # pending | applied | not_applied
    applied_at = Column(DateTime(timezone=True))  # when user marked applied
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="job_matches")
    job_listing = relationship("JobListing", back_populates="user_matches")
