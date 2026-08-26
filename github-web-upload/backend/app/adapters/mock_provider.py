"""Mock implementations of all provider interfaces.

These return realistic demo data sufficient to run the full UI flow.
Replace with real API adapters (CtripAdapter, AmapAdapter, etc.) in production.
"""

import uuid
import random
import math
from datetime import date, datetime, timedelta
from typing import List, Optional

from app.adapters.base import FlightDataProvider, PlaceDataProvider, RouteEstimationProvider, PredictionProvider


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AIRPORTS = {
    "北京": [("PEK", "首都国际机场", "T3"), ("PKX", "大兴国际机场", "T1")],
    "上海": [("PVG", "浦东国际机场", "T2"), ("SHA", "虹桥国际机场", "T2")],
    "广州": [("CAN", "白云国际机场", "T1")],
    "深圳": [("SZX", "宝安国际机场", "T3")],
    "成都": [("CTU", "双流国际机场", "T2"), ("TFU", "天府国际机场", "T1")],
    "杭州": [("HGH", "萧山国际机场", "T3")],
    "重庆": [("CKG", "江北国际机场", "T3")],
    "武汉": [("WUH", "天河国际机场", "T3")],
    "西安": [("XIY", "咸阳国际机场", "T3")],
    "南京": [("NKG", "禄口国际机场", "T2")],
    "昆明": [("KMG", "长水国际机场", "T1")],
    "三亚": [("SYX", "凤凰国际机场", "T1")],
    "厦门": [("XMN", "高崎国际机场", "T4")],
    "长沙": [("CSX", "黄花国际机场", "T2")],
}

AIRLINES = {
    "CA": ("中国国航", "https://www.airchina.com.cn"),
    "MU": ("东方航空", "https://www.ceair.com"),
    "CZ": ("南方航空", "https://www.csair.com"),
    "HU": ("海南航空", "https://www.hnair.com"),
    "3U": ("四川航空", "https://www.sichuanair.com"),
    "ZH": ("深圳航空", "https://www.shenzhenair.com"),
    "MF": ("厦门航空", "https://www.xiamenair.com"),
    "GS": ("天津航空", "https://www.tianjin-air.com"),
    "FM": ("上海航空", "https://www.shanghai-air.com"),
    "9C": ("春秋航空", "https://www.ch.com"),
}

PLATFORMS = [
    ("airline_official", "航司官网"),
    ("ctrip", "携程"),
    ("feizhu", "飞猪"),
    ("qunar", "去哪儿"),
    ("tongcheng", "同程"),
    ("zhixing", "智行旅行"),
]

PLATFORM_BASE_URLS = {
    "ctrip": "https://flights.ctrip.com",
    "feizhu": "https://www.fliggy.com",
    "qunar": "https://flight.qunar.com",
    "tongcheng": "https://www.ly.com/flights/home",
    "zhixing": "https://www.zx12306.com",
}

MOCK_FLIGHT_TEMPLATES = [
    {"fn": "CA1234", "al": "CA", "dep_hour": 7, "dep_min": 30, "dur": 150, "stops": 0, "aircraft": "Boeing 737-800"},
    {"fn": "MU5678", "al": "MU", "dep_hour": 9, "dep_min": 15, "dur": 165, "stops": 0, "aircraft": "Airbus A320neo"},
    {"fn": "CZ9012", "al": "CZ", "dep_hour": 11, "dep_min": 0, "dur": 145, "stops": 0, "aircraft": "Airbus A321"},
    {"fn": "HU3456", "al": "HU", "dep_hour": 13, "dep_min": 45, "dur": 180, "stops": 1, "aircraft": "Boeing 787-9"},
    {"fn": "3U7890", "al": "3U", "dep_hour": 15, "dep_min": 20, "dur": 155, "stops": 0, "aircraft": "Airbus A330"},
    {"fn": "ZH1111", "al": "ZH", "dep_hour": 17, "dep_min": 50, "dur": 160, "stops": 0, "aircraft": "Boeing 737 MAX"},
    {"fn": "MF2222", "al": "MF", "dep_hour": 19, "dep_min": 10, "dur": 170, "stops": 1, "aircraft": "Boeing 787-8"},
    {"fn": "GS3333", "al": "GS", "dep_hour": 21, "dep_min": 30, "dur": 140, "stops": 0, "aircraft": "Embraer E190"},
]

