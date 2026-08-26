from datetime import date as date_type
from typing import Optional

from fastapi import APIRouter, Query, HTTPException

from app.services.flight_service import flight_service

router = APIRouter(prefix="/api/flights", tags=["flights"])


def _parse_date(date_str: str) -> date_type:
    """Parse date string, raise 422 on invalid input."""
    try:
        return date_type.fromisoformat(date_str)
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail=f"无效日期格式: {date_str}，请使用 YYYY-MM-DD")


@router.get("/search")
async def search_flights(
    departure_city: str = Query(..., description="出发城市"),
    arrival_city: str = Query(..., description="到达城市"),
    date: str = Query(..., description="出发日期 YYYY-MM-DD"),
    time_period: str = Query("all", description="时间段: morning, afternoon, evening, all"),
    passengers: int = Query(1, ge=1, le=9, description="乘客数"),
):
    """按路线和时间段搜索航班列表。所有航班标注 source=mock 表示演示数据。"""
    flight_date = _parse_date(date)
    valid_periods = {"all", "morning", "afternoon", "evening"}
    if time_period not in valid_periods:
        raise HTTPException(status_code=422, detail=f"无效时间段: {time_period}，可选: {valid_periods}")
    return await flight_service.search(
        departure_city=departure_city,
        arrival_city=arrival_city,
        flight_date=flight_date,
        time_period=time_period,
        passengers=passengers,
    )


@router.get("/by-number")
async def search_flight_by_number(
    flightNumber: str = Query(..., description="航班号，如 MU5101、CA1831"),
    date: str = Query(..., description="出发日期 YYYY-MM-DD"),
    origin: Optional[str] = Query("", description="出发城市（可选）"),
    destination: Optional[str] = Query("", description="到达城市（可选）"),
):
    """按具体航班号查询航班详情、平台报价和跳转链接。"""
    flight_date = _parse_date(date)
    return await flight_service.search_by_number(
        flight_number=flightNumber,
        flight_date=flight_date,
        origin=origin or None,
        destination=destination or None,
    )


@router.get("/{flight_id}")
async def get_flight_detail(flight_id: str):
    """获取航班详情。航班不存在时返回 404。"""
    detail = await flight_service.get_detail(flight_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Flight not found")
    return detail


@router.get("/{flight_id}/history")
async def get_flight_price_history(
    flight_id: str,
    days: int = Query(30, ge=7, le=90, description="历史天数"),
):
    """获取该航班过去N天各平台价格历史。"""
    return await flight_service.get_price_history(flight_id, days)


@router.get("/{flight_id}/prediction")
async def get_flight_prediction(flight_id: str):
    """获取航班价格预测。若无足够真实数据则返回明确提示，不生成虚假预测。"""
    return await flight_service.get_prediction(flight_id)


@router.get("/{flight_id}/platform-trends")
async def get_platform_trends(flight_id: str):
    """获取不同平台的价格趋势对比（仅基于真实记录）。"""
    return await flight_service.get_platform_trends(flight_id)


@router.get("/{flight_id}/platform-links")
async def get_platform_links(flight_id: str):
    """获取各平台该航班的具体跳转链接。"""
    return await flight_service.get_platform_links(flight_id)


@router.get("/{flight_id}/trend")
async def get_flight_trend(flight_id: str, days: int = Query(30, ge=7, le=90)):
    """获取价格趋势参考（基于真实记录，明确标注source）。"""
    return await flight_service.get_trend(flight_id, days)