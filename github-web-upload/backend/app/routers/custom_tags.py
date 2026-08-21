"""
Custom place tags API — user-created POI tags with optional project sharing.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import get_db
from app.models.custom_tags import CustomPlaceTag, TravelProjectCustomTag
from app.models.collaboration import TravelProjectMember
from app.models.user import User
from app.routers.auth import get_current_user
from app.services.permissions import _get_membership

router = APIRouter(prefix="/api/custom-place-tags", tags=["custom-tags"])

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

    db.commit()
    db.refresh(tag)

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
# DELETE — archive a tag (owner only, soft-delete)
# ---------------------------------------------------------------------------

@router.delete("/{tag_id}")
async def archive_custom_tag(
    tag_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Archive a custom tag. Only the owner can do this. Does not affect existing itinerary nodes."""

    tag = db.query(CustomPlaceTag).filter(CustomPlaceTag.id == tag_id).first()
    if not tag:
        raise HTTPException(404, "标签不存在")
    if tag.owner_user_id != current_user.id:
        raise HTTPException(403, "只能归档自己创建的标签")

    tag.status = "archived"
    tag.updated_at = datetime.utcnow()
    db.commit()
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
