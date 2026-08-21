"""WeChat Mini Program login endpoint."""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.services.wechat_service import code2session
from app.services.auth_service import create_access_token

router = APIRouter(prefix="/api/auth/wechat", tags=["auth-wechat"])


class WechatLoginRequest(BaseModel):
    code: str


class WechatLoginResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    user_id: str
    display_name: str
    is_new_user: bool = False


@router.post("/login", response_model=WechatLoginResponse)
async def wechat_login(data: WechatLoginRequest, db: Session = Depends(get_db)):
    """
    Exchange wx.login code for internal user session.

    1. Calls WeChat code2Session (server-side only)
    2. Finds or creates User by openid
    3. Returns internal JWT access token
    """
    if not data.code or not data.code.strip():
        raise HTTPException(status_code=422, detail="code is required")

    try:
        wx_data = await code2session(data.code)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    openid = wx_data["openid"]
    unionid = wx_data.get("unionid", "") or None

    if not openid:
        raise HTTPException(status_code=401, detail="WeChat login failed: no openid returned")

    # Find existing user by openid
    user = db.query(User).filter(User.wechat_openid == openid).first()
    is_new = False

    if not user:
        # Create new user
        # Try unionid match first
        if unionid:
            user = db.query(User).filter(User.wechat_unionid == unionid).first()

        if not user:
            user = User(
                username=f"wx_{openid[:16]}",
                password_hash="",  # WeChat users have no password
                display_name=f"微信用户{openid[-6:]}",
                wechat_openid=openid,
                wechat_unionid=unionid,
                auth_source="wechat",
            )
            db.add(user)
            db.flush()
            is_new = True
        else:
            # Link wechat_openid to existing user (found by unionid)
            user.wechat_openid = openid
            if unionid:
                user.wechat_unionid = unionid
            user.auth_source = "wechat"

    # Update last login
    user.last_login_at = datetime.utcnow()
    db.commit()
    db.refresh(user)

    # Create JWT access token
    token = create_access_token(user.id, user.username)

    return WechatLoginResponse(
        access_token=token,
        user_id=user.id,
        display_name=user.display_name or user.username,
        is_new_user=is_new,
    )
