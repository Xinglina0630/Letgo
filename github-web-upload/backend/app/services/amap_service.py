"""
AMap Web API service — place search, route planning, and response parsing.

All external HTTP calls are centralized here so they can be mocked in tests.
"""

from __future__ import annotations

import math
import hashlib
import json
import time
from typing import Optional, List
from urllib.parse import quote

import httpx

from app.config import settings
from app.schemas.amap import (
    AmapPlaceItem, AmapPlaceSearchResponse,
    AmapRouteResponse, RouteAlternative,
)

# ---- Constants ----
AMAP_DIRECTION_BASE = "https://restapi.amap.com/v3/direction"
AMAP_PLACE_BASE = "https://restapi.amap.com/v3/place"
AMAP_GEOCODE_BASE = "https://restapi.amap.com/v3/geocode"

# Transit strategies: 0=best, 1=cheapest, 2=shortest walk, 3=least transfers, 5=metro-first
TRANSIT_STRATEGY_BUS = "0"      # bus: general best / time-efficient
TRANSIT_STRATEGY_SUBWAY = "5"   # subway: metro-first (GAODE strategy 5)

# Driving strategies: 0=recommended, 2=shortest, 3=avoid highway, ...
DRIVING_STRATEGIES = {"0": "recommended", "2": "shortest", "3": "avoid_highway"}

# Distance anomaly threshold (meters)
ANOMALY_DISTANCE_M = 100_000  # 100km — warn if single-city segment exceeds this

# In-memory cache (simple dict, TTL-based. No Redis.)
_cache: dict[str, tuple[float, any]] = {}
_CACHE_TTL_S = 300  # 5 minutes


def _cache_key(*parts: str) -> str:
    return hashlib.md5("|".join(parts).encode()).hexdigest()


def _cache_get(key: str) -> Optional[any]:
    entry = _cache.get(key)
    if entry is None:
        return None
    ts, val = entry
    if time.time() - ts > _CACHE_TTL_S:
        del _cache[key]
        return None
    return val


def _cache_set(key: str, val: any) -> None:
    _cache[key] = (time.time(), val)
    # Prune expired entries if cache gets too large
    if len(_cache) > 500:
        now = time.time()
        expired = [k for k, (ts, _) in _cache.items() if now - ts > _CACHE_TTL_S]
        for k in expired:
            del _cache[k]


def _api_key() -> Optional[str]:
    """Return AMap API key or None if not configured."""
    k = settings.AMAP_API_KEY
    return k.strip() if k else None


# =====================================================================
# Place Search
# =====================================================================

async def search_places(
    keyword: str,
    city: str = "",
    limit: int = 5,
) -> AmapPlaceSearchResponse:
    """
    Search POI by keyword, optionally scoped to a city.
    Falls back to nationwide search if city-scoped returns nothing.
    """
    key = _api_key()
    if not key:
        return AmapPlaceSearchResponse(
            query=keyword, city_hint=city,
            source="amap", items=[],
            error="AMAP_API_KEY 未配置，地点搜索不可用",
        )

    if not keyword or not keyword.strip():
        return AmapPlaceSearchResponse(
            query=keyword, city_hint=city,
            source="amap", items=[],
            error="请提供地点名称或地址",
        )

    kw = keyword.strip()[:100]  # limit keyword length
    limit_val = min(max(1, limit), 10)

    items: List[AmapPlaceItem] = []
    city_scoped_ok = True

    # First attempt: city-scoped search
    if city:
        try:
            async with httpx.AsyncClient(timeout=8) as cl:
                resp = await cl.get(
                    f"{AMAP_PLACE_BASE}/text",
                    params={
                        "key": key, "keywords": kw, "city": city,
                        "offset": limit_val, "page": 1,
                        "extensions": "all",
                    },
                )
                data = resp.json()
            if data.get("status") == "1" and int(data.get("count", 0)) > 0:
                for poi in data.get("pois", []):
                    items.append(_parse_poi(poi, city_match=True))
        except Exception as e:
            return AmapPlaceSearchResponse(
                query=keyword, city_hint=city,
                source="amap", items=[],
                error=f"地点搜索失败，请稍后重试",
            )

    # Second attempt: nationwide search (if city-scoped returned nothing)
    if not items:
        city_scoped_ok = False
        try:
            async with httpx.AsyncClient(timeout=8) as cl:
                resp = await cl.get(
                    f"{AMAP_PLACE_BASE}/text",
                    params={
                        "key": key, "keywords": kw,
                        "offset": limit_val, "page": 1,
                        "extensions": "all",
                    },
                )
                data = resp.json()
            if data.get("status") == "1":
                for poi in data.get("pois", []):
                    item = _parse_poi(poi, city_match=(poi.get("cityname", "") == city))
                    item.city_match = city_scoped_ok or (poi.get("cityname", "") == city)
                    items.append(item)
        except Exception as e:
            if not items:
                return AmapPlaceSearchResponse(
                    query=keyword, city_hint=city,
                    source="amap", items=[],
                    error=f"全国范围搜索也失败，请稍后重试",
                )

    if not items:
        # Final fallback: try geocode
        return await _geocode_fallback(keyword, city, key)

    return AmapPlaceSearchResponse(
        query=keyword, city_hint=city,
        source="amap", items=items,
        total_count=len(items),
    )


