"""
Custom place tags API — user-created POI tags with optional project sharing.
"""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime

from app.database import get_db
from app.models.custom_tags import CustomPlaceTag, TravelProjectCustomTag
from app.models.collaboration import TravelProjectMember, TravelProjectEvent
from app.models.user import User
from app.routers.auth import get_current_user
from app.services.permissions import _get_membership

router = APIRouter(prefix="/api/custom-place-tags", tags=["custom-tags"])


def _broadcast(project_id: str, event_type: str, user: User, entity_id: str, summary: str) -> None:
    async def _send():
        try:
            from app.routers.ws_collaboration import broadcast_project_event
            await broadcast_project_event(project_id, {
                "event_type": event_type,
                "actor": {"user_id": user.id, "display_name": user.display_name or user.username},
                "entity_id": entity_id,
                "entity_type": "custom_place_tag",
                "summary": summary,
            })
        except Exception:
            pass

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_send())
    except RuntimeError:
        pass

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CustomTagCreate(BaseModel):
    city: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=255)
    place_type: str = Field(default="other")
    address: str = Field(default="")
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    coordinate_system: str = Field(default="GCJ02")
    amap_poi_id: str = Field(default="")
    location_verified: bool = False
    opening_time: str = Field(default="")
    ticket_price: Optional[float] = None
    official_url: str = Field(default="")
    project_id: Optional[str] = None


class CustomTagOut(BaseModel):
    id: str
    owner_user_id: str
    city: str
    name: str
    place_type: str
    address: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    coordinate_system: str
    amap_poi_id: str
    location_verified: bool
    opening_time: str
    ticket_price: Optional[float] = None
    official_url: str
    status: str
    is_mine: bool = False
    is_shared: bool = False
    owner_display_name: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# GET — list tags for a city, optionally scoped to a project
# ---------------------------------------------------------------------------

