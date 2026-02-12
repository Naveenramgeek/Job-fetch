from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    search_category_id = Column(String, ForeignKey("search_categories.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    temp_password_hash = Column(String, nullable=True)
    temp_password_expires_at = Column(DateTime(timezone=True), nullable=True)

    resumes = relationship("Resume", back_populates="user")
    jobs = relationship("Job", back_populates="user")
    search_category = relationship("SearchCategory", back_populates="users")
    job_matches = relationship("UserJobMatch", back_populates="user")
