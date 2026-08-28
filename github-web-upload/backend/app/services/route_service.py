"""Route estimation service."""

import asyncio
from typing import Optional

from app.adapters.base import RouteEstimationProvider
from app.adapters.mock_provider import MockRouteEstimationProvider


class RouteService:
    def __init__(self, provider: Optional[RouteEstimationProvider] = None):
        self.provider = provider or MockRouteEstimationProvider()

    async def estimate(
        self,
        origin_name: str = "",
        origin_address: str = "",
        origin_lat: float = 0,
        origin_lng: float = 0,
        destination_name: str = "",
        destination_address: str = "",
        destination_lat: float = 0,
        destination_lng: float = 0,
        transport_mode: str = "taxi",
    ) -> dict:
        try:
            return await asyncio.wait_for(
                self.provider.estimate_route(
                    origin_name=origin_name,
                    origin_address=origin_address,
                    origin_lat=origin_lat,
                    origin_lng=origin_lng,
                    destination_name=destination_name,
                    destination_address=destination_address,
                    destination_lat=destination_lat,
                    destination_lng=destination_lng,
                    transport_mode=transport_mode,
                ),
                timeout=5.0,
            )
        except asyncio.TimeoutError:
            # Return fallback estimate on timeout
            return self._fallback_estimate(
                origin_name, origin_lat, origin_lng,
                destination_name, destination_lat, destination_lng,
                transport_mode,
            )

    def _fallback_estimate(
        self,
        origin_name: str, origin_lat: float, origin_lng: float,
        dest_name: str, dest_lat: float, dest_lng: float,
        transport_mode: str,
    ) -> dict:
        """Local haversine fallback."""
        import math
        from urllib.parse import quote

        R = 6371
        dlat = math.radians(dest_lat - origin_lat)
        dlng = math.radians(dest_lng - origin_lng)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(origin_lat)) * math.cos(math.radians(dest_lat)) *
             math.sin(dlng / 2) ** 2)
        km = R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)) * 1.3
        dist_m = int(km * 1000)

        speeds = {"walking": 5, "biking": 15, "bus": 25, "subway": 35, "taxi": 40, "driving": 40}
        costs = {"walking": 0, "biking": 0, "bus": 0.15, "subway": 0.25, "taxi": 2.5, "driving": 1.5}
        amap_modes = {"walking": "0", "biking": "4", "bus": "1", "subway": "1", "taxi": "2", "driving": "2"}

        speed = speeds.get(transport_mode, 30)
        cost_per_km = costs.get(transport_mode, 1.0)
        time_min = max(3, int(km / speed * 60))

        if transport_mode == "taxi":
            candidates = sorted([km * cost_per_km * (0.9 + 0.04 * i) for i in range(8)])
            cost = round(sum(candidates[:5]) / len(candidates[:5]), 2)
            cost_expl = "后端超时，使用本地离线估算（取最低5个候选平均值）"
        else:
            cost = round(km * cost_per_km, 2)
            cost_expl = "后端超时，使用本地离线估算"

        alternatives = []
        for mode, s in speeds.items():
            alt_time = max(3, int(km / s * 60))
            alt_cost = round(km * costs.get(mode, 0), 2)
            alternatives.append({"mode": mode, "duration_minutes": alt_time, "distance_meters": dist_m, "estimated_cost": alt_cost})

        amap_url = (
            f"https://uri.amap.com/navigation?"
            f"from={quote(f'{origin_lng},{origin_lat},{origin_name}')}"
            f"&to={quote(f'{dest_lng},{dest_lat},{dest_name}')}"
            f"&mode={amap_modes.get(transport_mode, '2')}"
        )

        return {
            "mode": transport_mode,
            "distance_meters": dist_m,
            "duration_minutes": time_min,
            "estimated_cost": cost,
            "cost_explanation": cost_expl,
            "amap_route_url": amap_url,
            "alternatives": alternatives,
        }


route_service = RouteService()