async def _geocode_fallback(
    keyword: str, city: str, key: str
) -> AmapPlaceSearchResponse:
    """Fallback: use geocode/regeo for address-like input."""
    try:
        async with httpx.AsyncClient(timeout=8) as cl:
            resp = await cl.get(
                f"{AMAP_GEOCODE_BASE}/geo",
                params={
                    "key": key, "address": keyword,
                    "city": city if city else "",
                },
            )
            data = resp.json()
        if data.get("status") == "1" and data.get("count", "0") != "0":
            geos = data.get("geocodes", [])
            items = []
            for g in geos[:5]:
                loc = g.get("location", "0,0")
                parts = loc.split(",")
                lng = float(parts[0]) if len(parts) == 2 else 0.0
                lat = float(parts[1]) if len(parts) == 2 else 0.0
                cityname = g.get("city", "")
                province = g.get("province", "")
                items.append(AmapPlaceItem(
                    poi_id="",
                    name=g.get("formatted_address", g.get("name", keyword)),
                    formatted_address=g.get("formatted_address", ""),
                    province=province,
                    city=cityname,
                    district=g.get("district", ""),
                    longitude=lng,
                    latitude=lat,
                    coordinate_system="GCJ02",
                    city_match=(cityname == city) if city else True,
                    type_name="",
                ))
            return AmapPlaceSearchResponse(
                query=keyword, city_hint=city,
                source="amap_geocode", items=items,
                total_count=len(items),
            )
    except Exception:
        pass

    return AmapPlaceSearchResponse(
        query=keyword, city_hint=city,
        source="amap", items=[],
        error="没有找到这个地点，请补充城市、区县、道路或门牌号。",
    )


def _parse_poi(poi: dict, city_match: bool = True) -> AmapPlaceItem:
    """Parse a single AMap POI result into AmapPlaceItem."""
    loc = poi.get("location", "0,0")
    parts = loc.split(",")
    lng = float(parts[0]) if len(parts) == 2 else 0.0
    lat = float(parts[1]) if len(parts) == 2 else 0.0

    # Validate coordinate range
    if not (-180 <= lng <= 180 and -90 <= lat <= 90):
        lng, lat = 0.0, 0.0

    return AmapPlaceItem(
        poi_id=poi.get("id", ""),
        name=poi.get("name", ""),
        formatted_address=poi.get("address", ""),
        province=poi.get("pname", ""),
        city=poi.get("cityname", ""),
        district=poi.get("adname", ""),
        longitude=lng,
        latitude=lat,
        coordinate_system="GCJ02",
        city_match=city_match,
        type_name=poi.get("type", ""),
    )


# =====================================================================
# Route Selection Helpers (pure functions, testable)
# =====================================================================

def select_fastest_route(routes: list) -> int:
    """Select the fastest valid route. Returns index of best route.
    Filters invalid routes, then picks by: duration → walking_dist → total_dist → price → original order.
    """
    valid = [(i, r) for i, r in enumerate(routes) if r.duration_seconds > 0]
    if not valid:
        valid = [(i, r) for i, r in enumerate(routes)]
        if not valid:
            return 0

    def sort_key(item):
        i, r = item
        return (
            r.duration_seconds if r.duration_seconds > 0 else 999999,
            getattr(r, 'traffic_lights', 0) or 0,
            r.distance_meters if r.distance_meters > 0 else 999999,
            -r.price if r.price > 0 else 0,
            i,
        )

    best = min(valid, key=sort_key)
    return best[0]


