"""Flight search and detail service.

Orchestrates between the provider layer and API routers.
"""

from datetime import date
from typing import List, Optional

from app.adapters.base import FlightDataProvider, PredictionProvider
from app.adapters.mock_provider import MockFlightDataProvider, MockPredictionProvider


class FlightService:
    """Handles flight search, detail, and pricing logic."""

    def __init__(
        self,
        flight_provider: Optional[FlightDataProvider] = None,
        prediction_provider: Optional[PredictionProvider] = None,
    ):
        self.flight_provider = flight_provider or MockFlightDataProvider()
        self.prediction_provider = prediction_provider or MockPredictionProvider()

    async def search(
        self,
        departure_city: str,
        arrival_city: str,
        flight_date: date,
        time_period: str = "all",
        passengers: int = 1,
    ) -> dict:
        flights = await self.flight_provider.search_flights(
            departure_city, arrival_city, flight_date, time_period, passengers
        )

        platform_prices = {}
        platform_cheapest_count = {}
        for f in flights:
            for q in f.get("platform_quotes", []):
                plat = q["platform_name"]
                if plat not in platform_prices:
                    platform_prices[plat] = []
                platform_prices[plat].append(q["price"])
                if q.get("is_cheapest"):
                    platform_cheapest_count[plat] = platform_cheapest_count.get(plat, 0) + 1

        price_ranking = []
        for plat, prices in platform_prices.items():
            price_ranking.append({
                "platform": plat,
                "avg_price": round(sum(prices) / len(prices), 2),
                "min_price": round(min(prices), 2),
                "cheapest_count": platform_cheapest_count.get(plat, 0),
            })
        price_ranking.sort(key=lambda x: x["avg_price"])

        return {"flights": flights, "total": len(flights), "price_ranking": price_ranking}

    async def search_by_number(
        self,
        flight_number: str,
        flight_date: date,
        origin: Optional[str] = None,
        destination: Optional[str] = None,
    ) -> dict:
        flight = await self.flight_provider.search_flight_by_number(
            flight_number, flight_date, origin, destination
        )
        if flight:
            return {"flight": flight, "error": None}
        return {"flight": None, "error": f"未找到航班 {flight_number}"}

    async def get_detail(self, flight_id: str) -> Optional[dict]:
        return await self.flight_provider.get_flight_detail(flight_id)

    async def get_price_history(self, flight_id: str, days: int = 30) -> dict:
        history = await self.flight_provider.get_price_history(flight_id, days)
        return {"flight_id": flight_id, "history": history}

    async def get_prediction(self, flight_id: str) -> dict:
        history = await self.flight_provider.get_price_history(flight_id, 30)
        return await self.prediction_provider.predict(flight_id, history)

    async def get_platform_trends(self, flight_id: str) -> dict:
        history = await self.flight_provider.get_price_history(flight_id, 14)
        quotes = await self.flight_provider.get_platform_quotes(flight_id)

        platform_names = ["航司官网", "携程", "飞猪", "去哪儿", "同程", "智行旅行"]
        platform_keys = ["airline_official", "ctrip", "feizhu", "qunar", "tongcheng", "zhixing"]

        trends = []
        if history and isinstance(history[0], dict) and "prices" in history[0]:
            # New per-platform format — use real data only
            dates = [p["date"][5:] for p in history[0].get("prices", [])]
            for plat_data in history:
                prices = [p["price"] for p in plat_data.get("prices", [])]
                trends.append({
                    "platform": plat_data["platform"],
                    "platform_name": plat_data["platform_name"],
                    "dates": dates,
                    "prices": prices,
                })
        else:
            # No real history — return empty trends, no fake generation
            trends = []

        # Compute judgment from real data only
        recent_avg = {}
        for t in trends:
            real_prices = [p for p in t["prices"] if p > 0]
            if real_prices:
                recent_avg[t["platform_name"]] = sum(real_prices[-7:]) / len(real_prices[-7:])

        if recent_avg:
            sp = sorted(recent_avg.items(), key=lambda x: x[1])
            top = sp[0]
            second = sp[1] if len(sp) > 1 else None
            judgment = f"{top[0]}最近7天价格最便宜，均价¥{top[1]:.0f}"
            if second and top[1] < second[1]:
                judgment += f"，比{second[0]}低¥{(second[1] - top[1]):.0f}"
            cheapest = top[0]
        else:
            judgment = "暂无足够真实价格数据，请通过比价系统导入平台价格"
            cheapest = None

        return {
            "flight_id": flight_id,
            "trends": trends,
            "cheapest_platform_recently": cheapest or "",
            "trend_judgment": judgment,
        }

    async def get_platform_links(self, flight_id: str) -> dict:
        links = await self.flight_provider.get_platform_links(flight_id)
        return {"flight_id": flight_id, "links": links}

    async def get_trend(self, flight_id: str, days: int = 30) -> dict:
        """Price trend — only based on real records. No fake data generated."""
        history = await self.flight_provider.get_price_history(flight_id, days)
        points = []
        if history and isinstance(history[0], dict) and "prices" in history[0]:
            # Extract real price points from per-platform history
            for plat_data in history:
                for p in plat_data.get("prices", []):
                    if p.get("price", 0) > 0:
                        points.append({"date": p["date"], "price": p["price"]})

        if len(points) < 3:
            return {
                "source": "real_records",
                "accuracy": "insufficient_data",
                "disclaimer": "暂无足够价格记录，继续导入平台价格后可生成趋势。",
                "currency": "CNY",
                "points": [],
                "current_reference_price": 0,
                "predicted_lowest_price": 0,
                "suggested_action": "collect",
                "suggestion_text": "请先通过比价系统导入平台价格记录",
            }

        points.sort(key=lambda x: x["date"])
        current = points[-1]["price"] if points else 0

        return {
            "source": "real_records",
            "accuracy": "based_on_user_records",
            "disclaimer": "趋势基于你的记录生成，实际票价以平台实时价格为准。",
            "currency": "CNY",
            "points": points,
            "current_reference_price": current,
            "predicted_lowest_price": 0,
            "suggested_action": "compare",
            "suggestion_text": "建议多平台实时查询确认最新价格",
        }


flight_service = FlightService()
