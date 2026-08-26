"""Authentication routes — register, login, logout, me."""

from typing import Optional

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
from app.services.auth_service import (
    create_user, authenticate_user, create_access_token,
    decode_access_token, get_user_by_id, get_user_by_username,
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
    username: str
    password: str
    display_name: str = ""


class LoginRequest(BaseModel):
    username: str
    password: str


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
    """Register a new user and log them in."""
    # Validate input
    username = data.username.strip()
    if not username or len(username) < 2:
        raise HTTPException(status_code=422, detail="用户名至少需要 2 个字符")
    if len(username) > 100:
        raise HTTPException(status_code=422, detail="用户名不能超过 100 个字符")
    if not data.password or len(data.password) < 6:
        raise HTTPException(status_code=422, detail="密码至少需要 6 个字符")
    if len(data.password) > 128:
        raise HTTPException(status_code=422, detail="密码不能超过 128 个字符")

    try:
        user = create_user(
            db,
            username=username,
            password=data.password,
            display_name=data.display_name or username,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    token = create_access_token(user.id, user.username)
    _set_auth_cookie(response, token)

    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@router.post("/login")
async def login(data: LoginRequest, response: Response, db: Session = Depends(get_db)):
    """Login and set auth cookie."""
    if not data.username or not data.password:
        raise HTTPException(status_code=422, detail="用户名和密码不能为空")

    user = authenticate_user(db, data.username, data.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = create_access_token(user.id, user.username)
    _set_auth_cookie(response, token)

    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@router.post("/logout")
async def logout(response: Response):
    """Clear auth cookie."""
    _clear_auth_cookie(response)
    return {"ok": True}


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
    if not user:
        return {"authenticated": False, "user": None}

    return {
        "authenticated": True,
        "user": {
            "id": user.id,
            "username": user.username,
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
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    """Update display name."""
    token = _extract_token(request, credentials)
    if not token:
        raise HTTPException(status_code=401, detail="请先登录")
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="登录已过期")
    user = get_user_by_id(db, payload.get("sub", ""))
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")

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
    request: Request = None,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    """Upload user avatar image. Max 2MB, PNG/JPEG/WebP only."""
    token = _extract_token(request, credentials)
    if not token:
        raise HTTPException(status_code=401, detail="请先登录")
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="登录已过期")
    user = get_user_by_id(db, payload.get("sub", ""))
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")

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