def compute_median_price(prices: list) -> float:
    """Compute median from sorted price list."""
    if not prices:
        return 0.0
    n = len(prices)
    if n % 2 == 1:
        return prices[n // 2]
    return (prices[n // 2 - 1] + prices[n // 2]) / 2.0


def compute_taxi_price_statistic(taxi_cost: float, routes: list) -> dict:
    """Compute taxi price statistic from driving routes.
    Returns dict with: price, price_label, price_statistic, price_sample_count.
    """
    # Collect valid prices: taxi_cost from response + per-route costs
    prices = []
    if taxi_cost > 0:
        prices.append(taxi_cost)

    prices.sort()
    if len(prices) == 0:
        return {
            "price": 0.0, "price_label": "价格暂不可用",
            "price_statistic": "fallback_estimate", "price_sample_count": 0,
        }
    elif len(prices) == 1:
        return {
            "price": prices[0], "price_label": f"高德单一估价 ¥{prices[0]:.0f}",
            "price_statistic": "single_amap_estimate", "price_sample_count": 1,
        }
    else:
        median = compute_median_price(prices)
        return {
            "price": median, "price_label": f"高德估价中位数 ¥{median:.0f}",
            "price_statistic": "median", "price_sample_count": len(prices),
        }


# =====================================================================
# Navigation URI Builder
# =====================================================================

# AMap navigation mode mapping: our mode → amap URI mode
AMAP_NAV_MODE = {
    "walking": "0", "bus": "1", "subway": "1", "transit": "1",
    "taxi": "2", "biking": "4", "bicycling": "4", "driving": "2",
}


def build_amap_navigation_uri(
    origin_lng: float, origin_lat: float, origin_name: str,
    dest_lng: float, dest_lat: float, dest_name: str,
    mode: str = "driving",
) -> str:
    """Build a properly encoded AMap navigation deep-link URI."""
    from urllib.parse import quote, urlencode

    from_param = f"{origin_lng},{origin_lat},{origin_name}"
    to_param = f"{dest_lng},{dest_lat},{dest_name}"
    nav_mode = AMAP_NAV_MODE.get(mode, "2")

    params = urlencode({
        "from": from_param,
        "to": to_param,
        "mode": nav_mode,
        "coordinate": "gaode",
        "callnative": "1",
        "src": "travel-planner",
    }, safe=",")  # commas in coordinate strings should remain unencoded

    return f"https://uri.amap.com/navigation?{params}"


# =====================================================================
# Route Planning
# =====================================================================

# Mode mapping: frontend mode -> AMap API mode
MODE_MAP = {
    "walking": "walking",
    "bus": "transit",
    "subway": "transit",
    "transit": "transit",
    "taxi": "driving",
    "biking": "bicycling",
    "bicycling": "bicycling",
    "driving": "driving",
}

NAV_MODE = {
    "walking": "0", "bus": "1", "subway": "1", "transit": "1",
    "taxi": "2", "biking": "4", "bicycling": "4", "driving": "2",
}


def _nav_url(olng, olat, dlng, dlat, oname, dname, mode) -> str:
    """Build AMap navigation deep-link URL using the unified builder."""
    return build_amap_navigation_uri(olng, olat, oname, dlng, dlat, dname, mode)


def _fallback_response(
    mode: str,
    origin_lat, origin_lng,
    dest_lat, dest_lng,
    origin_name, dest_name,
    reason: str = "",
) -> AmapRouteResponse:
    """Generate a local-estimate fallback route response."""
    r = 6371
    dlat = math.radians(dest_lat - origin_lat)
    dlng = math.radians(dest_lng - origin_lng)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(origin_lat)) *
         math.cos(math.radians(dest_lat)) *
         math.sin(dlng / 2) ** 2)
    km = r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)) * 1.3
    dm = int(km * 1000)

    speeds = {"driving": 40, "transit": 25, "walking": 5, "bicycling": 15}
    am = MODE_MAP.get(mode, mode)
    sp = speeds.get(am, 30)
    ds = int(km / sp * 3600)

    prices = {"driving": 0, "taxi": round(km * 2.5, 2), "bus": round(km * 0.25, 2),
              "subway": round(km * 0.25, 2), "walking": 0, "biking": 0}
    price = prices.get(mode, 0)
    labels = {"driving": "费用待确认", "taxi": "打车预估", "bus": "票价待确认",
              "subway": "票价待确认", "walking": "免费", "biking": "免费"}
    pl = labels.get(mode, "费用待确认")

    nav = _nav_url(origin_lng, origin_lat, dest_lng, dest_lat, origin_name, dest_name, mode)

    return AmapRouteResponse(
        mode=mode, amap_mode=am,
        source="fallback",
        recommended_index=0,
        routes=[RouteAlternative(
            id="route-fallback",
            label="本地估算",
            strategy="fallback",
            distance_meters=dm, duration_seconds=ds,
            price=price, price_label=f"{pl}（粗略估算）",
            amap_nav_url=nav,
            is_fallback=True,
        )],
        warning=f"本地粗略估算，请勿作为出发依据" + (f" ({reason})" if reason else ""),
    )


