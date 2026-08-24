"""AMap route and place search API endpoints."""

from typing import Optional
from fastapi import APIRouter, Query, HTTPException

from app.schemas.amap import AmapPlaceSearchResponse, AmapRouteResponse
from app.services.amap_service import search_places, get_route, MODE_MAP

router = APIRouter(prefix="/api/amap", tags=["amap"])

VALID_MODES = {"walking", "bus", "subway", "taxi", "biking", "bicycling", "driving", "transit"}


@router.get("/status")
async def amap_status():
    """Return AMap service status without exposing the key."""
    from app.config import settings as s
    return {
        "configured": bool(s.AMAP_API_KEY and s.AMAP_API_KEY.strip()),
        "service": "amap",
    }


# =====================================================================
# Place Search
# =====================================================================
@router.get("/places/search", response_model=AmapPlaceSearchResponse)
async def amap_places_search(
    keyword: str = Query(..., description="地点名称或地址"),
    city: str = Query("", description="搜索城市提示"),
    limit: int = Query(5, ge=1, le=10, description="返回数量"),
):
    """
    Search POI by keyword using AMap Place API.
    Falls back to geocode if POI search returns no results.
    """
    if not keyword or not keyword.strip():
        raise HTTPException(status_code=422, detail="请提供地点名称或地址")
    if len(keyword) > 200:
        raise HTTPException(status_code=422, detail="关键词过长（最多200字符）")

    return await search_places(keyword=keyword.strip(), city=city.strip(), limit=limit)


# =====================================================================
# Route Planning (multi-route)
# =====================================================================
@router.get("/route")
async def amap_route(
    origin_lng: float = Query(...),
    origin_lat: float = Query(...),
    dest_lng: float = Query(...),
    dest_lat: float = Query(...),
    mode: str = Query("driving"),
    origin_name: str = Query(""),
    dest_name: str = Query(""),
    city: str = Query(""),
):
    """
    Get route(s) from AMap supporting multiple alternatives.
    Returns up to 3 driving routes, 3 transit routes, or 3 walking/bicycling routes.
    """
    if mode not in VALID_MODES:
        raise HTTPException(status_code=422, detail=f"不支持的交通方式: {mode}")

    # Coordinate validation
    if not (-180 <= origin_lng <= 180 and -90 <= origin_lat <= 90):
        raise HTTPException(status_code=422, detail="起点坐标越界")
    if not (-180 <= dest_lng <= 180 and -90 <= dest_lat <= 90):
        raise HTTPException(status_code=422, detail="终点坐标越界")

    result: AmapRouteResponse = await get_route(
        origin_lng=origin_lng, origin_lat=origin_lat,
        dest_lng=dest_lng, dest_lat=dest_lat,
        mode=mode, origin_name=origin_name, dest_name=dest_name,
        city=city,
    )

    # Return compat dict format for seamless frontend transition
    return result.to_compat_dict()