CITIES = {
    "北京": (39.9042, 116.4074),
    "上海": (31.2304, 121.4737),
    "广州": (23.1291, 113.2644),
    "深圳": (22.5431, 114.0579),
    "成都": (30.5728, 104.0668),
    "杭州": (30.2741, 120.1551),
    "重庆": (29.4316, 106.9123),
    "武汉": (30.5928, 114.3055),
    "西安": (34.3416, 108.9398),
    "南京": (32.0603, 118.7969),
    "昆明": (25.0389, 102.7183),
    "三亚": (18.2528, 109.5120),
    "厦门": (24.4798, 118.0894),
    "长沙": (28.2282, 112.9388),
}

ATTRACTIONS = {
    "北京": [
        {"name": "故宫博物院", "lat": 39.9163, "lng": 116.3972, "type": "attraction",
         "open": "08:30-17:00", "ticket": 60, "rating": 4.8, "desc": "明清两代皇家宫殿", "tags": "历史文化,世界遗产,博物馆"},
        {"name": "颐和园", "lat": 39.9999, "lng": 116.2755, "type": "attraction",
         "open": "06:30-18:00", "ticket": 30, "rating": 4.7, "desc": "中国现存最大的皇家园林", "tags": "园林,世界遗产,自然风光"},
        {"name": "八达岭长城", "lat": 40.3597, "lng": 116.0204, "type": "attraction",
         "open": "06:30-16:30", "ticket": 40, "rating": 4.8, "desc": "万里长城的精华段", "tags": "世界遗产,历史,户外"},
    ],
    "上海": [
        {"name": "外滩", "lat": 31.2400, "lng": 121.4905, "type": "attraction",
         "open": "全天开放", "ticket": 0, "rating": 4.8, "desc": "黄浦江畔万国建筑博览群", "tags": "地标,夜景,免费"},
        {"name": "东方明珠", "lat": 31.2397, "lng": 121.4998, "type": "attraction",
         "open": "08:00-21:30", "ticket": 199, "rating": 4.5, "desc": "上海标志性广播电视塔", "tags": "地标,观景,城市"},
        {"name": "迪士尼乐园", "lat": 31.1433, "lng": 121.6620, "type": "attraction",
         "open": "08:30-20:30", "ticket": 475, "rating": 4.7, "desc": "中国大陆首座迪士尼主题乐园", "tags": "主题乐园,亲子,娱乐"},
    ],
    "成都": [
        {"name": "宽窄巷子", "lat": 30.6681, "lng": 104.0521, "type": "attraction",
         "open": "全天开放", "ticket": 0, "rating": 4.5, "desc": "清朝古街道", "tags": "古街,美食,文化"},
        {"name": "大熊猫繁育研究基地", "lat": 30.7355, "lng": 104.1448, "type": "attraction",
         "open": "07:30-18:00", "ticket": 55, "rating": 4.8, "desc": "近距离观赏大熊猫", "tags": "熊猫,自然,亲子"},
        {"name": "都江堰", "lat": 30.9980, "lng": 103.6143, "type": "attraction",
         "open": "08:00-17:30", "ticket": 90, "rating": 4.7, "desc": "世界文化遗产", "tags": "世界遗产,自然,工程"},
    ],
    "杭州": [
        {"name": "西湖", "lat": 30.2402, "lng": 120.1445, "type": "attraction",
         "open": "全天开放", "ticket": 0, "rating": 4.9, "desc": "中国十大风景名胜之一", "tags": "自然风光,世界遗产,免费"},
        {"name": "灵隐寺", "lat": 30.2782, "lng": 120.1013, "type": "attraction",
         "open": "07:00-17:30", "ticket": 75, "rating": 4.7, "desc": "中国佛教禅宗十大古刹之一", "tags": "寺庙,佛教,历史"},
    ],
}


