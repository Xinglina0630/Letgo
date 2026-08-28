from fastapi import APIRouter

from app.schemas.itinerary import RouteEstimateRequest, RouteEstimateOut
from app.services.route_service import route_service

router = APIRouter(prefix="/api/routes", tags=["routes"])


@router.post("/estimate", response_model=RouteEstimateOut)
async def estimate_route(data: RouteEstimateRequest):
    """估算两点之间的交通方式耗时、距离、费用，返回高德路线链接。"""
    result = await route_service.estimate(
        origin_name=data.origin_name,
        origin_address=data.origin_address,
        origin_lat=data.origin_lat,
        origin_lng=data.origin_lng,
        destination_name=data.destination_name,
        destination_address=data.destination_address,
        destination_lat=data.destination_lat,
        destination_lng=data.destination_lng,
        transport_mode=data.transport_mode,
    )
    return result
