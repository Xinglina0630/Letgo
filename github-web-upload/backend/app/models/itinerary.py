import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Text, DateTime, ForeignKey, Integer, Boolean
from sqlalchemy.orm import relationship

from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class Place(Base):
    __tablename__ = "places"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    name = Column(String(200), nullable=False)
    city = Column(String(100), nullable=False, index=True)
    address = Column(String(500), default="")
    place_type = Column(String(50), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    image_url = Column(String(500), default="")
    opening_time = Column(String(100), default="")
    ticket_price = Column(Float, default=0.0)
    ticket_link = Column(String(500), default="")
    rating = Column(Float, default=4.0)
    description = Column(Text, default="")
    tags = Column(String(500), default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class Itinerary(Base):
    __tablename__ = "itineraries"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    project_id = Column(String(36), ForeignKey("travel_projects.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String(200), nullable=False)
    city = Column(String(100), nullable=False, index=True)
    description = Column(Text, default="")
    version = Column(Integer, default=1)  # optimistic lock for collaboration
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Never rely on MySQL's natural row order.  Nodes are deleted/recreated on
    # every document save, so an unordered relationship can appear shuffled
    # after a reload even though order_in_day was persisted correctly.
    nodes = relationship(
        "ItineraryNode",
        back_populates="itinerary",
        cascade="all, delete-orphan",
        order_by=lambda: (ItineraryNode.day_number, ItineraryNode.order_in_day, ItineraryNode.id),
    )
    edges = relationship("ItineraryEdge", back_populates="itinerary", cascade="all, delete-orphan")


class ItineraryNode(Base):
    __tablename__ = "itinerary_nodes"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    itinerary_id = Column(String(36), ForeignKey("itineraries.id", ondelete="CASCADE"), nullable=False, index=True)
    place_id = Column(String(36), ForeignKey("places.id", ondelete="SET NULL"), nullable=True)
    custom_name = Column(String(200), default="")
    custom_address = Column(String(500), default="")
    city_name = Column(String(100), default="", nullable=False)
    node_type = Column(String(50), nullable=False)
    notes = Column(Text, default="")
    # Location snapshot
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    coordinate_system = Column(String(20), default="GCJ02")
    amap_poi_id = Column(String(100), default="")
    location_source = Column(String(30), default="")  # amap_poi | amap_geocode | manual | custom
    location_verified = Column(Boolean, default=False)
    source_tag_id = Column(String(100), default="")  # hot place id like "sh2"
    # Place metadata
    tags = Column(String(300), default="")
    opening_time = Column(String(100), default="")
    ticket_price = Column(Float, nullable=True)
    ticket_link = Column(String(500), default="")
    # Canvas position (unrelated to geo coords)
    x_position = Column(Float, default=0.0)
    y_position = Column(Float, default=0.0)
    day_number = Column(Integer, default=1)
    order_in_day = Column(Integer, default=0)

    itinerary = relationship("Itinerary", back_populates="nodes")
    place = relationship("Place")


class ItineraryEdge(Base):
    __tablename__ = "itinerary_edges"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    itinerary_id = Column(String(36), ForeignKey("itineraries.id", ondelete="CASCADE"), nullable=False, index=True)
    source_node_id = Column(String(36), ForeignKey("itinerary_nodes.id", ondelete="CASCADE"), nullable=False)
    target_node_id = Column(String(36), ForeignKey("itinerary_nodes.id", ondelete="CASCADE"), nullable=False)
    transport_type = Column(String(50), nullable=False)
    estimated_time_minutes = Column(Integer, default=0)
    estimated_distance_km = Column(Float, default=0.0)
    estimated_cost = Column(Float, default=0.0)
    notes = Column(Text, default="")

    itinerary = relationship("Itinerary", back_populates="edges")