# ---------------------------------------------------------------------------
# Deep Link Builder
# ---------------------------------------------------------------------------

def build_platform_flight_deep_link(platform: str, flight: dict) -> dict:
    """
    Build the most specific possible booking link for a flight on each platform.

    All URLs point to real, publicly accessible pages. When the exact flight
    detail page URL is not known, we link to the search results page with
    as many flight-specific parameters as possible.

    Returns: {url, fallbackUrl, linkType, note}
      linkType: "deep-link" | "search-result" | "fallback-search"
    """
    fn = flight.get("flight_number", "")
    dep_code = flight.get("departure_code", "")
    arr_code = flight.get("arrival_code", "")
    dep_city = flight.get("departure_city", "")
    arr_city = flight.get("arrival_city", "")
    dep_date = flight.get("departure_date", date.today().isoformat())
    al_code = flight.get("airline_code", "")

    if platform == "airline_official":
        al_info = AIRLINES.get(al_code, (None, None))
        al_name = al_info[0] if al_info else al_code
        al_url = al_info[1] if al_info else "https://www.example.com"
        # Link to airline homepage — booking pages vary too much between airlines
        return {
            "url": al_url,
            "fallbackUrl": al_url,
            "linkType": "deep-link",
            "note": f"直达{al_name}官网",
        }

    if platform == "ctrip":
        # Real ctrip flight search page
        return {
            "url": f"https://flights.ctrip.com/itinerary/oneway/{dep_code.lower()}-{arr_code.lower()}?date={dep_date}",
            "fallbackUrl": "https://flights.ctrip.com",
            "linkType": "search-result",
            "note": "携程单程航班搜索页",
        }

    if platform == "feizhu":
        # Real fliggy flight search
        return {
            "url": f"https://www.fliggy.com/search?q={dep_city}+{arr_city}+机票+{dep_date}",
            "fallbackUrl": "https://www.fliggy.com",
            "linkType": "search-result",
            "note": "飞猪机票搜索页",
        }

    if platform == "qunar":
        # Real qunar flight page
        return {
            "url": f"https://flight.qunar.com/",
            "fallbackUrl": "https://flight.qunar.com",
            "linkType": "search-result",
            "note": "去哪儿机票首页（搜索参数需手动输入）",
        }

    if platform == "tongcheng":
        # Real ly.com flight page
        return {
            "url": f"https://www.ly.com/flights/home",
            "fallbackUrl": "https://www.ly.com",
            "linkType": "search-result",
            "note": "同程机票首页（搜索参数需手动输入）",
        }

    if platform == "zhixing":
        # 智行旅行实际可通过 zx12306.com 或应用访问
        return {
            "url": f"https://www.zx12306.com",
            "fallbackUrl": "https://www.zx12306.com",
            "linkType": "fallback-search",
            "note": "智行旅行首页（搜索参数需手动输入）",
        }

    return {
        "url": "#",
        "fallbackUrl": "#",
        "linkType": "fallback-search",
        "note": "暂不支持该平台",
    }


# ---------------------------------------------------------------------------
# Mock Data Generators
# ---------------------------------------------------------------------------

def _airline_info(code: str):
    """Return (name, url) for airline code."""
    return AIRLINES.get(code, (code, "https://www.example.com"))


