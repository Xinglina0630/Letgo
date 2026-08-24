"""User model for authentication and data isolation."""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, LargeBinary
from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(200), default="")

    # WeChat fields
    wechat_openid = Column(String(100), unique=True, nullable=True)
    wechat_unionid = Column(String(100), nullable=True)
    wechat_display_name = Column(String(200), nullable=True)
    wechat_avatar_url = Column(String(500), nullable=True)
    avatar_content = Column(LargeBinary, nullable=True)
    avatar_content_type = Column(String(50), nullable=True)

    auth_source = Column(String(20), default="password")  # "password" | "wechat"
    last_login_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
