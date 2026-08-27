"""Real flight price provider abstraction.

All price providers implement this interface. When no real API key is
configured, UnavailablePriceProvider returns source: "unavailable" so
the frontend shows "暂无实时票价" instead of fake prices.
"""

from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import List, Optional, Dict, Any


class FlightPriceProvider(ABC):
    """Abstract provider for real-time flight price quotes."""

    name: str = ""

    @abstractmethod
    async def search_quotes(
        self,
        flight_number: str,
        departure_city: str,
        arrival_city: str,
        departure_date: date,
        airline_code: str = "",
    ) -> Dict[str, Any]:
        """Search for real-time price quotes. Returns {source, quotes, fetched_at}."""
        ...

    @abstractmethod
    async def get_trend(
        self,
        departure_city: str,
        arrival_city: str,
        departure_date: str,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get price trend from historical DB snapshots. Returns {source, points, disclaimer}."""
        ...


class UnavailablePriceProvider(FlightPriceProvider):
    """Returns source: "unavailable" — no real API keys configured."""

    name = "unavailable"

    async def search_quotes(
        self,
        flight_number: str = "",
        departure_city: str = "",
        arrival_city: str = "",
        departure_date: date = None,
        airline_code: str = "",
    ) -> Dict[str, Any]:
        return {
            "source": "unavailable",
            "quotes": [],
            "fetched_at": None,
            "disclaimer": "暂无实时票价来源，请前往平台查询",
        }

    async def get_trend(
        self,
        departure_city: str = "",
        arrival_city: str = "",
        departure_date: str = "",
        days: int = 30,
    ) -> Dict[str, Any]:
        return {
            "source": "unavailable",
            "points": [],
            "disclaimer": "暂无历史价格数据",
        }
