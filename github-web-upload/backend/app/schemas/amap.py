"""Pydantic schemas for AMap place search and route responses."""

from typing import Optional, List
from pydantic import BaseModel, Field


# ---- Place Search ----
class AmapPlaceItem(BaseModel):
    """Single place result from AMap POI search."""
    poi_id: str = ""
    name: str = ""
    formatted_address: str = ""
    province: str = ""
    city: str = ""
    district: str = ""
    longitude: float = 0.0
    latitude: float = 0.0
    coordinate_system: str = "GCJ02"
    city_match: bool = True  # True if city matches search hint
    type_name: str = ""  # POI type like "科教文化服务;学校;高等院校"


class AmapPlaceSearchResponse(BaseModel):
    """Response for /api/amap/places/search."""
    query: str = ""
    city_hint: str = ""
    source: str = "amap"
    items: List[AmapPlaceItem] = []
    total_count: int = 0
    error: Optional[str] = None


# ---- Route Option ----
class RouteAlternative(BaseModel):
    """A single route option within a mode response."""
    id: str = "route-0"
    label: str = "推荐路线"
    strategy: str = ""
    distance_meters: int = 0
    duration_seconds: int = 0
    price: float = 0.0
    price_label: str = ""
    tolls: float = 0.0
    traffic_lights: int = 0
    summary: str = ""
    amap_nav_url: str = ""
    is_fallback: bool = False


# ---- Multi-route Response ----
class AmapRouteResponse(BaseModel):
    """Multi-route response for /api/amap/route."""
    mode: str = ""
    amap_mode: str = ""
    source: str = "amap"  # amap | fallback
    # Route selection metadata
    selection_policy: str = ""  # "fastest" | "median_price"
    selected_route_index: int = 0
    recommended_index: int = 0
    routes_considered: int = 0
    # Price statistics (taxi only)
    price_statistic: Optional[str] = None  # "median" | "single_amap_estimate" | "fallback_estimate"
    price_sample_count: int = 0
    provider: str = "amap"
    # Routes
    routes: List[RouteAlternative] = []
    warning: Optional[str] = None

    # ---- Backward-compatible top-level fields (from recommended route) ----
    @property
    def distance_meters(self) -> int:
        return self.routes[self.recommended_index].distance_meters if self.routes else 0

    @property
    def duration_seconds(self) -> int:
        return self.routes[self.recommended_index].duration_seconds if self.routes else 0

    @property
    def price(self) -> float:
        return self.routes[self.recommended_index].price if self.routes else 0.0

    @property
    def price_label(self) -> str:
        return self.routes[self.recommended_index].price_label if self.routes else ""

    @property
    def amap_nav_url(self) -> str:
        return self.routes[self.recommended_index].amap_nav_url if self.routes else ""

    # ---- Compatibility dict for existing frontend code ----
    def to_compat_dict(self) -> dict:
        if not self.routes:
            return {}
        r = self.routes[self.recommended_index]
        return {
            "mode": self.mode,
            "amapMode": self.amap_mode,
            "distance_meters": r.distance_meters,
            "duration_seconds": r.duration_seconds,
            "price": r.price,
            "price_label": r.price_label,
            "source": self.source,
            "warning": self.warning,
            "amap_nav_url": r.amap_nav_url,
            "routes": [rt.model_dump() for rt in self.routes],
            "recommended_index": self.recommended_index,
            "selected_route_index": self.selected_route_index,
            "selection_policy": self.selection_policy,
            "routes_considered": self.routes_considered,
            "price_statistic": self.price_statistic,
            "price_sample_count": self.price_sample_count,
            "provider": self.provider,
        }
