from fastapi import APIRouter, Query

from app.services.place_service import place_service

router = APIRouter(prefix="/api/places", tags=["places"])


@router.get("/search")
async def search_places(
    city: str = Query(..., description="城市名称"),
    keyword: str = Query("", description="搜索关键词"),
):
    """搜索城市景点/地点。"""
    return await place_service.search(city, keyword)
