"""OCR API — PaddleOCR flight screenshot recognition with security controls."""

import imghdr
import threading
from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile, HTTPException, Request, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app.routers.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/ocr", tags=["ocr"])

# ---- Concurrency limiting (process-local, no Redis) ----
_ocr_semaphore = threading.Semaphore(settings.OCR_MAX_CONCURRENT)

# Allowed MIME types and extensions
ALLOWED_MIME_TYPES = {
    "image/png", "image/jpeg", "image/jpg", "image/webp", "image/bmp",
}
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
MAX_PIXELS = 100_000_000  # ~100 megapixels, prevent decompression bombs
MAX_TOTAL_REQUEST_SIZE = 60 * 1024 * 1024  # 60 MB total per request
VALID_PLATFORMS = {"ctrip", "tongcheng", "qunar", "zhixing", "feizhu", "other"}


def _validate_image(filename: str, content: bytes) -> None:
    """Validate image file: extension, MIME, and actual parseability."""
    import io
    from PIL import Image

    # Extension check
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {ext}，支持: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Content size check
    max_bytes = settings.OCR_MAX_FILE_SIZE_MB * 1024 * 1024
    if len(content) == 0:
        raise HTTPException(status_code=400, detail=f"{filename} 是空文件")
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"{filename} 文件过大 (最大 {settings.OCR_MAX_FILE_SIZE_MB}MB)",
        )

    # Actual image type check (don't trust extension or Content-Type header)
    img_type = imghdr.what(None, h=content[:32])
    if img_type not in ("png", "jpeg", "webp", "bmp"):
        raise HTTPException(
            status_code=400,
            detail=f"{filename} 不是有效的图片文件",
        )

    # Parse image to verify it's not corrupted and check dimensions
    try:
        img = Image.open(io.BytesIO(content))
        img.verify()
        # Re-open after verify
        img = Image.open(io.BytesIO(content))
        w, h = img.size
        if w <= 0 or h <= 0:
            raise HTTPException(status_code=400, detail=f"{filename} 图片尺寸异常")
        if w * h > MAX_PIXELS:
            raise HTTPException(
                status_code=400,
                detail=f"{filename} 图片像素过大 (最大约 10000x10000)",
            )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail=f"{filename} 图片无法解析或已损坏")


# OCR engine health — cached, does NOT trigger model init
_ocr_available: Optional[bool] = None


@router.get("/health")
async def ocr_health():
    """Check if PaddleOCR is available without triggering model load."""
    global _ocr_available
    if _ocr_available is not None:
        return {"status": "ok" if _ocr_available else "unavailable", "engine": "paddleocr"}

    try:
        import paddleocr  # noqa: F401
        _ocr_available = True
        return {"status": "ok", "engine": "paddleocr"}
    except ImportError:
        _ocr_available = False
        return {"status": "unavailable", "engine": "none", "detail": "PaddleOCR 未安装"}


@router.post("/flight-screenshots", response_model=dict)
async def ocr_flight_screenshots(
    request: Request,
    files: list[UploadFile] = File(...),
    platform: str = Form(default="ctrip"),
    departure_city: Optional[str] = Form(default=None),
    arrival_city: Optional[str] = Form(default=None),
    departure_date: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Run PaddleOCR on uploaded flight screenshots. Requires login.

    Security: max files, max file size, type validation, concurrency limiting.
    """
    # Check number of files
    if not files:
        raise HTTPException(status_code=400, detail="请上传至少一张截图")
    if len(files) > settings.OCR_MAX_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"一次最多上传 {settings.OCR_MAX_FILES} 张图片",
        )

    # Validate platform
    if platform not in VALID_PLATFORMS:
        raise HTTPException(
            status_code=400,
            detail=f"平台 {platform} 不支持，支持: {', '.join(sorted(VALID_PLATFORMS))}",
        )

    # Read and validate all files
    file_data: list[tuple[str, bytes]] = []
    total_size = 0
    for f in files:
        content = await f.read()
        total_size += len(content)
        if total_size > MAX_TOTAL_REQUEST_SIZE:
            raise HTTPException(status_code=400, detail="请求总大小超过限制 (60MB)")
        _validate_image(f.filename or "screenshot.png", content)
        file_data.append((f.filename or "screenshot.png", content))

    # Acquire concurrency semaphore
    acquired = _ocr_semaphore.acquire(blocking=False)
    if not acquired:
        raise HTTPException(
            status_code=503,
            detail="OCR 引擎正忙，请稍后重试。当前同时处理的任务数已达上限。",
        )

    try:
        from app.services.ocr_service import process_screenshots, OcrResult
        result: OcrResult = process_screenshots(file_data, platform)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail="OCR 引擎暂时不可用，请稍后重试")
    except Exception as e:
        # Log internally, return safe message to client
        import logging
        logging.getLogger("ocr").error(f"OCR processing error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="OCR 处理失败，请稍后重试")
    finally:
        _ocr_semaphore.release()

    return {
        "platform": result.platform,
        "items": [
            {
                "flight_number": item.flight_number,
                "airline_name": item.airline_name,
                "departure_time": item.departure_time,
                "arrival_time": item.arrival_time,
                "departure_airport": item.departure_airport,
                "arrival_airport": item.arrival_airport,
                "price": item.price,
                "cabin": item.cabin,
                "confidence": item.confidence,
                "source_file": item.source_file,
                "source_blocks": item.source_blocks,
                "warnings": item.warnings,
            }
            for item in result.items
        ],
        "raw_ocr": result.raw_ocr,
        "errors": result.errors,
    }