async def get_route(
    origin_lng: float, origin_lat: float,
    dest_lng: float, dest_lat: float,
    mode: str = "driving",
    origin_name: str = "", dest_name: str = "",
    city: str = "",
    refresh: bool = False,
) -> AmapRouteResponse:
    """Get route(s) from AMap for the specified mode. Returns multiple options."""
    key = _api_key()
    nav = _nav_url(origin_lng, origin_lat, dest_lng, dest_lat, origin_name, dest_name, mode)

    # Check coordinates
    if not (-180 <= origin_lng <= 180 and -90 <= origin_lat <= 90):
        return _fallback_response(mode, origin_lat, origin_lng, dest_lat, dest_lng,
                                  origin_name, dest_name, "起点坐标越界")
    if not (-180 <= dest_lng <= 180 and -90 <= dest_lat <= 90):
        return _fallback_response(mode, origin_lat, origin_lng, dest_lat, dest_lng,
                                  origin_name, dest_name, "终点坐标越界")

    if not key:
        return _fallback_response(mode, origin_lat, origin_lng, dest_lat, dest_lng,
                                  origin_name, dest_name, "AMAP_API_KEY 未配置")

    origin = f"{origin_lng},{origin_lat}"
    dest = f"{dest_lng},{dest_lat}"
    am = MODE_MAP.get(mode, "driving")

    # Cache check
    ck = _cache_key("route", origin, dest, am, city)
    if not refresh:
        cached = _cache_get(ck)
        if cached:
            return cached

    try:
        if am == "bicycling":
            result = await _get_bicycling_routes(key, origin, dest, mode, nav)
        elif am == "walking":
            result = await _get_walking_routes(key, origin, dest, mode, nav)
        elif am == "driving":
            result = await _get_driving_routes(key, origin, dest, mode, origin_name, dest_name, nav)
        elif am == "transit":
            result = await _get_transit_routes(key, origin, dest, city, mode, origin_name, dest_name, nav)
        else:
            result = _fallback_response(mode, origin_lat, origin_lng, dest_lat, dest_lng,
                                        origin_name, dest_name, f"unknown mode {mode}")

        _cache_set(ck, result)
        return result
    except Exception as e:
        msg = str(e)[:80]
        # Don't expose key in error
        if key in msg:
            msg = msg.replace(key, "[KEY]")
        return _fallback_response(mode, origin_lat, origin_lng, dest_lat, dest_lng,
                                  origin_name, dest_name, msg)


async def _get_bicycling_routes(key, origin, dest, mode, nav) -> AmapRouteResponse:
    """V4 bicycling — typically returns single path."""
    async with httpx.AsyncClient(timeout=8) as cl:
        r = await cl.get(
            f"{AMAP_DIRECTION_BASE.replace('/v3', '/v4')}/bicycling",
            params={"key": key, "origin": origin, "destination": dest},
        )
        d = r.json()
    if d.get("errcode") != 0:
        raise ValueError(d.get("errmsg", "bicycling error"))

    paths = d.get("data", {}).get("paths", [])
    routes = []
    for i, p in enumerate(paths[:3]):
        routes.append(RouteAlternative(
            id=f"route-{i}", label="骑行路线" if i == 0 else f"备选{i+1}",
            strategy="bicycling",
            distance_meters=int(p.get("distance", 0)),
            duration_seconds=int(p.get("duration", 0)),
            price=0, price_label="免费（不含共享单车费用）",
            amap_nav_url=nav,
        ))
    if not routes:
        raise ValueError("no bicycling route")

    best_idx = select_fastest_route(routes)
    return AmapRouteResponse(
        mode=mode, amap_mode="bicycling", source="amap",
        selection_policy="fastest",
        selected_route_index=best_idx, recommended_index=best_idx,
        routes_considered=len(routes),
        price_statistic=None, price_sample_count=0,
        provider="amap",
        routes=routes,
    )


