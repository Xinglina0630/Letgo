"""Abstract base classes for external data providers.

All external integrations (flight data, map services, place search, etc.)
must implement these interfaces so they can be swapped without changing
business logic. The mock implementations return realistic demo data.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import date


class FlightDataProvider(ABC):
    """Abstract provider for flight search and pricing data."""

    @abstractmethod
    async def search_flights(
        self,
        departure_city: str,
        arrival_city: str,
        flight_date: date,
        time_period: str = "all",
        passengers: int = 1,
    ) -> List[dict]:
        """Search flights by route and return raw flight dicts."""
        ...

    @abstractmethod
    async def search_flight_by_number(
        self,
        flight_number: str,
        flight_date: date,
        origin: Optional[str] = None,
        destination: Optional[str] = None,
    ) -> Optional[dict]:
        """Search for a specific flight by flight number and date."""
        ...

    @abstractmethod
    async def get_flight_detail(self, flight_id: str) -> Optional[dict]:
        """Get detailed info for a single flight."""
        ...

    @abstractmethod
    async def get_price_history(self, flight_id: str, days: int = 30) -> List[dict]:
        """Get per-platform price history snapshots for a flight."""
        ...

    @abstractmethod
    async def get_platform_quotes(self, flight_id: str) -> List[dict]:
        """Get platform-specific quotes for a flight."""
        ...

    @abstractmethod
    async def get_platform_links(self, flight_id: str) -> List[dict]:
        """Get deep-links for each platform for a specific flight."""
        ...


class PlaceDataProvider(ABC):
    """Abstract provider for place/attraction search."""

    @abstractmethod
    async def search_places(self, city: str, keyword: str = "") -> List[dict]:
        """Search for places/attractions in a city."""
        ...

    @abstractmethod
    async def get_place_detail(self, place_id: str) -> Optional[dict]:
        """Get detailed info for a place."""
        ...


class RouteEstimationProvider(ABC):
    """Abstract provider for route/time/cost estimation between two points."""

    @abstractmethod
    async def estimate_route(
        self,
        origin_name: str,
        origin_address: str,
        origin_lat: float,
        origin_lng: float,
        destination_name: str,
        destination_address: str,
        destination_lat: float,
        destination_lng: float,
        transport_mode: str = "taxi",
    ) -> dict:
        """Estimate time, distance, and cost for a route. Returns AMap deep link."""
        ...


class PredictionProvider(ABC):
    """Abstract provider for flight price prediction.

    Current implementation uses a simple rule-based model.
    The interface is designed so it can be replaced with LightGBM/CatBoost
    without changing any calling code.
    """

    @abstractmethod
    async def predict(
        self,
        flight_id: str,
        price_history: List[dict],
    ) -> dict:
        """Return prediction dict with recommended_date, predicted_lowest, etc."""
        ...
