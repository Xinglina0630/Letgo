from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class PlaceOut(BaseModel):
    id: str
    name: str
    city: str
    address: str
    place_type: str
    latitude: float
    longitude: float
    image_url: str
    opening_time: str
    ticket_price: float
    ticket_link: str
    rating: float
    description: str
    tags: str

    class Config:
        from_attributes = True


class PlaceSearchResponse(BaseModel):
    places: List[PlaceOut]
    city: str


class ItineraryNodeCreate(BaseModel):
    temp_id: Optional[str] = Field(None, max_length=64)
    place_id: Optional[str] = Field(None, max_length=64)
    custom_name: str = Field("", max_length=200)
    custom_address: str = Field("", max_length=500)
    city_name: str = Field("", max_length=100)
    node_type: str = Field("attraction", max_length=30)
    notes: str = Field("", max_length=4000)
    # Location snapshot
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    coordinate_system: str = Field("GCJ02", max_length=20)
    amap_poi_id: str = Field("", max_length=100)
    location_source: str = Field("", max_length=50)
    location_verified: bool = False
    source_tag_id: str = Field("", max_length=64)
    # Place metadata
    tags: str = Field("", max_length=500)
    opening_time: str = Field("", max_length=200)
    ticket_price: Optional[float] = Field(None, ge=0, le=1000000)
    ticket_link: str = Field("", max_length=1000)
    # Canvas position
    x_position: float = 0.0
    y_position: float = 0.0
    day_number: int = Field(1, ge=1, le=365)
    order_in_day: int = Field(0, ge=0, le=9999)


class ItineraryEdgeCreate(BaseModel):
    source_node_id: str = Field(..., min_length=1, max_length=64)
    target_node_id: str = Field(..., min_length=1, max_length=64)
    transport_type: str = Field("walking", max_length=30)
    estimated_time_minutes: int = Field(0, ge=0, le=525600)
    estimated_distance_km: float = Field(0.0, ge=0, le=50000)
    estimated_cost: float = Field(0.0, ge=0, le=1000000)
    notes: str = Field("", max_length=8000)


class ItineraryCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    city: str = Field(..., min_length=1, max_length=100)
    description: str = Field("", max_length=2000)
    project_id: Optional[str] = None
    version: Optional[int] = None
    nodes: List[ItineraryNodeCreate] = Field(default_factory=list, max_length=1000)
    edges: List[ItineraryEdgeCreate] = Field(default_factory=list, max_length=1500)

class ItineraryNodeOut(BaseModel):
    id: str
    place_id: Optional[str] = None
    custom_name: str
    custom_address: str
    city_name: str = ""
    node_type: str
    notes: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    coordinate_system: str = "GCJ02"
    amap_poi_id: str = ""
    location_source: str = ""
    location_verified: bool = False
    source_tag_id: str = ""
    tags: str = ""
    opening_time: str = ""
    ticket_price: Optional[float] = None
    ticket_link: str = ""
    x_position: float
    y_position: float
    day_number: int
    order_in_day: int
    place: Optional[PlaceOut] = None

    class Config:
        from_attributes = True


class ItineraryEdgeOut(BaseModel):
    id: str
    source_node_id: str
    target_node_id: str
    transport_type: str
    estimated_time_minutes: int
    estimated_distance_km: float
    estimated_cost: float
    notes: str

    class Config:
        from_attributes = True


class ItineraryOut(BaseModel):
    id: str
    user_id: Optional[str] = None
    project_id: Optional[str] = None
    version: int = 1
    name: str
    city: str
    description: str
    created_at: datetime
    updated_at: datetime
    nodes: List[ItineraryNodeOut] = None
    edges: List[ItineraryEdgeOut] = None

    class Config:
        from_attributes = True

    def model_post_init(self, __context) -> None:
        if self.nodes is None:
            self.nodes = []
        if self.edges is None:
            self.edges = []


class RouteEstimateRequest(BaseModel):
    origin_name: str = ""
    origin_address: str = ""
    origin_lat: float
    origin_lng: float
    destination_name: str = ""
    destination_address: str = ""
    destination_lat: float
    destination_lng: float
    transport_mode: str = "taxi"


class RouteAlternative(BaseModel):
    mode: str
    duration_minutes: int
    distance_meters: int
    estimated_cost: float


class RouteEstimateOut(BaseModel):
    mode: str
    distance_meters: int
    duration_minutes: int
    estimated_cost: float
    cost_explanation: str = ""
    amap_route_url: str = ""
    alternatives: List[RouteAlternative] = []