def _gen_per_platform_price_history(flight_id: str, days: int = 30) -> List[dict]:
    """Generate per-platform price history for a specific flight."""
    random.seed(flight_id[:8])
    today = date.today()
    platform_factors = {
        "airline_official": 1.00,
        "ctrip": 0.97,
        "feizhu": 0.95,
        "qunar": 0.96,
        "tongcheng": 0.98,
        "zhixing": 0.94,
    }
    result = []
    for plat_key, plat_name in PLATFORMS:
        factor = platform_factors.get(plat_key, 0.97)
        prices = []
        for i in range(days):
            d = today - timedelta(days=days - 1 - i)
            days_ago = days - 1 - i
            trend_factor = 1.0 + 0.015 * max(0, days_ago - 21)
            noise = random.uniform(-0.04, 0.04)
            price = 0  # no fake prices
            prices.append({"date": d.isoformat(), "price": price})
        result.append({
            "platform": plat_key,
            "platform_name": plat_name,
            "prices": prices,
        })
    random.seed()
    return result


def _gen_flight_dict(flight_number: str, airline_code: str, departure_city: str, arrival_city: str,
                     flight_date: date, dep_hour: int, dep_min: int, dur: int, stops: int,
                     aircraft: str) -> dict:
    """Build a complete flight dict with all fields."""
    dep_airports = AIRPORTS.get(departure_city, [("XXX", "Unknown", "T1")])
    arr_airports = AIRPORTS.get(arrival_city, [("YYY", "Unknown", "T1")])
    dep_code, dep_ap_name, dep_term = random.choice(dep_airports)
    arr_code, arr_ap_name, arr_term = random.choice(arr_airports)
    al_name, _ = _airline_info(airline_code)

    dep_dt = datetime(flight_date.year, flight_date.month, flight_date.day, dep_hour, dep_min, 0)
    arr_dt = dep_dt + timedelta(minutes=dur)

    fid = str(uuid.uuid4())

    platform_quotes = _gen_platform_quotes_priceless(flight_number, departure_city, arrival_city,
                                                      dep_code, arr_code, flight_date.isoformat(),
                                                      dep_dt.isoformat(), arr_dt.isoformat(), airline_code)
    deep_links = []
    for pk, pn in PLATFORMS:
        link = build_platform_flight_deep_link(pk, {
            "flight_number": flight_number, "departure_code": dep_code, "arrival_code": arr_code,
            "departure_city": departure_city, "arrival_city": arrival_city,
            "departure_date": flight_date.isoformat(), "airline_code": airline_code,
            "departure_time": dep_dt.isoformat(), "arrival_time": arr_dt.isoformat(),
        })
        deep_links.append({"platform": pk, "platform_name": pn, **link})

    on_time = random.uniform(0.75, 0.98)

    return {
        "id": fid,
        "source": "mock",
        "flight_number": flight_number,
        "airline_code": airline_code,
        "airline_name": al_name,
        "airline_logo": f"/airlines/{airline_code.lower()}.png",
        "aircraft_type": aircraft,
        "departure_city": departure_city,
        "arrival_city": arrival_city,
        "departure_code": dep_code,
        "arrival_code": arr_code,
        "departure_airport": dep_ap_name,
        "arrival_airport": arr_ap_name,
        "departure_terminal": dep_term,
        "arrival_terminal": arr_term,
        "departure_time": dep_dt.isoformat(),
        "arrival_time": arr_dt.isoformat(),
        "departure_date": flight_date.isoformat(),
        "duration_minutes": dur,
        "cabin_class": "economy",
        "price": 0,
        "price_source": "unavailable",
        "currency": "CNY",
        "stops": stops,
        "on_time_rate": round(on_time, 2),
        "baggage_policies": [
            {"id": str(uuid.uuid4()), "type_name": "carry_on", "weight_kg": 7, "pieces": 1,
             "description": "随身携带，不超过20x40x55cm"},
            {"id": str(uuid.uuid4()), "type_name": "checked", "weight_kg": 23, "pieces": 1,
             "description": "免费托运行李"},
        ],
        "refund_change_policies": [
            {"id": str(uuid.uuid4()), "policy_type": "refund", "time_label": "起飞前24小时以上",
             "fee_amount": 0, "description": "请以实际购票时平台退改规则为准"},
            {"id": str(uuid.uuid4()), "policy_type": "refund", "time_label": "起飞前2-24小时",
             "fee_amount": 0, "description": "请以实际购票时平台退改规则为准"},
            {"id": str(uuid.uuid4()), "policy_type": "change", "time_label": "起飞前24小时以上",
             "fee_amount": 0, "description": "请以实际购票时平台改签规则为准"},
        ],
        "platform_quotes": platform_quotes,
        "platform_links": deep_links,
    }


