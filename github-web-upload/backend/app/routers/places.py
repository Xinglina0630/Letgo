import hmac

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.itinerary import Place
from app.services.place_service import place_service

router = APIRouter(prefix="/api/places", tags=["places"])


class PopularPlacesSeedRequest(BaseModel):
    token: str
    city: str = ""
    offset: int = Field(default=0, ge=0)
    city_limit: int = Field(default=5, ge=1, le=10)


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


@router.post("/admin/seed-popular")
def seed_popular_places(data: PopularPlacesSeedRequest):
    """Import curated attractions through CloudRun's HTTP debugger."""
    expected = settings.POPULAR_PLACES_SEED_TOKEN.strip()
    if not expected:
        raise HTTPException(503, "POPULAR_PLACES_SEED_TOKEN 尚未配置")
    if not hmac.compare_digest(data.token, expected):
        raise HTTPException(403, "导入口令错误")

    try:
        from scripts.seed_popular_places import destination_cities, seed

        requested_city = data.city.strip()
        all_cities = destination_cities()
        if requested_city:
            batch_cities = [requested_city]
            added, existing, failed = seed(requested_city)
            next_offset = None
            done = True
        else:
            batch_cities = all_cities[data.offset:data.offset + data.city_limit]
            added, existing, failed = seed("", data.offset, data.city_limit)
            next_value = data.offset + len(batch_cities)
            done = next_value >= len(all_cities)
            next_offset = None if done else next_value
        return {
            "ok": failed == 0,
            "city": requested_city or "批量",
            "batch_cities": batch_cities,
            "offset": data.offset if not requested_city else None,
            "next_offset": next_offset,
            "done": done,
            "total_cities": len(all_cities),
            "added": added,
            "existing": existing,
            "failed": failed,
        }
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, f"景点导入失败：{type(exc).__name__}") from exc


@router.get("/search")
async def search_places(
    city: str = Query(..., description="城市名称"),
    keyword: str = Query("", description="搜索关键词"),
):
    """搜索城市景点/地点。"""
    return await place_service.search(city, keyword)
