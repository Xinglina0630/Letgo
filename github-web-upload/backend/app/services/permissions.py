"""
Unified permission checking for collaboration features.

All permission checks happen server-side. Never trust client-submitted roles.
"""

from fastapi import HTTPException, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.collaboration import TravelProject, TravelProjectMember
from app.routers.auth import get_current_user


# ---- Core permission checkers ----

def _get_membership(db: Session, project_id: str, user_id: str) -> TravelProjectMember:
    """Get active membership record. Also checks project is active. Raises 404 if not a member."""
    # Verify project is active
    project = db.query(TravelProject).filter(
        TravelProject.id == project_id,
        TravelProject.status == "active",
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="旅行项目不存在或已删除")

    member = (
        db.query(TravelProjectMember)
        .filter(
            TravelProjectMember.project_id == project_id,
            TravelProjectMember.user_id == user_id,
            TravelProjectMember.status == "active",
        )
        .first()
    )
    if not member:
        raise HTTPException(status_code=403, detail="你不在该旅行项目中，或已被移除")
    return member


def _get_project(db: Session, project_id: str) -> TravelProject:
    """Get project. Raises 404 if not found or deleted."""
    project = db.query(TravelProject).filter(
        TravelProject.id == project_id,
        TravelProject.status == "active",
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="旅行项目不存在或已删除")
    return project


# ---- FastAPI dependency factories ----

def require_project_member(project_id_param: str = "project_id"):
    """Require authenticated user to be an active member of the project."""

    async def dependency(
        project_id: str = None,  # will be filled from path param
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> TravelProjectMember:
        return _get_membership(db, project_id, user.id)

    return dependency


def require_project_edit_permission(project_id_param: str = "project_id"):
    """Require owner or editor role."""

    async def dependency(
        project_id: str = None,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> TravelProjectMember:
        member = _get_membership(db, project_id, user.id)
        if member.role not in ("owner", "editor"):
            raise HTTPException(status_code=403, detail="只有项目所有者和编辑者可以执行此操作")
        return member

    return dependency


def require_project_owner(project_id_param: str = "project_id"):
    """Require owner role."""

    async def dependency(
        project_id: str = None,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> TravelProjectMember:
        member = _get_membership(db, project_id, user.id)
        if member.role != "owner":
            raise HTTPException(status_code=403, detail="只有项目所有者可以执行此操作")
        return member

    return dependency


def require_project_invite_permission(project_id_param: str = "project_id"):
    """Require owner or editor with can_invite."""

    async def dependency(
        project_id: str = None,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> TravelProjectMember:
        member = _get_membership(db, project_id, user.id)
        if member.role == "owner":
            return member
        if member.role == "editor" and member.can_invite:
            return member
        raise HTTPException(status_code=403, detail="你没有邀请权限")
        return member

    return dependency


# ---- Convenience helpers for service-layer use ----

def check_project_member(db: Session, project_id: str, user_id: str) -> TravelProjectMember:
    return _get_membership(db, project_id, user_id)


def check_project_edit(db: Session, project_id: str, user_id: str) -> TravelProjectMember:
    member = _get_membership(db, project_id, user_id)
    if member.role not in ("owner", "editor"):
        raise HTTPException(status_code=403, detail="你没有编辑权限")
    return member


def check_project_owner(db: Session, project_id: str, user_id: str) -> TravelProjectMember:
    member = _get_membership(db, project_id, user_id)
    if member.role != "owner":
        raise HTTPException(status_code=403, detail="只有项目所有者可以执行此操作")
    return member
