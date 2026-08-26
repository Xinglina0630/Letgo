"""Flight comparison models: sessions, candidates, quotes, screenshot imports."""

import uuid
from datetime import datetime, date
from sqlalchemy import Column, String, Float, Integer, DateTime, Date, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from app.database import Base

def gen_uuid(): return str(uuid.uuid4())


class FlightSearchSession(Base):
    __tablename__ = "flight_search_sessions"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    project_id = Column(String(36), ForeignKey("travel_projects.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String(200), default="")
    departure_city = Column(String(100), nullable=False)
    arrival_city = Column(String(100), nullable=False)
    departure_date = Column(Date, nullable=False)
    passengers = Column(Integer, default=1)
    cabin = Column(String(20), default="economy")
    mode = Column(String(20), default="compare")
    specific_flight_number = Column(String(20), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    candidates = relationship("FlightCandidate", back_populates="session", cascade="all, delete-orphan")
    quotes = relationship("PlatformFlightQuote", back_populates="session", cascade="all, delete-orphan")


class FlightCandidate(Base):
    __tablename__ = "flight_candidates"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    session_id = Column(String(36), ForeignKey("flight_search_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    flight_number = Column(String(20), default="")
    airline_name = Column(String(100), default="")
    departure_time = Column(String(10), default="")   # HH:MM
    arrival_time = Column(String(10), default="")
    departure_airport = Column(String(100), default="")
    arrival_airport = Column(String(100), default="")
    duration_minutes = Column(Integer, default=0)
    stops = Column(Integer, default=0)
    aircraft = Column(String(50), default="")
    normalized_key = Column(String(200), default="", index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("FlightSearchSession", back_populates="candidates")
    quotes = relationship("PlatformFlightQuote", back_populates="candidate", cascade="all, delete-orphan")


class PlatformFlightQuote(Base):
    __tablename__ = "platform_flight_quotes"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    session_id = Column(String(36), ForeignKey("flight_search_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_id = Column(String(36), ForeignKey("flight_candidates.id", ondelete="CASCADE"), nullable=True, index=True)
    project_id = Column(String(36), ForeignKey("travel_projects.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    platform = Column(String(50), nullable=False)
    platform_name = Column(String(100), default="")
    flight_number = Column(String(20), default="")
    airline_name = Column(String(100), default="")
    departure_time = Column(String(10), default="")
    arrival_time = Column(String(10), default="")
    departure_airport = Column(String(100), default="")
    arrival_airport = Column(String(100), default="")
    price = Column(Float, nullable=False)
    currency = Column(String(10), default="CNY")
    cabin = Column(String(20), default="economy")
    baggage = Column(String(200), default="")
    refund_policy = Column(String(200), default="")
    source = Column(String(20), default="manual")  # manual | paste | ocr | api
    screenshot_id = Column(String(36), default="")
    confirmed_at = Column(DateTime, nullable=True)
    version = Column(Integer, default=1)
    captured_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("FlightSearchSession", back_populates="quotes")
    candidate = relationship("FlightCandidate", back_populates="quotes")


class ScreenshotImport(Base):
    __tablename__ = "screenshot_imports"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    session_id = Column(String(36), ForeignKey("flight_search_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("travel_projects.id", ondelete="SET NULL"), nullable=True, index=True)
    uploader_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    platform = Column(String(50), nullable=False)
    platform_name = Column(String(100), default="")
    image_url = Column(String(500), default="")  # private: only accessible to uploader
    ocr_text = Column(Text, default="")  # private: raw OCR output
    parsed_status = Column(String(20), default="pending")  # pending | parsed | draft | confirmed
    private_visibility = Column(Boolean, default=True)  # True = only uploader can access
    temporary_file_key = Column(String(200), default="")
    parsed_draft = Column(Text, nullable=True)  # JSON draft before confirmation
    expires_at = Column(DateTime, nullable=True)
    file_deleted_at = Column(DateTime, nullable=True)
    confirmed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
