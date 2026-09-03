"""Itinerary CRUD service with transaction support and edge validation."""

from typing import Optional, List

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.itinerary import Itinerary, ItineraryNode, ItineraryEdge
from app.models.collaboration import TravelProjectMember
from app.schemas.itinerary import ItineraryCreateRequest


def _create_nodes_and_edges(
    db: Session, itinerary_id: str, data: ItineraryCreateRequest
) -> None:
    """Create nodes first, then validate and create edges referencing only those nodes."""
    # Create nodes and collect temp_id → real_id mapping
    node_id_map: dict[str, str] = {}
    for node_data in data.nodes:
        node = ItineraryNode(
            itinerary_id=itinerary_id,
            place_id=node_data.place_id,
            custom_name=node_data.custom_name,
            custom_address=node_data.custom_address,
            city_name=getattr(node_data, 'city_name', None) or "",
            node_type=node_data.node_type,
            notes=node_data.notes,
            latitude=node_data.latitude,
            longitude=node_data.longitude,
            coordinate_system=node_data.coordinate_system or "GCJ02",
            amap_poi_id=getattr(node_data, 'amap_poi_id', None) or "",
            location_source=getattr(node_data, 'location_source', None) or "",
            location_verified=getattr(node_data, 'location_verified', None) or False,
            source_tag_id=getattr(node_data, 'source_tag_id', None) or "",
            tags=getattr(node_data, 'tags', None) or "",
            opening_time=getattr(node_data, 'opening_time', None) or "",
            ticket_price=getattr(node_data, 'ticket_price', None),
            ticket_link=getattr(node_data, 'ticket_link', None) or "",
            x_position=node_data.x_position,
            y_position=node_data.y_position,
            day_number=node_data.day_number,
            order_in_day=node_data.order_in_day,
        )
        db.add(node)
        db.flush()
        tid = getattr(node_data, 'temp_id', None) or None
        if tid:
            node_id_map[tid] = node.id

    # Validate and create edges
    for i, edge_data in enumerate(data.edges or []):
        src_raw = edge_data.source_node_id
        tgt_raw = edge_data.target_node_id

        # Resolve temp_ids to real DB ids
        src_id = node_id_map.get(src_raw)
        tgt_id = node_id_map.get(tgt_raw)

        # If source/target is not a temp_id from nodes in this request, reject
        if not src_id:
            raise HTTPException(
                status_code=422,
                detail=f"edge[{i}]: source_node_id '{src_raw}' does not reference a node in this request",
            )
        if not tgt_id:
            raise HTTPException(
                status_code=422,
                detail=f"edge[{i}]: target_node_id '{tgt_raw}' does not reference a node in this request",
            )
        if src_id == tgt_id:
            raise HTTPException(
                status_code=422,
                detail=f"edge[{i}]: source and target cannot be the same node",
            )

        edge = ItineraryEdge(
            itinerary_id=itinerary_id,
            source_node_id=src_id,
            target_node_id=tgt_id,
            transport_type=edge_data.transport_type,
            estimated_time_minutes=getattr(edge_data, 'estimated_time_minutes', None) or 0,
            estimated_distance_km=getattr(edge_data, 'estimated_distance_km', None) or 0.0,
            estimated_cost=getattr(edge_data, 'estimated_cost', None) or 0.0,
            notes=edge_data.notes,
        )
        db.add(edge)


