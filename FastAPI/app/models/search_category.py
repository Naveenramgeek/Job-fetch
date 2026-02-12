from sqlalchemy import Column, String, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class SearchCategory(Base):
    """Canonical search terms - source of truth for job scraping."""

    __tablename__ = "search_categories"

    id = Column(String, primary_key=True, index=True)
    slug = Column(String, unique=True, nullable=False, index=True)
    display_name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    job_listings = relationship("JobListing", back_populates="search_category")
    users = relationship("User", back_populates="search_category")
