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


def _normalize_code(code: str) -> str:
    return "".join(ch for ch in (code or "").upper() if ch.isalnum())


def _find_invite(db: Session, value: str, by_code: bool = False, lock: bool = False):
    normalized = _normalize_code(value) if by_code else value
    column = TravelProjectInvite.code_hash if by_code else TravelProjectInvite.token_hash
    query = db.query(TravelProjectInvite).filter(column == hash_token(normalized))
    return query.with_for_update().first() if lock else query.first()


def _preview(invite: TravelProjectInvite, db: Session):
    if not invite or invite.revoked_at:
        raise HTTPException(status_code=404, detail="邀请不存在或已失效")
    if invite.expires_at and invite.expires_at < datetime.utcnow():
        return {"project_name": "", "inviter_name": "", "role": invite.role,
                "scope": invite.scope, "expires_at": invite.expires_at.isoformat(), "is_expired": True}
    if invite.used_count >= invite.max_uses:
        raise HTTPException(status_code=404, detail="邀请已用完")
    project = db.query(TravelProject).filter(
        TravelProject.id == invite.project_id, TravelProject.status == "active",
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="旅行项目不存在或已删除")
    inviter = db.query(User).filter(User.id == invite.inviter_id).first()
    return {"project_name": project.name, "inviter_name": inviter.display_name if inviter else "未知用户",
            "role": invite.role, "scope": invite.scope,
            "expires_at": invite.expires_at.isoformat() if invite.expires_at else None, "is_expired": False}


def _accept(invite: TravelProjectInvite, db: Session, user: User):
    if not invite or invite.revoked_at:
        raise HTTPException(status_code=404, detail="邀请不存在或已失效")
    if invite.expires_at and invite.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="邀请已过期")
    existing = db.query(TravelProjectMember).filter(
        TravelProjectMember.project_id == invite.project_id,
        TravelProjectMember.user_id == user.id,
        TravelProjectMember.status == "active",
    ).first()
    if existing:
        return {"ok": True, "project_id": invite.project_id, "message": "你已经是项目成员"}
    if invite.used_count >= invite.max_uses:
        raise HTTPException(status_code=400, detail="邀请已用完")
    invite.used_count += 1
    prev_member = db.query(TravelProjectMember).filter(
        TravelProjectMember.project_id == invite.project_id,
        TravelProjectMember.user_id == user.id,
    ).first()
    if prev_member:
        prev_member.role, prev_member.can_invite, prev_member.status = invite.role, invite.can_invite, "active"
        prev_member.updated_at = datetime.utcnow()
    else:
        db.add(TravelProjectMember(project_id=invite.project_id, user_id=user.id,
                                   role=invite.role, can_invite=invite.can_invite, status="active"))
    db.add(TravelProjectEvent(project_id=invite.project_id, actor_id=user.id,
                              event_type="member.joined", summary="通过房间邀请加入项目",
                              change_data=json.dumps({"inviter_id": invite.inviter_id, "role": invite.role})))
    db.commit()
    return {"ok": True, "project_id": invite.project_id, "message": "已成功加入项目"}


@router.get("/by-code/{code}/preview")
def preview_invite_code(code: str, db: Session = Depends(get_db)):
    return _preview(_find_invite(db, code, by_code=True), db)


@router.post("/by-code/{code}/accept")
def accept_invite_code(code: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _accept(_find_invite(db, code, by_code=True, lock=True), db, user)


@router.get("/{token}/preview")
def preview_invite(
    token: str,
    db: Session = Depends(get_db),
):
    """
    Preview invite details before accepting.
    Does not require login — anyone with the token can preview.
    """
    return _preview(_find_invite(db, token), db)


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
    return _accept(_find_invite(db, token, lock=True), db, user)
