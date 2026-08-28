"""Authentication routes — register, login, logout, me."""

from typing import Optional
from datetime import datetime
import re

from fastapi import APIRouter, Depends, HTTPException, Response, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy.orm import Session

import io
from pathlib import Path

from fastapi import UploadFile, File
from fastapi.responses import StreamingResponse
from app.database import get_db
from app.config import settings
from app.models.user import User
from app.services.auth_service import (
    create_user, authenticate_user, create_access_token,
    decode_access_token, get_user_by_id, get_user_by_username,
    get_user_by_phone, authenticate_phone, hash_password, verify_password,
)

bearer_scheme = HTTPBearer(auto_error=False)

# Avatar storage
AVATAR_DIR = Path(__file__).resolve().parent.parent.parent / "uploads" / "avatars"
AVATAR_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_AVATAR_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
MAX_AVATAR_SIZE = 2 * 1024 * 1024  # 2MB

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ---- Schemas ----
class RegisterRequest(BaseModel):
    phone: str
    password: str
    display_name: str = ""


class LoginRequest(BaseModel):
    phone: str
    password: str


class PhoneRegisterRequest(BaseModel):
    phone: str
    password: str
    display_name: str = ""


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class BindPhoneRequest(BaseModel):
    phone: str
    new_password: str


class UserOut(BaseModel):
    id: str
    username: str
    display_name: str
    is_active: bool
    created_at: str

    class Config:
        from_attributes = True


# ---- Cookie helpers ----
def _set_auth_cookie(response: Response, token: str):
    """Set HttpOnly auth cookie."""
    response.set_cookie(
        key="auth_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.AUTH_COOKIE_SECURE,
        max_age=settings.AUTH_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )


def _clear_auth_cookie(response: Response):
    """Clear auth cookie."""
    response.delete_cookie(
        key="auth_token",
        httponly=True,
        samesite="lax",
        secure=settings.AUTH_COOKIE_SECURE,
        path="/",
    )


def _normalize_phone(value: str) -> str:
    phone = re.sub(r"[\s-]", "", (value or "").strip())
    if phone.startswith("+86"):
        phone = phone[3:]
    if not re.fullmatch(r"1[3-9]\d{9}", phone):
        raise HTTPException(status_code=422, detail="请输入正确的11位中国大陆手机号")
    return phone


def _validate_password(password: str, field_name: str = "密码") -> None:
    if len(password or "") < 8:
        raise HTTPException(status_code=422, detail=f"{field_name}至少需要8个字符")
    if len(password) > 128:
        raise HTTPException(status_code=422, detail=f"{field_name}不能超过128个字符")


def _user_payload(user, token: str = "") -> dict:
    return {
        "access_token": token,
        "token_type": "bearer",
        "id": user.id,
        "username": user.username,
        "phone": user.phone or "",
        "display_name": user.display_name,
        "avatar_url": user.wechat_avatar_url or "",
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


# ---- Token extraction (Cookie OR Bearer) ----
def _extract_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials],
) -> Optional[str]:
    """Extract JWT from HttpOnly Cookie first, then Authorization Bearer header."""
    # Priority 1: HttpOnly Cookie (Web)
    token = request.cookies.get("auth_token")
    if token:
        return token
    # Priority 2: Authorization Bearer (Mini Program / API clients)
    if credentials and credentials.scheme == "Bearer":
        return credentials.credentials
    return None


# ---- Auth dependencies ----
async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    """Extract and validate current user from Cookie OR Bearer token."""
    token = _extract_token(request, credentials)
    if not token:
        raise HTTPException(status_code=401, detail="请先登录")

    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="无效的登录凭证")

    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已被禁用")
    if int(payload.get("ver", 0)) != int(user.token_version or 0):
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")

    return user


async def get_optional_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    """Like get_current_user but returns None for unauthenticated requests."""
    token = _extract_token(request, credentials)
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    return get_user_by_id(db, user_id)