@router.get("/cities", response_model=List[str])
async def list_custom_tag_cities(
    project_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return cities represented by the user's and project's custom tags."""
    cities = set()
    if project_id:
        membership = _get_membership(db, project_id, current_user.id)
        if membership.status == "active":
            rows = (
                db.query(CustomPlaceTag.city)
                .join(TravelProjectCustomTag, TravelProjectCustomTag.custom_tag_id == CustomPlaceTag.id)
                .filter(
                    TravelProjectCustomTag.project_id == project_id,
                    CustomPlaceTag.status == "active",
                )
                .distinct().all()
            )
            cities.update(row[0] for row in rows)
    else:
        cities.update(
            row[0] for row in db.query(CustomPlaceTag.city).filter(
                CustomPlaceTag.owner_user_id == current_user.id,
                CustomPlaceTag.status == "active",
            ).distinct().all()
        )
    return sorted(c for c in cities if c)

@router.get("", response_model=List[CustomTagOut])
async def list_custom_tags(
    city: str = Query(..., min_length=1, description="City name"),
    project_id: Optional[str] = Query(None, description="Optional project ID for shared tags"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return user's own tags for city + project-shared tags if project_id given."""

    # Own tags for this city
    own_tags = (
        db.query(CustomPlaceTag)
        .filter(
            CustomPlaceTag.owner_user_id == current_user.id,
            CustomPlaceTag.city == city,
            CustomPlaceTag.status == "active",
        )
        .all()
    )

    # Project-shared tags
    shared_tag_ids = set()
    shared_tags = []
    if project_id:
        # Verify membership first (soft fail — non-members just don't see shared)
        membership = _get_membership(db, project_id, current_user.id)
        if membership and membership.status == "active":
            links = (
                db.query(TravelProjectCustomTag)
                .filter(TravelProjectCustomTag.project_id == project_id)
                .all()
            )
            linked_ids = {l.custom_tag_id for l in links}
            shared = (
                db.query(CustomPlaceTag)
                .filter(
                    CustomPlaceTag.id.in_(linked_ids),
                    CustomPlaceTag.city == city,
                    CustomPlaceTag.status == "active",
                )
                .all()
            )
            for tag in shared:
                if tag.owner_user_id != current_user.id:
                    shared_tag_ids.add(tag.id)
                    shared_tags.append(tag)

    # Merge and dedup
    seen = set()
    result = []
    for tag in own_tags + shared_tags:
        if tag.id in seen:
            continue
        seen.add(tag.id)

        owner_name = None
        if tag.owner and tag.owner.display_name:
            owner_name = tag.owner.display_name

        result.append(
            CustomTagOut(
                id=tag.id,
                owner_user_id=tag.owner_user_id,
                city=tag.city,
                name=tag.name,
                place_type=tag.place_type,
                address=tag.address,
                latitude=tag.latitude,
                longitude=tag.longitude,
                coordinate_system=tag.coordinate_system,
                amap_poi_id=tag.amap_poi_id,
                location_verified=tag.location_verified,
                opening_time=tag.opening_time,
                ticket_price=tag.ticket_price,
                official_url=tag.official_url,
                status=tag.status,
                is_mine=tag.owner_user_id == current_user.id,
                is_shared=tag.id in shared_tag_ids,
                owner_display_name=owner_name,
                created_at=tag.created_at.isoformat() if tag.created_at else None,
                updated_at=tag.updated_at.isoformat() if tag.updated_at else None,
            )
        )
    return result


# ---------------------------------------------------------------------------
# POST — create a custom tag (optionally shared to a project)
# ---------------------------------------------------------------------------

@router.post("", response_model=CustomTagOut, status_code=201)
async def create_custom_tag(
    body: CustomTagCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a custom place tag. If project_id is given, verify membership and auto-share."""

    # Check project permission if project_id set
    if body.project_id:
        membership = _get_membership(db, body.project_id, current_user.id)
        if not membership or membership.status != "active":
            raise HTTPException(403, "你没有该项目的访问权限")
        if membership.role == "viewer":
            raise HTTPException(403, "查看者不能创建或共享标签")

    tag = CustomPlaceTag(
        owner_user_id=current_user.id,
        city=body.city,
        name=body.name,
        place_type=body.place_type,
        address=body.address,
        latitude=body.latitude,
        longitude=body.longitude,
        coordinate_system=body.coordinate_system,
        amap_poi_id=body.amap_poi_id,
        location_verified=body.location_verified,
        opening_time=body.opening_time,
        ticket_price=body.ticket_price,
        official_url=body.official_url,
        status="active",
    )
    try:
        db.add(tag)
        db.flush()

        # Auto-share to project
        if body.project_id:
            link = TravelProjectCustomTag(
                project_id=body.project_id,
                custom_tag_id=tag.id,
                shared_by_user_id=current_user.id,
            )
            db.add(link)
            db.add(TravelProjectEvent(
                project_id=body.project_id,
                actor_id=current_user.id,
                event_type="custom_tag_created",
                entity_type="custom_place_tag",
                entity_id=tag.id,
                summary=f"新增了 {body.city} 的标签「{body.name}」",
            ))

        db.commit()
        db.refresh(tag)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(500, "保存标签失败，数据库结构需要更新，请重新部署最新版本") from exc

    if body.project_id:
        _broadcast(body.project_id, "custom_tag_created", current_user, tag.id,
                   f"新增了 {body.city} 的标签「{body.name}」")

    return CustomTagOut(
        id=tag.id,
        owner_user_id=tag.owner_user_id,
        city=tag.city,
        name=tag.name,
        place_type=tag.place_type,
        address=tag.address,
        latitude=tag.latitude,
        longitude=tag.longitude,
        coordinate_system=tag.coordinate_system,
        amap_poi_id=tag.amap_poi_id,
        location_verified=tag.location_verified,
        opening_time=tag.opening_time,
        ticket_price=tag.ticket_price,
        official_url=tag.official_url,
        status=tag.status,
        is_mine=True,
        is_shared=bool(body.project_id),
        owner_display_name=current_user.display_name,
        created_at=tag.created_at.isoformat() if tag.created_at else None,
        updated_at=tag.updated_at.isoformat() if tag.updated_at else None,
    )


# ---------------------------------------------------------------------------
# PUT — update a custom tag (owner only)
# ---------------------------------------------------------------------------

@router.put("/{tag_id}", response_model=CustomTagOut)
async def update_custom_tag(
    tag_id: str,
    body: CustomTagCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an owned custom tag and notify every project sharing it."""
    tag = db.query(CustomPlaceTag).filter(CustomPlaceTag.id == tag_id).first()
    if not tag:
        raise HTTPException(404, "标签不存在")
    if tag.owner_user_id != current_user.id:
        raise HTTPException(403, "只能修改自己创建的标签")

    linked_project_ids = [link.project_id for link in tag.project_links]
    if body.project_id and body.project_id not in linked_project_ids:
        membership = _get_membership(db, body.project_id, current_user.id)
        if not membership or membership.status != "active" or membership.role == "viewer":
            raise HTTPException(403, "你没有该项目的编辑权限")

    tag.city = body.city
    tag.name = body.name
    tag.place_type = body.place_type
    tag.address = body.address
    tag.latitude = body.latitude
    tag.longitude = body.longitude
    tag.coordinate_system = body.coordinate_system
    tag.amap_poi_id = body.amap_poi_id
    tag.location_verified = body.location_verified
    tag.opening_time = body.opening_time
    tag.ticket_price = body.ticket_price
    tag.official_url = body.official_url

    for project_id in linked_project_ids:
        db.add(TravelProjectEvent(
            project_id=project_id,
            actor_id=current_user.id,
            event_type="custom_tag_updated",
            entity_type="custom_place_tag",
            entity_id=tag.id,
            summary=f"修改了 {tag.city} 的标签「{tag.name}」",
        ))
    try:
        db.commit()
        db.refresh(tag)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(500, "修改标签失败，请稍后重试") from exc

    for project_id in linked_project_ids:
        _broadcast(project_id, "custom_tag_updated", current_user, tag.id,
                   f"修改了 {tag.city} 的标签「{tag.name}」")

    return CustomTagOut(
        id=tag.id, owner_user_id=tag.owner_user_id, city=tag.city,
        name=tag.name, place_type=tag.place_type, address=tag.address,
        latitude=tag.latitude, longitude=tag.longitude,
        coordinate_system=tag.coordinate_system, amap_poi_id=tag.amap_poi_id,
        location_verified=tag.location_verified, opening_time=tag.opening_time,
        ticket_price=tag.ticket_price, official_url=tag.official_url,
        status=tag.status, is_mine=True, is_shared=bool(linked_project_ids),
        owner_display_name=current_user.display_name,
        created_at=tag.created_at.isoformat() if tag.created_at else None,
        updated_at=tag.updated_at.isoformat() if tag.updated_at else None,
    )


# ---------------------------------------------------------------------------
# DELETE — permanently remove a tag and its sharing links (owner only)
# ---------------------------------------------------------------------------

@router.delete("/{tag_id}")
async def delete_custom_tag(
    tag_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Permanently delete a custom tag. Existing itinerary nodes are independent snapshots."""

    tag = db.query(CustomPlaceTag).filter(CustomPlaceTag.id == tag_id).first()
    if not tag:
        raise HTTPException(404, "标签不存在")
    if tag.owner_user_id != current_user.id:
        raise HTTPException(403, "只能删除自己创建的标签")

    linked_project_ids = [link.project_id for link in tag.project_links]
    deleted_tag_id, deleted_city, deleted_name = tag.id, tag.city, tag.name
    for project_id in linked_project_ids:
        db.add(TravelProjectEvent(
            project_id=project_id,
            actor_id=current_user.id,
            event_type="custom_tag_deleted",
            entity_type="custom_place_tag",
            entity_id=tag.id,
            summary=f"删除了 {tag.city} 的标签「{tag.name}」",
        ))
    # Links are removed explicitly so this also works on older MySQL schemas
    # that were created before ON DELETE CASCADE was added.
    db.query(TravelProjectCustomTag).filter(
        TravelProjectCustomTag.custom_tag_id == tag.id
    ).delete(synchronize_session=False)
    db.delete(tag)
    db.commit()
    for project_id in linked_project_ids:
        _broadcast(project_id, "custom_tag_deleted", current_user, deleted_tag_id,
                   f"删除了 {deleted_city} 的标签「{deleted_name}」")
    return {"ok": True}


# ---------------------------------------------------------------------------
# POST /api/projects/{project_id}/custom-place-tags/{tag_id}/share
# ---------------------------------------------------------------------------

project_share_router = APIRouter(prefix="/api/projects", tags=["custom-tags-project"])


@project_share_router.post("/{project_id}/custom-place-tags/{tag_id}/share")
async def share_tag_to_project(
    project_id: str,
    tag_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Share an existing personal tag to a project. Idempotent."""

    # Verify tag ownership
    tag = db.query(CustomPlaceTag).filter(CustomPlaceTag.id == tag_id).first()
    if not tag:
        raise HTTPException(404, "标签不存在")
    if tag.owner_user_id != current_user.id:
        raise HTTPException(403, "只能分享自己创建的标签")

    # Verify project edit permission
    membership = _get_membership(db, project_id, current_user.id)
    if not membership or membership.status != "active":
        raise HTTPException(403, "你没有该项目的访问权限")
    if membership.role == "viewer":
        raise HTTPException(403, "查看者不能分享标签")

    # Idempotent upsert
    existing = (
        db.query(TravelProjectCustomTag)
        .filter(
            TravelProjectCustomTag.project_id == project_id,
            TravelProjectCustomTag.custom_tag_id == tag_id,
        )
        .first()
    )
    if existing:
        return {"ok": True, "message": "已存在"}

    link = TravelProjectCustomTag(
        project_id=project_id,
        custom_tag_id=tag_id,
        shared_by_user_id=current_user.id,
    )
    db.add(link)
    db.commit()
    return {"ok": True}
