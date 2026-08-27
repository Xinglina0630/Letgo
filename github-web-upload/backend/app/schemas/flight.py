from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


# --- Search ---
class FlightSearchRequest(BaseModel):
    departure_city: str
    arrival_city: str
    date: str
    time_period: Optional[str] = "all"
    passengers: int = 1


class FlightByNumberRequest(BaseModel):
    flight_number: str
    date: str
    origin: Optional[str] = ""
    destination: Optional[str] = ""


class BaggagePolicyOut(BaseModel):
    id: str
    type_name: str
    weight_kg: float
    pieces: int
    description: str

    class Config:
        from_attributes = True


class RefundChangePolicyOut(BaseModel):
    id: str
    policy_type: str
    time_label: str
    fee_amount: float
    description: str

    class Config:
        from_attributes = True


class PlatformQuoteOut(BaseModel):
    id: str
    platform: str
    platform_name: str
    price: float
    currency: str
    tax_included: bool = True
    cabin_class: str = "economy"
    remaining_seats: int = 5
    baggage_summary: str = ""
    refund_change_summary: str = ""
    booking_url: str = ""
    fallback_url: str = ""
    link_type: str = "fallback-search"
    link_note: str = ""
    is_cheapest: bool = False
    updated_at: str = ""

    class Config:
        from_attributes = True


class PlatformLinkOut(BaseModel):
    platform: str
    platform_name: str
    url: str
    fallbackUrl: str
    linkType: str
    note: str


class FlightOut(BaseModel):
    id: str
    flight_number: str
    airline_code: str = ""
    airline_name: str = ""
    airline_logo: str = ""
    aircraft_type: str = ""
    departure_city: str
    arrival_city: str
    departure_code: str
    arrival_code: str
    departure_airport: str = ""
    arrival_airport: str = ""
    departure_terminal: str = ""
    arrival_terminal: str = ""
    departure_time: Optional[str] = None
    arrival_time: Optional[str] = None
    departure_date: str = ""
    duration_minutes: int = 0
    cabin_class: str = "economy"
    price: float = 0
    currency: str = "CNY"
    stops: int = 0
    on_time_rate: float = 0.9
    baggage_policies: List[BaggagePolicyOut] = None
    refund_change_policies: List[RefundChangePolicyOut] = None
    platform_quotes: List[PlatformQuoteOut] = None
    platform_links: List[PlatformLinkOut] = None

    def model_post_init(self, __context) -> None:
        if self.baggage_policies is None:
            self.baggage_policies = []
        if self.refund_change_policies is None:
            self.refund_change_policies = []
        if self.platform_quotes is None:
            self.platform_quotes = []
        if self.platform_links is None:
            self.platform_links = []

    class Config:
        from_attributes = True


class FlightSearchResponse(BaseModel):
    flights: List[FlightOut]
    total: int
    price_ranking: List[dict]


class FlightByNumberResponse(BaseModel):
    flight: Optional[FlightOut] = None
    error: Optional[str] = None


# --- Detail ---
class FlightPriceSnapshotOut(BaseModel):
    id: str
    date: str
    min_price: float
    avg_price: float = 0
    max_price: float = 0
    sample_count: int = 1

    class Config:
        from_attributes = True


class FlightPriceHistoryOut(BaseModel):
    flight_id: str
    snapshots: List[FlightPriceSnapshotOut]


class PlatformPriceHistoryPoint(BaseModel):
    date: str
    price: float


class PlatformPriceHistoryOut(BaseModel):
    platform: str
    platform_name: str
    prices: List[PlatformPriceHistoryPoint]


class FlightPriceHistoryPerPlatformOut(BaseModel):
    flight_id: str
    history: List[PlatformPriceHistoryOut]


# --- Prediction ---
class PredictionOut(BaseModel):
    flight_id: str
    recommended_buy_date: str
    predicted_lowest_price: float
    current_lowest_price: float
    confidence: float
    price_range_low: float
    price_range_high: float
    trend_direction: str
    reasoning: str
    risk_level: str = "medium"


# --- Platform Trends ---
class PlatformTrendPoint(BaseModel):
    platform: str
    platform_name: str
    dates: List[str]
    prices: List[float]


class PlatformTrendsOut(BaseModel):
    flight_id: str
    trends: List[PlatformTrendPoint]
    cheapest_platform_recently: str
    trend_judgment: str
