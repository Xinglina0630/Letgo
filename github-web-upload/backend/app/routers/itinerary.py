"""Itinerary CRUD API with auth protection and project collaboration."""

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.itinerary import ItineraryCreateRequest, ItineraryOut
from app.services.itinerary_service import itinerary_service
from app.services.permissions import _get_membership
from app.routers.auth import get_current_user, get_optional_user
from app.models.user import User
from app.models.itinerary import Itinerary
from app.models.collaboration import (
    TravelProject, TravelProjectMember, TravelProjectInvite, TravelProjectEvent,
    gen_invite_token, hash_token,
)

router = APIRouter(prefix="/api/itineraries", tags=["itinerary"])


def _check_itinerary_access(db: Session, itinerary: Itinerary, user_id: str) -> bool:
    """Check if user can access an itinerary (owner or project member)."""
    if itinerary.user_id == user_id:
        return True
    if itinerary.project_id:
        membership = _get_membership(db, itinerary.project_id, user_id)
        if membership and membership.status == "active":
            return True
    return False


def _check_itinerary_edit(db: Session, itinerary: Itinerary, user_id: str) -> bool:
    """Check if user can edit an itinerary (owner or project editor/owner)."""
    if itinerary.user_id == user_id:
        return True
    if itinerary.project_id:
        membership = _get_membership(db, itinerary.project_id, user_id)
        if membership and membership.status == "active" and membership.role in ("owner", "editor"):
            return True
    return False


@router.post("", response_model=ItineraryOut, status_code=201)
async def create_itinerary(
    data: ItineraryCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """创建旅游攻略（需要登录）。如果提供 project_id，需要项目编辑权限。"""
    project_id = getattr(data, 'project_id', None)
    if project_id:
        membership = _get_membership(db, project_id, user.id)
        if not membership or membership.status != "active":
            raise HTTPException(403, "你没有该项目的访问权限")
        if membership.role == "viewer":
            raise HTTPException(403, "查看者不能创建攻略")
    try:
        itinerary = await itinerary_service.create(db, data, user.id)
        return itinerary
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="创建行程失败")


