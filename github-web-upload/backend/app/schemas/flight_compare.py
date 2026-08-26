"""Schemas for flight comparison API."""

from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel


# ---- Session ----
class SessionCreate(BaseModel):
    departure_city: str
    arrival_city: str
    departure_date: str  # YYYY-MM-DD
    passengers: int = 1
    cabin: str = "economy"
    mode: str = "compare"
    specific_flight_number: str = ""
    name: str = ""

class SessionOut(BaseModel):
    id: str; name: str; departure_city: str; arrival_city: str
    departure_date: str; passengers: int; cabin: str; mode: str
    specific_flight_number: str; created_at: Optional[str] = None; updated_at: Optional[str] = None

    class Config: from_attributes = True

    @classmethod
    def from_orm_obj(cls, obj):
        """Convert SQLAlchemy object with date fields to Pydantic model."""
        return cls(
            id=obj.id, name=obj.name or "",
            departure_city=obj.departure_city, arrival_city=obj.arrival_city,
            departure_date=obj.departure_date.isoformat() if hasattr(obj.departure_date, "isoformat") else str(obj.departure_date),
            passengers=obj.passengers or 1, cabin=obj.cabin or "economy",
            mode=obj.mode or "compare", specific_flight_number=obj.specific_flight_number or "",
            created_at=obj.created_at.isoformat() if obj.created_at else None,
            updated_at=obj.updated_at.isoformat() if obj.updated_at else None,
        )

# ---- Quote ----
class QuoteCreate(BaseModel):
    session_id: str
    platform: str; platform_name: str = ""
    flight_number: str = ""; airline_name: str = ""
    departure_time: str = ""; arrival_time: str = ""
    departure_airport: str = ""; arrival_airport: str = ""
    price: float; currency: str = "CNY"; cabin: str = "economy"
    baggage: str = ""; refund_policy: str = ""
    source: str = "manual"; screenshot_id: str = ""

class QuoteOut(BaseModel):
    id: str; session_id: str; candidate_id: Optional[str] = None
    platform: str; platform_name: str
    flight_number: str; airline_name: str
    departure_time: str; arrival_time: str
    departure_airport: str; arrival_airport: str
    price: float; currency: str; cabin: str
    baggage: str; refund_policy: str
    source: str; captured_at: Optional[str] = None; created_at: Optional[str] = None
    class Config: from_attributes = True

# ---- Paste Parse ----
class PasteParseRequest(BaseModel):
    platform: str; platform_name: str = ""
    text: str; session_id: str

class PasteParseResult(BaseModel):
    quotes: List[QuoteCreate] = None

    def model_post_init(self, __context) -> None:
        if self.quotes is None:
            self.quotes = []

# ---- Candidate (aggregated) ----
class CandidateOut(BaseModel):
    id: str; session_id: str; flight_number: str; airline_name: str
    departure_time: str; arrival_time: str
    departure_airport: str; arrival_airport: str
    duration_minutes: int; stops: int; aircraft: str; normalized_key: str
    quotes: List[QuoteOut] = []
    class Config: from_attributes = True

# ---- Aggregation result ----
class AggregatedRow(BaseModel):
    flight_number: str; airline_name: str
    departure_time: str; arrival_time: str
    departure_airport: str; arrival_airport: str
    duration_minutes: int; stops: int
    platform_prices: dict  # {platform_name: price}
    lowest_price: Optional[float] = None
    lowest_platform: str = ""
    candidate_id: str = ""

class SessionDetail(BaseModel):
    session: SessionOut
    candidates: List[AggregatedRow] = None
    quote_count: int = 0

    def model_post_init(self, __context) -> None:
        if self.candidates is None:
            self.candidates = []
