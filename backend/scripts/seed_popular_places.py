"""Seed curated popular attractions into MySQL and resolve locations with AMap.

Usage inside the CloudRun container:
    python scripts/seed_popular_places.py
    python scripts/seed_popular_places.py --city 杭州

The operation is idempotent by (city, name): existing rows are not duplicated.
"""

import argparse
import json
import sys
from pathlib import Path

import httpx

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings
from app.database import get_session_local
from app.models.itinerary import Place

AMAP_TEXT_URL = "https://restapi.amap.com/v3/place/text"
DATA_FILE = BACKEND_DIR / "data" / "popular_destinations.json"


def resolve_place(client: httpx.Client, key: str, province: str, city: str, name: str) -> dict | None:
    response = client.get(AMAP_TEXT_URL, params={
        "key": key,
        "keywords": name,
        "city": city,
        "citylimit": "true",
        "offset": 5,
        "page": 1,
        "extensions": "base",
    })
    response.raise_for_status()
    data = response.json()
    if data.get("status") != "1" or not data.get("pois"):
        print(f"SKIP {province}/{city}/{name}: {data.get('info', 'no POI')}")
        return None
    poi = data["pois"][0]
    raw_location = poi.get("location", "")
    if "," not in raw_location:
        print(f"SKIP {province}/{city}/{name}: no coordinates")
        return None
    lng, lat = (float(v) for v in raw_location.split(",", 1))
    address = poi.get("address")
    if isinstance(address, list):
        address = "".join(str(v) for v in address)
    return {
        "name": poi.get("name") or name,
        "address": str(address or ""),
        "latitude": lat,
        "longitude": lng,
        "description": f"高德地点类型：{poi.get('type', '')}",
    }


def seed(city_filter: str = "") -> tuple[int, int, int]:
    key = settings.AMAP_API_KEY.strip()
    if not key:
        raise RuntimeError("AMAP_API_KEY is required")

    destinations = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    if city_filter:
        destinations = [d for d in destinations if d["city"] == city_filter]
        if not destinations:
            raise RuntimeError(f"Unknown city in seed data: {city_filter}")

    inserted = skipped = failed = 0
    db = get_session_local()()
    try:
        with httpx.Client(timeout=12) as client:
            for destination in destinations:
                province, city = destination["province"], destination["city"]
                for rank, requested_name in enumerate(destination["places"], start=1):
                    exists = db.query(Place).filter(
                        Place.city == city,
                        Place.name == requested_name,
                    ).first()
                    if exists:
                        skipped += 1
                        continue
                    try:
                        resolved = resolve_place(client, key, province, city, requested_name)
                        if not resolved:
                            failed += 1
                            continue
                        db.add(Place(
                            name=requested_name, city=city,
                            address=resolved["address"], place_type="attraction",
                            latitude=resolved["latitude"], longitude=resolved["longitude"],
                            opening_time="请以景区当日公告为准", ticket_price=0,
                            rating=round(5.0 - rank * 0.1, 1),
                            description=resolved["description"],
                            tags=f"热门,{province},{city}",
                        ))
                        db.commit()
                        inserted += 1
                        print(f"ADD  {province}/{city}/{requested_name}")
                    except Exception as exc:
                        db.rollback()
                        failed += 1
                        print(f"FAIL {province}/{city}/{requested_name}: {type(exc).__name__}")
    finally:
        db.close()
    return inserted, skipped, failed


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--city", default="", help="Seed only one city")
    args = parser.parse_args()
    added, existing, failed = seed(args.city)
    print(f"DONE added={added} existing={existing} failed={failed}")