async def _get_walking_routes(key, origin, dest, mode, nav) -> AmapRouteResponse:
    """Walking — returns paths."""
    async with httpx.AsyncClient(timeout=8) as cl:
        r = await cl.get(
            f"{AMAP_DIRECTION_BASE}/walking",
            params={"key": key, "origin": origin, "destination": dest},
        )
        d = r.json()
    if d.get("status") != "1":
        raise ValueError(d.get("info", "walking error"))

    paths = d.get("route", {}).get("paths", [])
    routes = []
    for i, p in enumerate(paths[:3]):
        routes.append(RouteAlternative(
            id=f"route-{i}", label="步行路线" if i == 0 else f"备选{i+1}",
            strategy="walking",
            distance_meters=int(p.get("distance", 0)),
            duration_seconds=int(p.get("duration", 0)),
            price=0, price_label="免费",
            amap_nav_url=nav,
        ))
    if not routes:
        raise ValueError("no walking route")

    best_idx = select_fastest_route(routes)
    return AmapRouteResponse(
        mode=mode, amap_mode="walking", source="amap",
        selection_policy="fastest",
        selected_route_index=best_idx, recommended_index=best_idx,
        routes_considered=len(routes),
        price_statistic=None, price_sample_count=0,
        provider="amap",
        routes=routes,
    )


async def _get_driving_routes(key, origin, dest, mode, origin_name, dest_name, nav) -> AmapRouteResponse:
    """Driving — returns routes with fastest selection. Taxi uses median price."""
    async with httpx.AsyncClient(timeout=8) as cl:
        r = await cl.get(
            f"{AMAP_DIRECTION_BASE}/driving",
            params={"key": key, "origin": origin, "destination": dest,
                    "extensions": "all", "strategy": "0", "show_fields": "cost"},
        )
        d = r.json()
    if d.get("status") != "1":
        raise ValueError(d.get("info", "driving error"))

    rt = d.get("route", {})
    paths = rt.get("paths", [])
    taxi_cost = float(rt.get("taxi_cost", 0) or 0)

    seen_sigs = set()
    routes = []
    for i, p in enumerate(paths[:3]):
        dm = int(p.get("distance", 0))
        ds = int(p.get("duration", 0))
        tolls = float(p.get("tolls", 0) or 0)
        tl = int(p.get("traffic_lights", 0) or 0)
        sig = f"{dm}-{ds}"
        if sig in seen_sigs: continue
        seen_sigs.add(sig)
        steps = p.get("steps", [])
        summary = _build_summary(steps)
        strategy_tag = p.get("strategy", "")
        label = _driving_label(i, strategy_tag)

        if mode == "taxi":
            # Price computed after collecting all routes
            routes.append(RouteAlternative(
                id=f"route-{i}", label=label, strategy=strategy_tag,
                distance_meters=dm, duration_seconds=ds,
                price=0.0, price_label="", tolls=tolls, traffic_lights=tl,
                summary=summary, amap_nav_url=nav,
            ))
        else:
            # Driving (not taxi) — tolls + fuel estimate
            price = tolls if tolls > 0 else 0
            pl = ""
            if tolls > 0:
                fuel = round(dm / 1000 * 0.8, 2)
                pl = f"过路费 ¥{tolls:.0f} · 油费估算 ¥{fuel:.0f}"
            else:
                pl = "费用待确认"
            routes.append(RouteAlternative(
                id=f"route-{i}", label=label, strategy=strategy_tag,
                distance_meters=dm, duration_seconds=ds,
                price=price, price_label=pl, tolls=tolls, traffic_lights=tl,
                summary=summary, amap_nav_url=nav,
            ))

    if not routes:
        raise ValueError("no driving route")

    # Select fastest route for driving
    best_idx = select_fastest_route(routes)

    if mode == "taxi":
        # Compute taxi price statistic
        stat = compute_taxi_price_statistic(taxi_cost, routes)
        # Apply price to recommended route
        routes[best_idx].price = stat["price"]
        routes[best_idx].price_label = stat["price_label"]
        return AmapRouteResponse(
            mode=mode, amap_mode="driving", source="amap",
            selection_policy="median_price",
            selected_route_index=best_idx, recommended_index=best_idx,
            routes_considered=len(routes),
            price_statistic=stat["price_statistic"],
            price_sample_count=stat["price_sample_count"],
            provider="amap",
            routes=routes,
        )
    else:
        return AmapRouteResponse(
            mode=mode, amap_mode="driving", source="amap",
            selection_policy="fastest",
            selected_route_index=best_idx, recommended_index=best_idx,
            routes_considered=len(routes),
            price_statistic=None, price_sample_count=0,
            provider="amap",
            routes=routes,
        )


