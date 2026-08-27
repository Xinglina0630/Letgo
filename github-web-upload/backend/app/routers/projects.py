"""
TravelProject CRUD, member management, and invite endpoints.

/users/{user_id} -> Projects
/with me -> shared projects
/invites/<token>/preview, accept
/members/<mid>/update, remove
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.collaboration import (
    TravelProject, TravelProjectMember, TravelProjectInvite, TravelProjectEvent,
    gen_uuid, gen_invite_token, gen_invite_code, hash_token,
)
from app.routers.auth import get_current_user
from app.services.permissions import (
    check_project_member, check_project_edit, check_project_owner,
)


def _broadcast(project_id: str, event_type: str, actor: dict, entity_id: str = "", summary: str = ""):
    """Queue a background broadcast via WebSocket. Non-blocking."""
    async def _send():
        try:
            from app.routers.ws_collaboration import broadcast_project_event
            await broadcast_project_event(project_id, {
                "event_type": event_type,
                "actor": actor,
                "entity_id": entity_id,
                "summary": summary,
            })
        except Exception:
            pass  # broadcast failure should not fail the HTTP request

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_send())
    except RuntimeError:
        pass

router = APIRouter(prefix="/api/projects", tags=["projects"])


# ====================================================================
# Schemas
# ====================================================================

class ProjectCreate(BaseModel):
    name: str
    city: str
    description: str = ""


class ProjectOut(BaseModel):
    id: str; owner_id: str; name: str; city: str; description: str
    status: str; version: int; member_count: int = 0
    created_at: Optional[str] = None; updated_at: Optional[str] = None

    class Config: from_attributes = True


class MemberOut(BaseModel):
    id: str; user_id: str; display_name: str; role: str
    can_invite: bool; joined_at: Optional[str] = None

    class Config: from_attributes = True


VALID_INVITE_ROLES = {"editor", "viewer"}
VALID_INVITE_SCOPES = {"all", "itinerary", "flights"}


class InviteCreate(BaseModel):
    role: str = "editor"
    scope: str = "all"
    can_invite: bool = False
    expires_in_hours: int = 24
    max_uses: int = 1

    def model_post_init(self, __context) -> None:
        if self.role not in VALID_INVITE_ROLES:
            raise ValueError(f"role must be one of: {', '.join(sorted(VALID_INVITE_ROLES))}")
        if self.scope not in VALID_INVITE_SCOPES:
            raise ValueError(f"scope must be one of: {', '.join(sorted(VALID_INVITE_SCOPES))}")
        if self.expires_in_hours < 1 or self.expires_in_hours > 168:  # 1h to 7 days
            raise ValueError("expires_in_hours must be between 1 and 168")
        if self.max_uses < 1 or self.max_uses > 50:
            raise ValueError("max_uses must be between 1 and 50")


class InviteOut(BaseModel):
    invite_token: str
    invite_code: str
    expires_at: str
    share_path: str


class InvitePreview(BaseModel):
    project_name: str
    inviter_name: str
    role: str
    scope: str
    expires_at: str
    is_expired: bool


class EventOut(BaseModel):
    id: str; event_type: str; actor_name: str
    summary: str; created_at: Optional[str] = None

    class Config: from_attributes = True


# ====================================================================
# Project CRUD
# ====================================================================

@router.post("", response_model=ProjectOut, status_code=201)
def create_project(
    data: ProjectCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a new travel project. Creator becomes owner."""
    project = TravelProject(
        owner_id=user.id,
        name=data.name, city=data.city,
        description=data.description,
    )
    db.add(project)
    db.flush()

    # Add creator as owner member
    member = TravelProjectMember(
        project_id=project.id,
        user_id=user.id,
        role="owner",
        can_invite=True,
        status="active",
    )
    db.add(member)

    # Log event
    event = TravelProjectEvent(
        project_id=project.id,
        actor_id=user.id,
        event_type="project.created",
        summary=f"创建了旅行项目「{data.name}」",
    )
    db.add(event)

    db.commit()
    db.refresh(project)

    _broadcast(project.id, "project.created",
               actor={"id": user.id, "name": user.display_name},
               summary=f"创建了旅行项目「{project.name}」")

    return _project_out(project, db)