# ---- Routes ----
@router.post("/register", status_code=201)
async def register(data: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    """Backward-compatible alias for phone registration."""
    return await phone_register(
        PhoneRegisterRequest(phone=data.phone, password=data.password, display_name=data.display_name),
        response,
        db,
    )


@router.post("/phone/register", status_code=201)
async def phone_register(data: PhoneRegisterRequest, response: Response, db: Session = Depends(get_db)):
    phone = _normalize_phone(data.phone)
    _validate_password(data.password)
    if get_user_by_phone(db, phone):
        raise HTTPException(status_code=409, detail="该手机号已经注册，请直接登录")
    user = User(
        username=phone,
        phone=phone,
        password_hash=hash_password(data.password),
        password_updated_at=datetime.utcnow(),
        display_name=(data.display_name or "").strip() or f"用户{phone[-4:]}",
        auth_source="phone",
        last_login_at=datetime.utcnow(),
        token_version=0,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user.id, user.username, user.token_version)
    _set_auth_cookie(response, token)
    return _user_payload(user, token)


@router.post("/login")
async def login(data: LoginRequest, response: Response, db: Session = Depends(get_db)):
    """Login with the unique phone number."""
    phone = _normalize_phone(data.phone)
    if not data.password:
        raise HTTPException(status_code=422, detail="手机号和密码不能为空")
    user = authenticate_phone(db, phone, data.password)
    if not user:
        raise HTTPException(status_code=401, detail="手机号或密码错误")
    user.last_login_at = datetime.utcnow()
    db.commit()
    token = create_access_token(user.id, user.username, user.token_version)
    _set_auth_cookie(response, token)
    return _user_payload(user, token)


@router.post("/logout")
async def logout(response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Revoke all existing tokens for this user and clear the cookie."""
    user.token_version = int(user.token_version or 0) + 1
    db.commit()
    _clear_auth_cookie(response)
    return {"ok": True}


@router.post("/change-password")
async def change_password(data: ChangePasswordRequest, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _validate_password(data.new_password, "新密码")
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="原密码错误")
    if verify_password(data.new_password, user.password_hash):
        raise HTTPException(status_code=422, detail="新密码不能与原密码相同")
    user.password_hash = hash_password(data.new_password)
    user.password_updated_at = datetime.utcnow()
    user.token_version = int(user.token_version or 0) + 1
    db.commit()
    return {"ok": True, "relogin_required": True}


@router.post("/bind-phone")
async def bind_phone(data: BindPhoneRequest, user=Depends(get_current_user), db: Session = Depends(get_db)):
    phone = _normalize_phone(data.phone)
    _validate_password(data.new_password, "密码")
    owner = get_user_by_phone(db, phone)
    if owner and owner.id != user.id:
        raise HTTPException(status_code=409, detail="该手机号已经绑定其他账号")
    user.phone = phone
    user.password_hash = hash_password(data.new_password)
    user.password_updated_at = datetime.utcnow()
    user.auth_source = "phone"
    user.token_version = int(user.token_version or 0) + 1
    db.commit()
    return {"ok": True, "relogin_required": True}


@router.get("/me")
async def me(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    """Return current user info or guest status. Supports Cookie and Bearer."""
    token = _extract_token(request, credentials)
    if not token:
        return {"authenticated": False, "user": None}

    payload = decode_access_token(token)
    if not payload:
        return {"authenticated": False, "user": None}

    user_id = payload.get("sub")
    if not user_id:
        return {"authenticated": False, "user": None}

    user = get_user_by_id(db, user_id)
    if not user or not user.is_active:
        return {"authenticated": False, "user": None}
    if int(payload.get("ver", 0)) != int(user.token_version or 0):
        return {"authenticated": False, "user": None}

    return {
        "authenticated": True,
        "user": {
            "id": user.id,
            "username": user.username,
            "phone": user.phone or "",
            "display_name": user.display_name,
            "avatar_url": user.wechat_avatar_url or "",
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },
    }


# ---- Profile update ----
class ProfileUpdateRequest(BaseModel):
    display_name: str = ""


@router.patch("/profile")
async def update_profile(
    data: ProfileUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update display name."""
    name = data.display_name.strip()
    if not name or len(name) < 1:
        raise HTTPException(status_code=422, detail="名称不能为空")
    if len(name) > 50:
        raise HTTPException(status_code=422, detail="名称不能超过50个字符")

    user.display_name = name
    db.commit()
    return {"ok": True, "display_name": name}


# ---- Avatar upload ----
@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload user avatar image. Max 2MB, PNG/JPEG/WebP only."""
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="请选择图片")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="图片为空")
    if len(content) > MAX_AVATAR_SIZE:
        raise HTTPException(status_code=400, detail="图片不能超过 2MB")

    # Validate image type
    import imghdr
    img_type = imghdr.what(None, h=content[:32])
    if img_type not in ("png", "jpeg", "webp"):
        raise HTTPException(status_code=400, detail="仅支持 PNG、JPEG、WebP 格式")

    # Store in MySQL so the avatar survives CloudRun restarts and scaling.
    content_type = "image/jpeg" if img_type == "jpeg" else f"image/{img_type}"
    avatar_url = f"/api/auth/avatar/{user.id}"
    user.avatar_content = content
    user.avatar_content_type = content_type
    user.wechat_avatar_url = avatar_url
    db.commit()

    return {"ok": True, "avatar_url": avatar_url}


@router.get("/avatar/{user_id}")
async def get_avatar(user_id: str, db: Session = Depends(get_db)):
    """Serve a persistent avatar stored in MySQL."""
    user = get_user_by_id(db, user_id)
    if not user or not user.avatar_content:
        raise HTTPException(status_code=404, detail="头像不存在")
    return StreamingResponse(
        io.BytesIO(user.avatar_content),
        media_type=user.avatar_content_type or "image/jpeg",
        headers={"Cache-Control": "public, max-age=3600"},
    )