def _gen_platform_quotes_priceless(flight_number: str, dep_city: str, arr_city: str,
                                     dep_code: str, arr_code: str, dep_date: str,
                                     dep_time: str, arr_time: str, airline_code: str) -> list:
    """Generate platform jump targets WITHOUT fake prices. Price = 0, source = unavailable."""
    quotes = []
    for plat_key, plat_name in PLATFORMS:
        flight_ref = {
            "flight_number": flight_number, "departure_code": dep_code, "arrival_code": arr_code,
            "departure_city": dep_city, "arrival_city": arr_city,
            "departure_date": dep_date, "airline_code": airline_code,
            "departure_time": dep_time, "arrival_time": arr_time,
        }
        link = build_platform_flight_deep_link(plat_key, flight_ref)
        quotes.append({
            "id": str(uuid.uuid4()),
            "platform": plat_key,
            "platform_name": plat_name,
            "price": 0,
            "currency": "CNY",
            "tax_included": False,
            "cabin_class": "economy",
            "remaining_seats": 0,
            "baggage_summary": "请以平台实际显示为准",
            "refund_change_summary": "请以平台实际显示为准",
            "booking_url": link["url"],
            "fallback_url": link["fallbackUrl"],
            "link_type": link["linkType"],
            "link_note": link["note"],
            "is_cheapest": False,
            "source": "unavailable",
            "updated_at": datetime.utcnow().isoformat(),
        })
    return quotes


def _gen_platform_quotes(flight_number: str) -> list:
    """Platform jump targets — no fake prices."""
    quotes = []
    for plat_key, plat_name in PLATFORMS:
        quotes.append({
            "id": str(uuid.uuid4()),
            "platform": plat_key,
            "platform_name": plat_name,
            "price": 0,
            "currency": "CNY",
            "tax_included": False,
            "cabin_class": "economy",
            "remaining_seats": 0,
            "baggage_summary": "请以平台实际显示为准",
            "refund_change_summary": "请以平台实际显示为准",
            "booking_url": PLATFORM_BASE_URLS.get(plat_key, "#"),
            "fallback_url": PLATFORM_BASE_URLS.get(plat_key, "#"),
            "link_type": "fallback-search",
            "link_note": "通用搜索页",
            "is_cheapest": False,
            "source": "unavailable",
            "updated_at": datetime.utcnow().isoformat(),
        })
    return quotes


# ---------------------------------------------------------------------------
# Mock Implementations
# ---------------------------------------------------------------------------