@router.get("", response_model=List[ProjectOut])
def list_my_projects(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List projects: mine (owned) and shared with me."""
    # Owned projects
    owned = db.query(TravelProject).filter(
        TravelProject.owner_id == user.id,
        TravelProject.status == "active",
    ).all()

    # Projects where I'm a member
    shared = (
        db.query(TravelProject)
        .join(TravelProjectMember)
        .filter(
            TravelProjectMember.user_id == user.id,
            TravelProjectMember.status == "active",
            TravelProject.status == "active",
        )
        .all()
    )

    # Deduplicate (owner is also a member)
    seen = set()
    result = []
    for p in owned + shared:
        if p.id not in seen:
            seen.add(p.id)
            result.append(_project_out(p, db))
    return result


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get project details. Must be a member."""
    member = check_project_member(db, project_id, user.id)
    project = member.project
    return _project_out(project, db)


@router.patch("/{project_id}")
def update_project(
    project_id: str,
    data: ProjectCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update project name/city/description. Owner or editor only."""
    member = check_project_edit(db, project_id, user.id)
    project = member.project
    project.name = data.name or project.name
    project.city = data.city or project.city
    project.description = data.description or project.description
    project.version += 1

    db.add(TravelProjectEvent(
        project_id=project_id, actor_id=user.id,
        event_type="project.updated", summary=f"更新了项目信息",
    ))
    db.commit()
    return {"ok": True, "version": project.version}


@router.delete("/{project_id}")
def delete_project(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Soft-delete project and revoke all active invites. Owner only."""
    member = check_project_owner(db, project_id, user.id)
    project = member.project
    project.status = "deleted"
    project.updated_at = datetime.utcnow()

    # Revoke all active invites
    now = datetime.utcnow()
    db.query(TravelProjectInvite).filter(
        TravelProjectInvite.project_id == project_id,
        TravelProjectInvite.revoked_at.is_(None),
    ).update({"revoked_at": now}, synchronize_session="fetch")

    db.add(TravelProjectEvent(
        project_id=project_id, actor_id=user.id,
        event_type="project.deleted", summary="删除了项目",
    ))
    db.commit()
    return {"ok": True}


# ====================================================================
# Members
# ====================================================================

@router.get("/{project_id}/members", response_model=List[MemberOut])
def list_members(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all active members of a project."""
    check_project_member(db, project_id, user.id)
    members = (
        db.query(TravelProjectMember)
        .filter(
            TravelProjectMember.project_id == project_id,
            TravelProjectMember.status == "active",
        )
        .all()
    )
    result = []
    for m in members:
        u = db.query(User).filter(User.id == m.user_id).first()
        result.append(MemberOut(
            id=m.id, user_id=m.user_id,
            display_name=u.display_name if u else "Unknown",
            role=m.role, can_invite=m.can_invite,
            joined_at=m.joined_at.isoformat() if m.joined_at else None,
        ))
    return result


@router.patch("/{project_id}/members/{member_id}")
def update_member_role(
    project_id: str, member_id: str,
    body: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update member role/can_invite. Owner only.
    Cannot create/remove owner through this endpoint."""
    check_project_owner(db, project_id, user.id)

    member = db.query(TravelProjectMember).filter(
        TravelProjectMember.id == member_id,
        TravelProjectMember.project_id == project_id,
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")

    # Cannot change the owner's role through this endpoint
    if member.role == "owner":
        raise HTTPException(status_code=400, detail="不能通过此接口修改所有者角色")

    new_role = body.get("role")
    if new_role:
        # Cannot set anyone to owner via this endpoint
        if new_role == "owner":
            raise HTTPException(
                status_code=400,
                detail="不能通过此接口设置所有者。如需转让所有权，请使用专门的所有权转移功能。",
            )
        if new_role in ("editor", "viewer"):
            member.role = new_role
    if "can_invite" in body:
        member.can_invite = bool(body["can_invite"])

    member.updated_at = datetime.utcnow()
    db.add(TravelProjectEvent(
        project_id=project_id, actor_id=user.id,
        event_type="member.role_changed",
        summary=f"修改了成员权限",
    ))
    db.commit()
    return {"ok": True}


@router.delete("/{project_id}/members/{member_id}")
def remove_member(
    project_id: str, member_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Remove a member from project. Owner only."""
    check_project_owner(db, project_id, user.id)

    member = db.query(TravelProjectMember).filter(
        TravelProjectMember.id == member_id,
        TravelProjectMember.project_id == project_id,
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")

    if member.role == "owner":
        raise HTTPException(status_code=400, detail="不能移除项目所有者")

    member.status = "removed"
    member.updated_at = datetime.utcnow()

    db.add(TravelProjectEvent(
        project_id=project_id, actor_id=user.id,
        event_type="member.removed",
        summary=f"移除了成员",
        change_data=json.dumps({"removed_user_id": member.user_id}),
    ))
    db.commit()
    return {"ok": True}


# ====================================================================
# Invites
# ====================================================================

@router.post("/{project_id}/invites", response_model=InviteOut)
def create_invite(
    project_id: str,
    data: InviteCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create an invite link. Requires owner or can_invite.
    Owner can invite editor/viewer. Editor with can_invite can only invite viewer."""
    member = check_project_member(db, project_id, user.id)
    if member.role != "owner" and not (member.role == "editor" and member.can_invite):
        raise HTTPException(status_code=403, detail="你没有邀请权限")

    # Editor can only invite viewer (not editor, not owner)
    if member.role == "editor":
        if data.role != "viewer":
            raise HTTPException(
                status_code=403,
                detail="作为编辑者，你只能邀请查看者。邀请编辑者需要项目所有者操作。",
            )
        data.can_invite = False  # editor-invited viewers cannot invite further

    # Validate the invite data (role/scope/expiry/uses)
    try:
        data.model_post_init(None)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    project = member.project

    token = gen_invite_token()
    code = gen_invite_code()
    while db.query(TravelProjectInvite.id).filter(TravelProjectInvite.code_hash == hash_token(code)).first():
        code = gen_invite_code()
    expires = datetime.utcnow() + timedelta(hours=data.expires_in_hours)

    invite = TravelProjectInvite(
        project_id=project_id,
        inviter_id=user.id,
        token_hash=hash_token(token),
        code_hash=hash_token(code),
        role=data.role,
        scope=data.scope,
        can_invite=data.can_invite,
        expires_at=expires,
        max_uses=data.max_uses,
        used_count=0,
    )
    db.add(invite)
    db.add(TravelProjectEvent(
        project_id=project_id, actor_id=user.id,
        event_type="invite.created",
        summary=f"创建了一个邀请（角色：{data.role}）",
    ))
    db.commit()

    return InviteOut(
        invite_token=token,
        invite_code=code,
        expires_at=expires.isoformat(),
        share_path=f"/pages/invite/accept?invite={token}",
    )


@router.get("/{project_id}/invites")
def list_invites(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List active invites for a project."""
    check_project_member(db, project_id, user.id)

    invites = db.query(TravelProjectInvite).filter(
        TravelProjectInvite.project_id == project_id,
        TravelProjectInvite.revoked_at.is_(None),
    ).all()

    return [{
        "id": inv.id,
        "role": inv.role,
        "scope": inv.scope,
        "expires_at": inv.expires_at.isoformat() if inv.expires_at else None,
        "used_count": inv.used_count,
        "max_uses": inv.max_uses,
        "is_expired": inv.expires_at < datetime.utcnow() if inv.expires_at else False,
        "created_at": inv.created_at.isoformat() if inv.created_at else None,
    } for inv in invites]


@router.delete("/{project_id}/invites/{invite_id}")
def revoke_invite(
    project_id: str, invite_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Revoke an active invite."""
    member = check_project_member(db, project_id, user.id)
    if member.role != "owner" and not (member.role == "editor" and member.can_invite):
        raise HTTPException(status_code=403, detail="你没有权限撤销邀请")

    invite = db.query(TravelProjectInvite).filter(
        TravelProjectInvite.id == invite_id,
        TravelProjectInvite.project_id == project_id,
    ).first()
    if not invite:
        raise HTTPException(status_code=404, detail="邀请不存在")

    invite.revoked_at = datetime.utcnow()
    db.add(TravelProjectEvent(
        project_id=project_id, actor_id=user.id,
        event_type="invite.revoked", summary="撤销了邀请",
    ))
    db.commit()
    return {"ok": True}


# ====================================================================
# Events
# ====================================================================

@router.get("/{project_id}/events", response_model=List[EventOut])
def list_events(
    project_id: str,
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get recent project activity/events."""
    check_project_member(db, project_id, user.id)

    events = (
        db.query(TravelProjectEvent)
        .filter(TravelProjectEvent.project_id == project_id)
        .order_by(TravelProjectEvent.created_at.desc())
        .limit(limit)
        .all()
    )

    result = []
    for e in events:
        actor = db.query(User).filter(User.id == e.actor_id).first() if e.actor_id else None
        result.append(EventOut(
            id=e.id, event_type=e.event_type,
            actor_name=actor.display_name if actor else "系统",
            summary=e.summary,
            created_at=e.created_at.isoformat() if e.created_at else None,
        ))
    return result


# ====================================================================
# Helpers
# ====================================================================

def _project_out(p: TravelProject, db: Session) -> dict:
    mc = db.query(TravelProjectMember).filter(
        TravelProjectMember.project_id == p.id,
        TravelProjectMember.status == "active",
    ).count()
    return ProjectOut(
        id=p.id, owner_id=p.owner_id, name=p.name, city=p.city,
        description=p.description or "", status=p.status,
        version=p.version or 1, member_count=mc,
        created_at=p.created_at.isoformat() if p.created_at else None,
        updated_at=p.updated_at.isoformat() if p.updated_at else None,
    )