@router.get("", response_model=List[ItineraryOut])
async def list_itineraries(
    project_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """获取行程列表。提供 project_id 时返回项目行程（需成员权限）。"""
    if project_id:
        membership = _get_membership(db, project_id, user.id)
        if not membership or membership.status != "active":
            raise HTTPException(403, "你没有该项目的访问权限")
        return await itinerary_service.list_by_project(db, project_id)
    return await itinerary_service.list_by_user(db, user.id)


@router.get("/{itinerary_id}", response_model=ItineraryOut)
async def get_itinerary(
    itinerary_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """获取行程详情（个人行程仅创建者可读，项目行程成员可读）。"""
    itinerary = db.query(Itinerary).filter(Itinerary.id == itinerary_id).first()
    if not itinerary:
        raise HTTPException(status_code=404, detail="Itinerary not found")
    if not _check_itinerary_access(db, itinerary, user.id):
        raise HTTPException(status_code=404, detail="Itinerary not found")
    return itinerary


@router.put("/{itinerary_id}", response_model=ItineraryOut)
async def update_itinerary(
    itinerary_id: str,
    data: ItineraryCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """更新行程。个人行程仅创建者可编辑，项目行程 owner/editor 可编辑。支持 version 乐观锁。"""
    itinerary = db.query(Itinerary).filter(Itinerary.id == itinerary_id).first()
    if not itinerary:
        raise HTTPException(status_code=404, detail="Itinerary not found")
    if not _check_itinerary_edit(db, itinerary, user.id):
        raise HTTPException(status_code=403, detail="你没有编辑该行程的权限")

    # Version optimistic locking
    client_version = getattr(data, 'version', None)
    if client_version is not None and client_version != itinerary.version:
        raise HTTPException(
            status_code=409,
            detail=f"版本冲突：你的版本是 {client_version}，服务器版本是 {itinerary.version}。请刷新后重试。",
        )

    try:
        updated = await itinerary_service.update(db, itinerary_id, data, user.id)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="更新行程失败")

    if not updated:
        raise HTTPException(status_code=404, detail="Itinerary not found")
    return updated


@router.delete("/{itinerary_id}")
async def delete_itinerary(
    itinerary_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """删除行程。个人行程仅创建者可删除，项目行程 owner 可删除。"""
    itinerary = db.query(Itinerary).filter(Itinerary.id == itinerary_id).first()
    if not itinerary:
        raise HTTPException(status_code=404, detail="Itinerary not found")
    if not _check_itinerary_edit(db, itinerary, user.id):
        raise HTTPException(status_code=403, detail="你没有删除该行程的权限")

    deleted = await itinerary_service.delete(db, itinerary_id, user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Itinerary not found")
    return {"ok": True}


@router.post("/{itinerary_id}/share")
async def share_itinerary(
    itinerary_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Turn a personal itinerary into a project when needed and create an editor invite."""
    itinerary = db.query(Itinerary).filter(Itinerary.id == itinerary_id).first()
    if not itinerary:
        raise HTTPException(status_code=404, detail="攻略不存在")
    if itinerary.user_id != user.id:
        raise HTTPException(status_code=403, detail="只有攻略创建者可以邀请同行者")

    if itinerary.project_id:
        project = db.query(TravelProject).filter(
            TravelProject.id == itinerary.project_id,
            TravelProject.status == "active",
        ).first()
        if not project:
            raise HTTPException(status_code=404, detail="关联的旅行项目不存在")
    else:
        project = TravelProject(
            owner_id=user.id,
            name=itinerary.name,
            city=itinerary.city,
            description=itinerary.description or "",
        )
        db.add(project)
        db.flush()
        db.add(TravelProjectMember(
            project_id=project.id, user_id=user.id,
            role="owner", can_invite=True, status="active",
        ))
        itinerary.project_id = project.id
        db.add(TravelProjectEvent(
            project_id=project.id, actor_id=user.id,
            event_type="project.created",
            summary=f"为攻略「{itinerary.name}」创建了协作项目",
        ))

    token = gen_invite_token()
    expires = datetime.utcnow() + timedelta(days=7)
    db.add(TravelProjectInvite(
        project_id=project.id,
        inviter_id=user.id,
        token_hash=hash_token(token),
        role="editor",
        scope="itinerary",
        can_invite=False,
        expires_at=expires,
        max_uses=20,
        used_count=0,
    ))
    db.add(TravelProjectEvent(
        project_id=project.id, actor_id=user.id,
        event_type="invite.created", entity_type="itinerary", entity_id=itinerary.id,
        summary="创建了攻略协作邀请",
    ))
    db.commit()
    return {
        "project_id": project.id,
        "share_path": f"/pages/invite/accept?invite={token}",
        "expires_at": expires.isoformat(),
    }


# ---- Backward-compatible route under /api/itinerary ----
_legacy_router = APIRouter(prefix="/api/itinerary", tags=["itinerary-legacy"])


@_legacy_router.post("", response_model=ItineraryOut, status_code=201)
async def create_itinerary_legacy(
    data: ItineraryCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """[Legacy] 创建旅游攻略。"""
    try:
        itinerary = await itinerary_service.create(db, data, user.id)
        return itinerary
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="创建行程失败")


@_legacy_router.get("/{itinerary_id}", response_model=ItineraryOut)
async def get_itinerary_legacy(
    itinerary_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """[Legacy] 获取行程详情。"""
    itinerary = db.query(Itinerary).filter(Itinerary.id == itinerary_id).first()
    if not itinerary:
        raise HTTPException(status_code=404, detail="Itinerary not found")
    if not _check_itinerary_access(db, itinerary, user.id):
        raise HTTPException(status_code=404, detail="Itinerary not found")
    return itinerary
