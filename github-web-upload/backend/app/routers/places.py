import hmac

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.itinerary import Place
from app.services.place_service import place_service

router = APIRouter(prefix="/api/places", tags=["places"])


class PopularPlacesSeedRequest(BaseModel):
    token: str
    city: str = ""


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
        from scripts.seed_popular_places import seed

        added, existing, failed = seed(data.city.strip())
        return {
            "ok": failed == 0,
            "city": data.city.strip() or "全部",
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
