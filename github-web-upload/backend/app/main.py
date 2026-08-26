from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.config import settings
from app.database import init_db
from app.routers import flights, places, itinerary, routes, amap_routes, flight_compare, ocr, auth
from app.routers.wechat_auth import router as wechat_router
from app.routers.projects import router as projects_router
from app.routers.invites import router as invites_router
from app.routers.ws_collaboration import router as ws_router
from app.routers.custom_tags import router as custom_tags_router, project_share_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create tables; Shutdown: clean up."""
    # Only use create_all for development convenience
    # Production must use Alembic migrations
    if settings.APP_ENV == "development":
        init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — production-safe configuration
if settings.APP_ENV == "development":
    # Dev mode: allow localhost origins with credentials
    origins = settings.cors_origin_list or ["http://localhost:3000", "http://127.0.0.1:3000"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    # Production: only allowed origins from env var
    origins = settings.cors_origin_list
    if not origins:
        raise RuntimeError("CORS_ORIGINS must be set in production")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Routers
app.include_router(flights.router)
app.include_router(places.router)
app.include_router(itinerary.router)
app.include_router(itinerary._legacy_router)  # backward compatibility for /api/itinerary
app.include_router(routes.router)
app.include_router(amap_routes.router)
app.include_router(flight_compare.router)
app.include_router(ocr.router)
app.include_router(auth.router)
app.include_router(wechat_router)
app.include_router(projects_router)
app.include_router(invites_router)
app.include_router(ws_router)
app.include_router(custom_tags_router)
app.include_router(project_share_router)

# Static files — avatars, uploads
uploads_dir = Path(__file__).resolve().parent.parent / "uploads"
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")


@app.get("/api/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME}