async def _get_transit_routes(key, origin, dest, city, mode, origin_name, dest_name, nav) -> AmapRouteResponse:
    """Transit (bus/subway) — returns up to 3 transits with different strategies."""
    tc = city or "成都"

    # Different strategies for bus vs subway
    if mode == "subway":
        strategy = TRANSIT_STRATEGY_SUBWAY  # 5 = metro-first
        strategy_label = "地铁优先"
    else:
        strategy = TRANSIT_STRATEGY_BUS  # 0 = best/time-efficient
        strategy_label = "公交推荐"

    async with httpx.AsyncClient(timeout=8) as cl:
        r = await cl.get(
            f"{AMAP_DIRECTION_BASE}/transit/integrated",
            params={"key": key, "origin": origin, "destination": dest,
                    "city": tc, "cityd": tc,
                    "extensions": "all", "strategy": strategy},
        )
        d = r.json()
    if d.get("status") != "1":
        raise ValueError(d.get("info", "transit error"))

    transits = d.get("route", {}).get("transits", [])

    seen_sigs = set()
    routes = []
    for i, t in enumerate(transits[:3]):
        dm = int(t.get("distance", 0))
        ds = int(t.get("duration", 0))
        cost = float(t.get("cost", 0) or 0)
        if cost <= 0:
            cost = 2.0

        # Walking distance within transit
        wdist = int(t.get("walking_distance", 0))

        # Dedup
        sig = f"{dm}-{ds}-{cost}"
        if sig in seen_sigs:
            continue
        seen_sigs.add(sig)

        # Build summary from segments
        segs = t.get("segments", [])
        summary = _build_transit_summary(segs)

        # Label
        if i == 0 and mode == "subway":
            label = "地铁优先"
        elif i == 0:
            label = "公交推荐"
        else:
            label = f"备选方案 {i+1}"

        if wdist > 0:
            summary = f"步行{wdist}m → " + summary if summary else ""

        routes.append(RouteAlternative(
            id=f"route-{i}", label=label, strategy=strategy,
            distance_meters=dm, duration_seconds=ds,
            price=cost,
            price_label=f"票价 ¥{cost:.0f}" if cost > 0 else "票价待确认",
            summary=summary,
            amap_nav_url=nav,
        ))

    if not routes:
        raise ValueError("no transit route")

    best_idx = select_fastest_route(routes)
    return AmapRouteResponse(
        mode=mode, amap_mode="transit", source="amap",
        selection_policy="fastest",
        selected_route_index=best_idx, recommended_index=best_idx,
        routes_considered=len(routes),
        price_statistic=None, price_sample_count=0,
        provider="amap",
        routes=routes,
    )


# =====================================================================
# Helpers
# =====================================================================

def _haversine_km(lat1, lng1, lat2, lng2) -> float:
    r = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlng / 2) ** 2)
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _build_summary(steps: list) -> str:
    """Build short road summary from driving steps (max 60 chars)."""
    roads = []
    for s in steps[:5]:
        road = (s.get("road", "") or "").strip()
        if road and road not in roads:
            roads.append(road)
    return " → ".join(roads[:4]) if roads else ""


def _build_transit_summary(segments: list) -> str:
    """Build short transit summary from segments."""
    parts = []
    for seg in segments[:5]:
        bus_info = seg.get("bus", {}) if "bus" in seg else seg.get("railway", {})
        if not bus_info:
            bus_info = seg.get("walking", {})
        name = (bus_info.get("name", "") if isinstance(bus_info, dict) else "") or ""
        if name:
            typ = "🚇" if "railway" in seg else ("🚌" if "bus" in seg else "")
            parts.append(f"{typ}{name}")
    return " → ".join(parts[:3]) if parts else ""


def _driving_label(index: int, strategy_tag: str) -> str:
    """Human-readable driving route label."""
    if index == 0:
        return "高德推荐"
    strategy = strategy_tag.strip() if strategy_tag else ""
    label_map = {
        "0": "推荐路线", "2": "距离最短", "3": "避免拥堵",
        "4": "避免收费", "5": "大路优先",
    }
    return label_map.get(strategy, f"方案{index+1}")
