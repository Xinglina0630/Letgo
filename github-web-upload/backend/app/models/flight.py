import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, Text, Boolean, Enum as SAEnum
from sqlalchemy.orm import relationship
import enum

from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class CabinClass(str, enum.Enum):
    ECONOMY = "economy"
    PREMIUM_ECONOMY = "premium_economy"
    BUSINESS = "business"
    FIRST = "first"


class Flight(Base):
    __tablename__ = "flights"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    flight_number = Column(String(20), nullable=False, index=True)
    airline = Column(String(100), nullable=False)
    airline_logo = Column(String(255), default="")
    departure_city = Column(String(100), nullable=False)
    departure_airport = Column(String(100), nullable=False)
    departure_code = Column(String(10), nullable=False)
    arrival_city = Column(String(100), nullable=False)
    arrival_airport = Column(String(100), nullable=False)
    arrival_code = Column(String(10), nullable=False)
    departure_time = Column(DateTime, nullable=False)
    arrival_time = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    cabin_class = Column(String(20), default="economy")
    price = Column(Float, nullable=False)
    currency = Column(String(10), default="CNY")
    stops = Column(Integer, default=0)
    aircraft_type = Column(String(50), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    price_snapshots = relationship("FlightPriceSnapshot", back_populates="flight", cascade="all, delete-orphan")
    platform_quotes = relationship("PlatformQuote", back_populates="flight", cascade="all, delete-orphan")
    baggage_policies = relationship("BaggagePolicy", back_populates="flight", cascade="all, delete-orphan")
    refund_change_policies = relationship("RefundChangePolicy", back_populates="flight", cascade="all, delete-orphan")


class FlightPriceSnapshot(Base):
    __tablename__ = "flight_price_snapshots"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    flight_id = Column(String(36), ForeignKey("flights.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(DateTime, nullable=False)
    min_price = Column(Float, nullable=False)
    avg_price = Column(Float, nullable=False)
    max_price = Column(Float, nullable=False)
    sample_count = Column(Integer, default=1)

    flight = relationship("Flight", back_populates="price_snapshots")


class PlatformQuote(Base):
    __tablename__ = "platform_quotes"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    flight_id = Column(String(36), ForeignKey("flights.id", ondelete="CASCADE"), nullable=False, index=True)
    platform = Column(String(50), nullable=False)
    platform_name = Column(String(100), nullable=False)
    price = Column(Float, nullable=False)
    currency = Column(String(10), default="CNY")
    booking_url = Column(String(500), default="")
    quote_date = Column(DateTime, nullable=False)
    is_cheapest = Column(Boolean, default=False)

    flight = relationship("Flight", back_populates="platform_quotes")


class BaggagePolicy(Base):
    __tablename__ = "baggage_policies"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    flight_id = Column(String(36), ForeignKey("flights.id", ondelete="CASCADE"), nullable=False, index=True)
    type_name = Column(String(50), nullable=False)
    weight_kg = Column(Float, nullable=False)
    pieces = Column(Integer, default=1)
    description = Column(String(255), default="")

    flight = relationship("Flight", back_populates="baggage_policies")


class RefundChangePolicy(Base):
    __tablename__ = "refund_change_policies"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    flight_id = Column(String(36), ForeignKey("flights.id", ondelete="CASCADE"), nullable=False, index=True)
    policy_type = Column(String(50), nullable=False)
    time_label = Column(String(100), nullable=False)
    fee_amount = Column(Float, nullable=False)
    description = Column(String(255), default="")

    flight = relationship("Flight", back_populates="refund_change_policies")
