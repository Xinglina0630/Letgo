"""Authentication service — password hashing, JWT, user CRUD."""

from datetime import datetime, timedelta
from typing import Optional

from passlib.context import CryptContext
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User

# Password hashing with bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
SECRET_KEY = None
ALGORITHM = "HS256"


def _get_secret_key() -> str:
    """Get or validate the secret key."""
    global SECRET_KEY
    if SECRET_KEY is not None:
        return SECRET_KEY

    key = settings.AUTH_SECRET_KEY
    if settings.is_production:
        if not key:
            raise RuntimeError(
                "AUTH_SECRET_KEY is required in production. "
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        if len(key) < 32:
            raise RuntimeError("AUTH_SECRET_KEY must be at least 32 characters in production")
    else:
        # Development default — explicitly labeled as unsafe for production
        if not key:
            key = "dev-secret-key-change-in-production-do-not-use-in-prod-32chars"
            print("WARNING: Using default dev AUTH_SECRET_KEY. Set AUTH_SECRET_KEY for production.")

    SECRET_KEY = key
    return SECRET_KEY


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: str, username: str) -> str:
    """Create JWT access token."""
    expire = datetime.utcnow() + timedelta(minutes=settings.AUTH_TOKEN_EXPIRE_MINUTES)
    to_encode = {
        "sub": user_id,
        "username": username,
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(to_encode, _get_secret_key(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate JWT token. Returns payload or None."""
    try:
        payload = jwt.decode(token, _get_secret_key(), algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()


def create_user(db: Session, username: str, password: str, display_name: str = "") -> User:
    """Create a new user. Raises ValueError on duplicate username."""
    if get_user_by_username(db, username):
        raise ValueError(f"用户名 '{username}' 已被占用")

    user = User(
        username=username,
        password_hash=hash_password(password),
        display_name=display_name or username,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """Verify credentials and return user or None."""
    user = get_user_by_username(db, username)
    if not user:
        return None
    if not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
