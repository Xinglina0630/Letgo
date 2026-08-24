from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.itinerary import Place
from app.services.place_service import place_service

router = APIRouter(prefix="/api/places", tags=["places"])


@router.get("/popular")
async def popular_places(
    city: str = Query(..., min_length=1),
    limit: int = Query(12, ge=1, le=30),
    db: Session = Depends(get_db),
):
    """Return curated popular places stored in MySQL for a city."""
    items = (
        db.query(Place)
        .filter(Place.city == city)
        .order_by(Place.rating.desc(), Place.name.asc())
        .limit(limit)
        .all()
    )
    return {"city": city, "places": items, "source": "mysql"}


@router.get("/search")
async def search_places(
    city: str = Query(..., description="城市名称"),
    keyword: str = Query("", description="搜索关键词"),
):
    """搜索城市景点/地点。"""
    return await place_service.search(city, keyword)
