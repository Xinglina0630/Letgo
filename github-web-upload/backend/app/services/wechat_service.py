"""
WeChat Mini Program login service.

Uses code2Session to exchange wx.login code for openid/session_key.
AppSecret MUST only live in backend environment variables.
"""

import httpx
from app.config import settings


WECHAT_CODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session"


async def code2session(code: str) -> dict:
    """
    Exchange wx.login code for openid, session_key, unionid.

    Returns dict with: openid, session_key, unionid (optional)
    Raises ValueError on failure.
    """
    app_id = settings.WECHAT_MINIPROGRAM_APP_ID
    app_secret = settings.WECHAT_MINIPROGRAM_APP_SECRET

    if not app_id or not app_secret:
        # Mock mode for development without real WeChat credentials
        if settings.WECHAT_AUTH_MOCK:
            return _mock_code2session(code)
        raise ValueError("WeChat AppID/Secret not configured")

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(WECHAT_CODE2SESSION_URL, params={
            "appid": app_id,
            "secret": app_secret,
            "js_code": code,
            "grant_type": "authorization_code",
        })
        data = resp.json()

    errcode = data.get("errcode", 0)
    if errcode != 0:
        errmsg = data.get("errmsg", "unknown error")
        raise ValueError(f"WeChat code2Session failed: {errmsg} (code={errcode})")

    return {
        "openid": data.get("openid", ""),
        "session_key": data.get("session_key", ""),
        "unionid": data.get("unionid", ""),
    }


def _mock_code2session(code: str) -> dict:
    """
    Development mock for WeChat login.
    Only enabled when WECHAT_AUTH_MOCK=true AND APP_ENV=development.
    """
    if settings.APP_ENV == "production":
        raise RuntimeError("WECHAT_AUTH_MOCK is forbidden in production")

    # Generate deterministic mock openid from code
    if not code or len(code) < 4:
        raise ValueError("Invalid WeChat login code")
    mock_openid = f"mock_openid_{code[:12]}"
    return {
        "openid": mock_openid,
        "session_key": "mock_session_key_do_not_log",
        "unionid": f"mock_unionid_{code[:8]}",
    }
