"""Place search service."""

from typing import Optional

from app.adapters.base import PlaceDataProvider
from app.adapters.mock_provider import MockPlaceDataProvider


class PlaceService:
    def __init__(self, provider: Optional[PlaceDataProvider] = None):
        self.provider = provider or MockPlaceDataProvider()

    async def search(self, city: str, keyword: str = "") -> dict:
        places = await self.provider.search_places(city, keyword)
        return {"places": places, "city": city}

    async def get_detail(self, place_id: str) -> Optional[dict]:
        return await self.provider.get_place_detail(place_id)


place_service = PlaceService()
