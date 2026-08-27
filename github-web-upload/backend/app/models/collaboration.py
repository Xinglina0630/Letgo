"""
Collaboration models: TravelProject, members, invites, events.

A TravelProject represents a shared trip that can contain multiple
itineraries and flight comparison sessions.
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from sqlalchemy import (
    Column, String, Integer, DateTime, ForeignKey, Text, Boolean, UniqueConstraint, Index,
)
from sqlalchemy.orm import relationship
from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


def gen_invite_token() -> str:
    """Generate a cryptographically secure random invite token (128+ bits)."""
    return secrets.token_urlsafe(24)


INVITE_CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


def gen_invite_code() -> str:
    """Generate an easy-to-read 8 character room code."""
    return "".join(secrets.choice(INVITE_CODE_ALPHABET) for _ in range(8))


def hash_token(token: str) -> str:
    """Store only SHA-256 hash of invite tokens, never the raw token."""
    return hashlib.sha256(token.encode()).hexdigest()


# ============================================================================
# TravelProject
# ============================================================================

class TravelProject(Base):
    __tablename__ = "travel_projects"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    owner_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    city = Column(String(100), nullable=False, index=True)
    status = Column(String(20), default="active")  # active | deleted | archived
    version = Column(Integer, default=1)  # optimistic lock for project-level ops
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    members = relationship("TravelProjectMember", back_populates="project", cascade="all, delete-orphan")
    invites = relationship("TravelProjectInvite", back_populates="project", cascade="all, delete-orphan")
    events = relationship("TravelProjectEvent", back_populates="project", cascade="all, delete-orphan")


# ============================================================================
# TravelProjectMember
# ============================================================================

class TravelProjectMember(Base):
    __tablename__ = "travel_project_members"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_user"),
        Index("ix_tpm_project_id", "project_id"),
        Index("ix_tpm_user_id", "user_id"),
    )

    id = Column(String(36), primary_key=True, default=gen_uuid)
    project_id = Column(String(36), ForeignKey("travel_projects.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False, default="viewer")  # owner | editor | viewer
    can_invite = Column(Boolean, default=False)
    status = Column(String(20), default="active")  # active | removed
    joined_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("TravelProject", back_populates="members")
    user = relationship("User")


# ============================================================================
# TravelProjectInvite
# ============================================================================

class TravelProjectInvite(Base):
    __tablename__ = "travel_project_invites"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    project_id = Column(String(36), ForeignKey("travel_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    inviter_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    code_hash = Column(String(64), unique=True, nullable=True, index=True)
    role = Column(String(20), nullable=False, default="viewer")
    scope = Column(String(20), default="all")  # all | itinerary | flights
    can_invite = Column(Boolean, default=False)
    expires_at = Column(DateTime, nullable=False)
    max_uses = Column(Integer, default=1)
    used_count = Column(Integer, default=0)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("TravelProject", back_populates="invites")


# ============================================================================
# TravelProjectEvent
# ============================================================================

class TravelProjectEvent(Base):
    __tablename__ = "travel_project_events"
    __table_args__ = (
        Index("ix_tpe_project_created", "project_id", "created_at"),
    )

    id = Column(String(36), primary_key=True, default=gen_uuid)
    project_id = Column(String(36), ForeignKey("travel_projects.id", ondelete="CASCADE"), nullable=False)
    actor_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    event_type = Column(String(50), nullable=False)
    # event_type examples:
    #   project.created, project.updated,
    #   itinerary.node.created, itinerary.node.updated, itinerary.node.deleted,
    #   itinerary.route.updated,
    #   flight.quote.created, flight.quote.updated, flight.quote.deleted,
    #   member.joined, member.removed, member.role_changed,
    #   invite.created, invite.revoked, invite.accepted,
    entity_type = Column(String(50), nullable=True)
    entity_id = Column(String(36), nullable=True)
    base_version = Column(Integer, nullable=True)
    new_version = Column(Integer, nullable=True)
    summary = Column(String(500), default="")
    change_data = Column(Text, nullable=True)  # JSON blob for detailed changes
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("TravelProject", back_populates="events")
