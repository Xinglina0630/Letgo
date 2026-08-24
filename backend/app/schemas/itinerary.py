from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


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
    temp_id: Optional[str] = None
    place_id: Optional[str] = None
    custom_name: str = ""
    custom_address: str = ""
    node_type: str = "attraction"
    notes: str = ""
    # Location snapshot
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    coordinate_system: str = "GCJ02"
    amap_poi_id: str = ""
    location_source: str = ""
    location_verified: bool = False
    source_tag_id: str = ""
    # Place metadata
    tags: str = ""
    opening_time: str = ""
    ticket_price: Optional[float] = None
    ticket_link: str = ""
    # Canvas position
    x_position: float = 0.0
    y_position: float = 0.0
    day_number: int = 1
    order_in_day: int = 0


class ItineraryEdgeCreate(BaseModel):
    source_node_id: str
    target_node_id: str
    transport_type: str = "walking"
    estimated_time_minutes: int = 0
    estimated_distance_km: float = 0.0
    estimated_cost: float = 0.0
    notes: str = ""


class ItineraryCreateRequest(BaseModel):
    name: str
    city: str
    description: str = ""
    project_id: Optional[str] = None
    version: Optional[int] = None
    nodes: List[ItineraryNodeCreate] = None
    edges: List[ItineraryEdgeCreate] = None

    def model_post_init(self, __context) -> None:
        if self.nodes is None:
            self.nodes = []
        if self.edges is None:
            self.edges = []


class ItineraryNodeOut(BaseModel):
    id: str
    place_id: Optional[str] = None
    custom_name: str
    custom_address: str
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