class MockFlightDataProvider(FlightDataProvider):
    """Mock flight data using generated realistic data."""

    async def search_flights(
        self,
        departure_city: str,
        arrival_city: str,
        flight_date: date,
        time_period: str = "all",
        passengers: int = 1,
    ) -> List[dict]:
        if departure_city not in AIRPORTS or arrival_city not in AIRPORTS:
            return []

        random.seed(f"{departure_city}{arrival_city}{flight_date.isoformat()}")
        flights = []

        for tmpl in MOCK_FLIGHT_TEMPLATES:
            dep_h = tmpl["dep_hour"]
            period = "morning" if dep_h < 10 else "afternoon" if dep_h < 16 else "evening"
            if time_period != "all" and period != time_period:
                continue

            f = _gen_flight_dict(
                tmpl["fn"], tmpl["al"], departure_city, arrival_city,
                flight_date, tmpl["dep_hour"], tmpl["dep_min"],
                tmpl["dur"], tmpl["stops"], tmpl["aircraft"],
            )
            flights.append(f)

        random.seed()
        return flights

    async def search_flight_by_number(
        self,
        flight_number: str,
        flight_date: date,
        origin: Optional[str] = None,
        destination: Optional[str] = None,
    ) -> Optional[dict]:
        """Find a specific flight by number. Returns realistic mock data."""
        if not flight_number or not flight_number.strip():
            return None

        # Normalize: if user enters something like MU5101, try to match
        fn = flight_number.strip().upper()

        # Extract airline code from flight number (first 2 chars usually)
        airline_code = fn[:2] if len(fn) >= 4 else "CA"
        # Check if this is a known airline
        if airline_code not in AIRLINES:
            airline_code = "CA"

        # Determine cities
        dep_city = origin or "北京"
        arr_city = destination or "上海"
        if dep_city not in AIRPORTS:
            dep_city = "北京"
        if arr_city not in AIRPORTS:
            arr_city = "上海"

        random.seed(f"{fn}{flight_date.isoformat()}")

        _bp = 0  # no fake prices
        dep_h = random.choice([7, 8, 9, 10, 14, 16, 19])
        dep_m = random.choice([0, 15, 30, 45])
        dur = random.choice([120, 135, 150, 165, 180])
        stops = 0 if random.random() > 0.2 else 1
        aircraft = random.choice(["Boeing 737-800", "Airbus A320neo", "Airbus A321", "Boeing 787-9"])

        f = _gen_flight_dict(
            fn, airline_code, dep_city, arr_city,
            flight_date, dep_h, dep_m, dur, stops, aircraft,
        )

        random.seed()
        return f

    async def get_flight_detail(self, flight_id: str) -> Optional[dict]:
        """Return enhanced detail for a given flight_id."""
        random.seed(flight_id[:8])
        tmpl = random.choice(MOCK_FLIGHT_TEMPLATES)
        dep_city = random.choice(list(AIRPORTS.keys()))
        arr_city = random.choice([c for c in AIRPORTS.keys() if c != dep_city])
        dep_date = date.today() + timedelta(days=random.randint(1, 14))

        f = _gen_flight_dict(
            tmpl["fn"], tmpl["al"], dep_city, arr_city,
            dep_date, tmpl["dep_hour"], tmpl["dep_min"],
            tmpl["dur"], tmpl["stops"], tmpl["aircraft"],
        )
        f["id"] = flight_id
        random.seed()
        return f

    async def get_price_history(self, flight_id: str, days: int = 30) -> List[dict]:
        """Return per-platform price history for this flight."""
        random.seed(flight_id[:8])
        result = _gen_per_platform_price_history(flight_id, days)
        random.seed()
        return result

    async def get_platform_quotes(self, flight_id: str) -> List[dict]:
        random.seed(flight_id[:8])
        result = _gen_platform_quotes("unknown")
        random.seed()
        return result

    async def get_platform_links(self, flight_id: str) -> List[dict]:
        """Generate platform deep-links for a given flight."""
        random.seed(flight_id[:8])
        tmpl = random.choice(MOCK_FLIGHT_TEMPLATES)
        fn = tmpl["fn"]
        al_code = tmpl["al"]
        dep_city = random.choice(list(AIRPORTS.keys()))
        arr_city = random.choice([c for c in AIRPORTS.keys() if c != dep_city])
        dep_code, _, _ = AIRPORTS[dep_city][0]
        arr_code, _, _ = AIRPORTS[arr_city][0]
        dep_date = (date.today() + timedelta(days=random.randint(1, 7))).isoformat()

        links = []
        for plat_key, plat_name in PLATFORMS:
            ref = {
                "flight_number": fn, "departure_code": dep_code, "arrival_code": arr_code,
                "departure_city": dep_city, "arrival_city": arr_city,
                "departure_date": dep_date, "airline_code": al_code,
                "departure_time": "", "arrival_time": "",
            }
            link = build_platform_flight_deep_link(plat_key, ref)
            links.append({
                "platform": plat_key,
                "platform_name": plat_name,
                **link,
            })
        random.seed()
        return links


