"""
Public invite accept flow — preview and accept invite tokens.

Invite tokens are only stored as hashes in the database.
The raw token is transmitted via URL and never logged.
"""

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.collaboration import (
    TravelProject, TravelProjectMember, TravelProjectInvite, TravelProjectEvent,
    hash_token,
)
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/invites", tags=["invites"])


@router.get("/{token}/preview")
def preview_invite(
    token: str,
    db: Session = Depends(get_db),
):
    """
    Preview invite details before accepting.
    Does not require login — anyone with the token can preview.
    """
    token_hash = hash_token(token)

    invite = db.query(TravelProjectInvite).filter(
        TravelProjectInvite.token_hash == token_hash,
    ).first()

    if not invite:
        raise HTTPException(status_code=404, detail="邀请不存在或已失效")

    # Check revoked
    if invite.revoked_at:
        raise HTTPException(status_code=404, detail="邀请已被撤销")

    # Check expired
    if invite.expires_at and invite.expires_at < datetime.utcnow():
        return {
            "project_name": "",
            "inviter_name": "",
            "role": invite.role,
            "scope": invite.scope,
            "expires_at": invite.expires_at.isoformat(),
            "is_expired": True,
        }

    # Check not exhausted
    if invite.used_count >= invite.max_uses:
        raise HTTPException(status_code=404, detail="邀请已用完")

    # Get project and inviter info — reject deleted projects
    project = db.query(TravelProject).filter(
        TravelProject.id == invite.project_id,
        TravelProject.status == "active",
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="旅行项目不存在或已删除")

    inviter = db.query(User).filter(User.id == invite.inviter_id).first()
    inviter_name = inviter.display_name if inviter else "未知用户"

    return {
        "project_name": project.name,
        "inviter_name": inviter_name,
        "role": invite.role,
        "scope": invite.scope,
        "expires_at": invite.expires_at.isoformat() if invite.expires_at else None,
        "is_expired": False,
    }


@router.post("/{token}/accept")
def accept_invite(
    token: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Accept an invite. Must be logged in.
    Uses DB-level optimistic locking for concurrent acceptance prevention.
    Idempotent — accepting the same invite twice is safe.
    """
    token_hash = hash_token(token)

    invite = db.query(TravelProjectInvite).filter(
        TravelProjectInvite.token_hash == token_hash,
    ).with_for_update().first()

    if not invite:
        raise HTTPException(status_code=404, detail="邀请不存在或已失效")

    if invite.revoked_at:
        raise HTTPException(status_code=404, detail="邀请已被撤销")

    if invite.expires_at and invite.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="邀请已过期")

    # Check if user is already an active member (idempotent)
    existing = db.query(TravelProjectMember).filter(
        TravelProjectMember.project_id == invite.project_id,
        TravelProjectMember.user_id == user.id,
        TravelProjectMember.status == "active",
    ).first()

    if existing:
        return {
            "ok": True,
            "project_id": invite.project_id,
            "message": "你已经是项目成员",
        }

    # Check if this invite still has uses remaining
    if invite.used_count >= invite.max_uses:
        raise HTTPException(status_code=400, detail="邀请已用完")

    # Accept — create member and increment usage in same transaction
    invite.used_count += 1

    # Check if previously removed — reactivate
    prev_member = db.query(TravelProjectMember).filter(
        TravelProjectMember.project_id == invite.project_id,
        TravelProjectMember.user_id == user.id,
    ).first()

    if prev_member:
        prev_member.role = invite.role
        prev_member.can_invite = invite.can_invite
        prev_member.status = "active"
        prev_member.updated_at = datetime.utcnow()
    else:
        member = TravelProjectMember(
            project_id=invite.project_id,
            user_id=user.id,
            role=invite.role,
            can_invite=invite.can_invite,
            status="active",
        )
        db.add(member)

    # Log event
    db.add(TravelProjectEvent(
        project_id=invite.project_id,
        actor_id=user.id,
        event_type="member.joined",
        summary=f"通过邀请加入项目",
        change_data=json.dumps({"inviter_id": invite.inviter_id, "role": invite.role}),
    ))

    db.commit()

    return {
        "ok": True,
        "project_id": invite.project_id,
        "message": "已成功加入项目",
    }
