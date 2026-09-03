from pydantic_settings import BaseSettings
from typing import List
from pathlib import Path
from urllib.parse import quote_plus
from pydantic import model_validator

# Compute absolute .env path relative to this config file
_CONFIG_DIR = Path(__file__).resolve().parent.parent  # backend/
_ENV_FILE = str(_CONFIG_DIR / ".env")


class Settings(BaseSettings):
    # ---- Application ----
    APP_ENV: str = "development"  # development | production
    APP_NAME: str = "Travel Planner API"
    DEBUG: bool = False

    # ---- Database ----
    DATABASE_URL: str = "sqlite:///./travel_planner.db"
    MYSQL_ADDRESS: str = ""
    MYSQL_HOST: str = ""
    MYSQL_PORT: int = 3306
    MYSQL_USERNAME: str = ""
    MYSQL_USER: str = ""
    MYSQL_PASSWORD: str = ""
    MYSQL_DATABASE: str = "flask_demo"

    # ---- Auth ----
    AUTH_SECRET_KEY: str = ""
    AUTH_COOKIE_SECURE: bool = False
    AUTH_TOKEN_EXPIRE_MINUTES: int = 1440

    # ---- CORS ----
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # ---- External APIs ----
    AMAP_API_KEY: str = ""
    POPULAR_PLACES_SEED_TOKEN: str = ""

    # ---- WeChat Mini Program ----
    WECHAT_MINIPROGRAM_APP_ID: str = ""
    WECHAT_MINIPROGRAM_APP_SECRET: str = ""
    WECHAT_LOGIN_ENABLED: bool = True
    WECHAT_AUTH_MOCK: bool = False

    class Config:
        env_file = _ENV_FILE
        extra = "allow"

    @model_validator(mode="after")
    def build_cloud_mysql_url(self):
        """Build a safely escaped PyMySQL URL from CloudRun environment variables."""
        if self.DATABASE_URL != "sqlite:///./travel_planner.db":
            return self

        host = self.MYSQL_HOST.strip()
        port = self.MYSQL_PORT
        if not host and self.MYSQL_ADDRESS:
            address = self.MYSQL_ADDRESS.strip()
            if ":" in address:
                host, raw_port = address.rsplit(":", 1)
                if raw_port.isdigit():
                    port = int(raw_port)
            else:
                host = address

        username = (self.MYSQL_USERNAME or self.MYSQL_USER).strip()
        if host and username and self.MYSQL_PASSWORD:
            self.DATABASE_URL = (
                f"mysql+pymysql://{quote_plus(username)}:{quote_plus(self.MYSQL_PASSWORD)}"
                f"@{host}:{port}/{self.MYSQL_DATABASE}?charset=utf8mb4"
            )
        return self

    @property
    def cors_origin_list(self) -> List[str]:
        if not self.CORS_ORIGINS:
            return []
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


settings = Settings()