class MockPlaceDataProvider(PlaceDataProvider):
    async def search_places(self, city: str, keyword: str = "") -> List[dict]:
        places = []
        city_attractions = ATTRACTIONS.get(city, [])
        for attr in city_attractions:
            if keyword and keyword not in attr["name"]:
                continue
            places.append({
                "id": str(uuid.uuid4()),
                "name": attr["name"],
                "city": city,
                "address": f"{city}市{attr['name']}",
                "place_type": attr["type"],
                "latitude": attr["lat"],
                "longitude": attr["lng"],
                "image_url": f"/images/{attr['name']}.jpg",
                "opening_time": attr["open"],
                "ticket_price": attr["ticket"],
                "ticket_link": f"https://www.example.com/tickets/{attr['name']}",
                "rating": attr["rating"],
                "description": attr["desc"],
                "tags": attr["tags"],
            })
        return places

    async def get_place_detail(self, place_id: str) -> Optional[dict]:
        return None


class MockRouteEstimationProvider(RouteEstimationProvider):
    """Mock route estimation with AMap deep link generation.

    For taxi: generates 5-8 mock price candidates, averages the lowest 5.
    AMap route URL carries origin/destination names and coordinates.
    """

    MODE_SPEEDS = {
        "walking": (5, 0),
        "biking": (15, 0),
        "bus": (25, 0.15),
        "subway": (35, 0.25),
        "taxi": (40, 2.5),
        "driving": (40, 1.5),
    }

    MODE_NAMES = {
        "walking": "步行", "biking": "骑行", "bus": "公交",
        "subway": "地铁", "taxi": "打车", "driving": "自驾",
    }

    AMAP_MODE_MAP = {
        "walking": "0", "biking": "4", "bus": "1",
        "subway": "1", "taxi": "2", "driving": "2",
    }

    def _haversine_km(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        R = 6371
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlng / 2) ** 2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def _build_amap_route_url(
        self, origin_name: str, origin_lat: float, origin_lng: float,
        dest_name: str, dest_lat: float, dest_lng: float,
        mode: str,
    ) -> str:
        """Build a deep link to AMap route planning between two points.

        Uses AMap's URI scheme for route planning:
        https://uri.amap.com/navigation?from=<lng>,<lat>,<name>&to=<lng>,<lat>,<name>&mode=<mode>
        """
        from urllib.parse import quote
        amap_mode = self.AMAP_MODE_MAP.get(mode, "2")
        from_enc = f"{origin_lng},{origin_lat},{quote(origin_name)}"
        to_enc = f"{dest_lng},{dest_lat},{quote(dest_name)}"
        return f"https://uri.amap.com/navigation?from={from_enc}&to={to_enc}&mode={amap_mode}"

    async def estimate_route(
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
        dist_km = self._haversine_km(origin_lat, origin_lng, destination_lat, destination_lng) * 1.3
        dist_m = int(dist_km * 1000)

        speed, base_cost_per_km = self.MODE_SPEEDS.get(transport_mode, (30, 1.0))
        time_min = max(3, int(dist_km / speed * 60))

        # Cost estimation with averaging logic for taxi
        if transport_mode == "taxi":
            candidates = [dist_km * base_cost_per_km * (0.9 + 0.04 * i) for i in range(8)]
            candidates.sort()
            top5 = candidates[:5]
            cost = round(sum(top5) / len(top5), 2)
            cost_explanation = f"根据最低5个候选方案估算平均值（共{len(candidates)}个候选）"
        else:
            cost = round(dist_km * base_cost_per_km, 2)
            cost_explanation = "按标准费率估算"

        # Build alternatives (all modes)
        alternatives = []
        for mode_key, (alt_speed, alt_cost_per_km) in self.MODE_SPEEDS.items():
            alt_time = max(3, int(dist_km / alt_speed * 60))
            if mode_key == "taxi":
                alt_candidates = [dist_km * alt_cost_per_km * (0.9 + 0.04 * i) for i in range(8)]
                alt_candidates.sort()
                alt_cost = round(sum(alt_candidates[:5]) / len(alt_candidates[:5]), 2)
            else:
                alt_cost = round(dist_km * alt_cost_per_km, 2)
            alternatives.append({
                "mode": mode_key,
                "duration_minutes": alt_time,
                "distance_meters": dist_m,
                "estimated_cost": alt_cost,
            })

        amap_url = self._build_amap_route_url(
            origin_name or f"起点({origin_lat:.4f},{origin_lng:.4f})",
            origin_lat, origin_lng,
            destination_name or f"终点({destination_lat:.4f},{destination_lng:.4f})",
            destination_lat, destination_lng,
            transport_mode,
        )

        return {
            "mode": transport_mode,
            "distance_meters": dist_m,
            "duration_minutes": time_min,
            "estimated_cost": cost,
            "cost_explanation": cost_explanation,
            "amap_route_url": amap_url,
            "alternatives": alternatives,
        }


class MockPredictionProvider(PredictionProvider):
    """No-fake-data prediction stub.

    ALL predictions require real price history from the compare system.
    Without real data, this returns a clear "no data" response.
    Production replacement: swap with LightGBMPredictionProvider or CatBoostPredictionProvider
    backed by real API-sourced price snapshots.
    """

    async def predict(
        self,
        flight_id: str,
        price_history: List[dict],
    ) -> dict:
        """Return 'no data' unless at least 3 real (non-zero) price records exist."""
        # Extract real (non-zero) prices from history
        real_prices = []
        if price_history:
            for item in price_history:
                if isinstance(item, dict) and "prices" in item:
                    for p in item.get("prices", []):
                        if p.get("price", 0) > 0:
                            real_prices.append(p["price"])
                elif isinstance(item, dict):
                    p = item.get("min_price", item.get("price", 0))
                    if p > 0:
                        real_prices.append(p)

        if len(real_prices) < 3:
            return {
                "flight_id": flight_id,
                "recommended_buy_date": date.today().isoformat(),
                "predicted_lowest_price": 0,
                "current_lowest_price": 0,
                "confidence": 0,
                "price_range_low": 0,
                "price_range_high": 0,
                "trend_direction": "stable",
                "reasoning": "暂无足够真实价格记录，继续导入平台价格后可生成趋势。预测需要至少3条真实价格记录。",
                "risk_level": "unknown",
            }

        # Use real prices only --- no random generation
        real_prices.sort()
        all_min = min(real_prices)
        all_avg = sum(real_prices) / len(real_prices)
        recent = real_prices[-7:] if len(real_prices) >= 7 else real_prices
        recent_avg = sum(recent) / len(recent)

        if recent_avg > all_avg * 1.03:
            trend = "rising"; risk = "high"
        elif recent_avg < all_avg * 0.97:
            trend = "falling"; risk = "low"
        else:
            trend = "stable"; risk = "medium"

        return {
            "flight_id": flight_id,
            "recommended_buy_date": date.today().isoformat(),
            "predicted_lowest_price": round(all_min, 2),
            "current_lowest_price": round(recent[-1], 2),
            "confidence": round(min(0.7, len(real_prices) / 30), 2),
            "price_range_low": round(all_min, 2),
            "price_range_high": round(max(real_prices), 2),
            "trend_direction": trend,
            "reasoning": f"基于 {len(real_prices)} 条真实价格记录生成。趋势仅供参考，实际票价以平台实时查询为准。",
            "risk_level": risk,
        }
