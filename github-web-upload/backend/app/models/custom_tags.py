"""
Custom place tags — user-created POI tags that can be shared with projects.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey, UniqueConstraint, Index, Text
from sqlalchemy.orm import relationship
from app.database import Base


def _new_id() -> str:
    return uuid.uuid4().hex


class CustomPlaceTag(Base):
    """A user-created place tag, scoped to owner + city."""

    __tablename__ = "custom_place_tags"

    id = Column(String(32), primary_key=True, default=_new_id)
    owner_user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    city = Column(String(64), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    place_type = Column(String(32), default="other", nullable=False)
    address = Column(String(512), default="", nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    coordinate_system = Column(String(16), default="GCJ02", nullable=False)
    amap_poi_id = Column(String(128), default="", nullable=False)
    location_verified = Column(Boolean, default=False, nullable=False)
    opening_time = Column(String(256), default="", nullable=False)
    ticket_price = Column(Float, nullable=True)
    official_url = Column(String(1024), default="", nullable=False)
    status = Column(String(16), default="active", nullable=False)  # active | archived
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    owner = relationship("User")
    project_links = relationship("TravelProjectCustomTag", back_populates="tag", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_custom_tag_owner_city", "owner_user_id", "city"),
    )


class TravelProjectCustomTag(Base):
    """Links a custom place tag to a travel project for sharing."""

    __tablename__ = "travel_project_custom_tags"

    id = Column(String(32), primary_key=True, default=_new_id)
    project_id = Column(String(36), ForeignKey("travel_projects.id"), nullable=False, index=True)
    custom_tag_id = Column(String(32), ForeignKey("custom_place_tags.id"), nullable=False, index=True)
    shared_by_user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    project = relationship("TravelProject")
    tag = relationship("CustomPlaceTag", back_populates="project_links")
    shared_by = relationship("User")

    __table_args__ = (
        UniqueConstraint("project_id", "custom_tag_id", name="uq_project_custom_tag"),
    )