class ItineraryService:
    def _ensure_unique_name(
        self, db: Session, user_id: str, name: str, exclude_itinerary_id: Optional[str] = None
    ) -> None:
        normalized_name = (name or "").strip()
        query = db.query(Itinerary.id).filter(
            Itinerary.user_id == user_id,
            func.lower(func.trim(Itinerary.name)) == normalized_name.lower(),
        )
        if exclude_itinerary_id:
            query = query.filter(Itinerary.id != exclude_itinerary_id)
        if query.first():
            raise HTTPException(status_code=409, detail=f"攻略名称「{normalized_name}」已经存在，请换一个名字")

    async def create(self, db: Session, data: ItineraryCreateRequest, user_id: str) -> Itinerary:
        """Create a new itinerary with nodes and edges in a transaction."""
        self._ensure_unique_name(db, user_id, data.name)
        project_id = getattr(data, 'project_id', None)
        itinerary = Itinerary(
            user_id=user_id,
            name=data.name,
            city=data.city,
            description=data.description or "",
            project_id=project_id,
        )
        db.add(itinerary)
        db.flush()
        _create_nodes_and_edges(db, itinerary.id, data)
        db.commit()
        db.refresh(itinerary)
        return itinerary

    async def get(self, db: Session, itinerary_id: str, user_id: Optional[str] = None) -> Optional[Itinerary]:
        """Get itinerary by ID, optionally filtered by user."""
        q = db.query(Itinerary).filter(Itinerary.id == itinerary_id)
        if user_id:
            q = q.filter(Itinerary.user_id == user_id)
        return q.first()

    async def list_by_user(self, db: Session, user_id: str) -> List[Itinerary]:
        """List owned itineraries plus itineraries shared with this user."""
        shared_project_ids = db.query(TravelProjectMember.project_id).filter(
            TravelProjectMember.user_id == user_id,
            TravelProjectMember.status == "active",
        )
        return (
            db.query(Itinerary)
            .filter((Itinerary.user_id == user_id) | (Itinerary.project_id.in_(shared_project_ids)))
            .order_by(Itinerary.updated_at.desc())
            .all()
        )

    async def list_by_project(self, db: Session, project_id: str) -> List[Itinerary]:
        """List all itineraries for a project."""
        return (
            db.query(Itinerary)
            .filter(Itinerary.project_id == project_id)
            .order_by(Itinerary.updated_at.desc())
            .all()
        )

    async def update(
        self, db: Session, itinerary_id: str, data: ItineraryCreateRequest, user_id: str
    ) -> Optional[Itinerary]:
        """Update an existing itinerary with full replacement of nodes/edges."""
        # The router has already checked owner/project-editor permission.  Do not
        # filter by the original creator here, otherwise invited editors can open
        # a shared itinerary but every save is incorrectly reported as 404.
        itinerary = await self.get(db, itinerary_id)
        if not itinerary:
            return None

        # Shared editors save on behalf of the original owner; uniqueness is
        # therefore checked in the owner's guide collection.
        self._ensure_unique_name(db, itinerary.user_id or user_id, data.name, itinerary_id)

        # Perform the optimistic-lock check and version increment in one SQL
        # statement.  A separate SELECT followed by UPDATE lets two workers
        # both pass the version check and the later writer silently win.
        client_version = data.version
        update_query = db.query(Itinerary).filter(Itinerary.id == itinerary_id)
        if client_version is not None:
            update_query = update_query.filter(Itinerary.version == client_version)
        updated_rows = update_query.update(
            {
                Itinerary.name: data.name,
                Itinerary.city: data.city,
                Itinerary.description: data.description,
                Itinerary.version: Itinerary.version + 1,
            },
            synchronize_session=False,
        )
        if updated_rows != 1:
            db.rollback()
            current = db.query(Itinerary.version).filter(Itinerary.id == itinerary_id).scalar()
            raise HTTPException(
                status_code=409,
                detail=f"版本冲突：你的版本是 {client_version}，服务器版本是 {current}。请刷新后重试。",
            )

        # Delete old nodes and edges
        db.query(ItineraryEdge).filter(ItineraryEdge.itinerary_id == itinerary_id).delete()
        db.query(ItineraryNode).filter(ItineraryNode.itinerary_id == itinerary_id).delete()
        db.flush()

        # Create new nodes and edges with validation
        _create_nodes_and_edges(db, itinerary.id, data)

        db.commit()
        db.refresh(itinerary)
        return itinerary

    async def delete(self, db: Session, itinerary_id: str, user_id: str) -> bool:
        """Delete an owner itinerary while retaining its collaboration audit project."""
        itinerary = await self.get(db, itinerary_id, user_id)
        if not itinerary:
            return False
        db.delete(itinerary)
        db.commit()
        return True


itinerary_service = ItineraryService()
