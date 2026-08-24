"""
PaddleOCR-based flight screenshot recognition service.

Returns structured flight info with bounding-box coordinates,
confidence scores, and card-level grouping.
"""

from __future__ import annotations

import json
import math
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

@dataclass
class OcrBox:
    text: str
    box: list[list[float]]  # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
    score: float
    center_y: float = 0.0
    center_x: float = 0.0
    x_min: float = 0.0
    x_max: float = 0.0
    y_min: float = 0.0
    y_max: float = 0.0

    def __post_init__(self):
        xs = [p[0] for p in self.box]
        ys = [p[1] for p in self.box]
        self.center_y = float(np.mean(ys))
        self.center_x = float(np.mean(xs))
        self.x_min = float(min(xs))
        self.x_max = float(max(xs))
        self.y_min = float(min(ys))
        self.y_max = float(max(ys))


@dataclass
class FlightCard:
    """A group of OCR boxes that belong to one flight listing."""
    boxes: list[OcrBox] = field(default_factory=list)
    y_center: float = 0.0
    y_min: float = 0.0
    y_max: float = 0.0

    @property
    def text(self) -> str:
        return "\n".join(b.text for b in self.boxes)


@dataclass
class ParsedFlightItem:
    flight_number: str = ""
    airline_name: str = ""
    departure_time: str = ""
    arrival_time: str = ""
    departure_airport: str = ""
    arrival_airport: str = ""
    price: int = 0
    cabin: str = ""
    confidence: float = 0.0
    source_file: str = ""
    source_blocks: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class OcrResult:
    platform: str
    items: list[ParsedFlightItem] = field(default_factory=list)
    raw_ocr: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AIRLINE_CODES = {
    "CA", "MU", "CZ", "HU", "3U", "ZH", "MF", "GS", "FM", "9C",
    "HO", "KN", "NS", "PN", "SC", "GJ", "TV", "EU", "QW", "BK",
    "DR", "JR", "GT", "8L", "RY", "AQ", "Y8", "DZ", "G5",
}

MIN_FLIGHT_PRICE = 80
MAX_FLIGHT_PRICE = 50000
LOW_PRICE_THRESHOLD = 300  # below this = likely coupon/upgrade

# ---- Platform right-side price x-coordinate thresholds (normalized 0-1) ----
# The price column is typically in the rightmost 25-35% of a flight listing card image
PRICE_X_RATIO_MIN = 0.60  # price text center_x / card_width must be > this

# ---- Excluded price contexts ----
EXCLUDE_PRICE_PATTERNS = [
    re.compile(r"已减\s*[¥Y]?\s*\d+"),
    re.compile(r"优惠\s*[¥Y]?\s*\d+"),
    re.compile(r"升舱\s*[+＋]\s*\d+"),
    re.compile(r"优惠券"),
    re.compile(r"抹零卡"),
    re.compile(r"买贵赔"),
    re.compile(r"接送机"),
    re.compile(r"酒店券"),
    re.compile(r"[¥Y]\s*1~9"),
    re.compile(r"省\s*[¥Y]\d+"),
    re.compile(r"推荐.*[¥Y#]\d+"),
    re.compile(r"低\s*于\s*[#¥Y]\d+"),
]


def is_reasonable_price(price: float) -> bool:
    return MIN_FLIGHT_PRICE <= price <= MAX_FLIGHT_PRICE


def is_low_confidence_price(price: float) -> bool:
    return 0 < price < LOW_PRICE_THRESHOLD


# ---------------------------------------------------------------------------
# PaddleOCR wrapper — lazy init
# ---------------------------------------------------------------------------

_paddle_ocr = None


def _get_ocr():
    global _paddle_ocr
    if _paddle_ocr is None:
        try:
            from paddleocr import PaddleOCR
            _paddle_ocr = PaddleOCR(lang="ch", use_angle_cls=True)
        except Exception as e:
            raise RuntimeError(f"PaddleOCR 初始化失败: {e}") from e
    return _paddle_ocr


# ---------------------------------------------------------------------------
# Main OCR pipeline
# ---------------------------------------------------------------------------

def process_screenshots(
    files: list[tuple[str, bytes]],
    platform: str,
) -> OcrResult:
    """
    Run PaddleOCR on a batch of flight screenshots and return structured results.

    Args:
        files: list of (filename, file_bytes)
        platform: one of ctrip/tongcheng/qunar/zhixing/feizhu

    Returns:
        OcrResult with items and raw_ocr
    """
    ocr = _get_ocr()
    result = OcrResult(platform=platform)
    all_boxes: list[tuple[str, list[OcrBox]]] = []

    # ---- Step 1: OCR each image ----
    for fname, fbytes in files:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(fbytes)
            tmp_path = tmp.name

        try:
            ocr_output = ocr.ocr(tmp_path, cls=True)
            boxes = _parse_ocr_output(ocr_output, fname)
            all_boxes.append((fname, boxes))
            result.raw_ocr.extend([
                {"text": b.text, "box": b.box, "score": b.score}
                for b in boxes
            ])
        except Exception as e:
            result.errors.append(f"{fname}: {e}")
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    if not all_boxes:
        return result

    # ---- Step 2: Group boxes into flight cards by y-coordinate proximity ----
    all_cards: list[tuple[str, list[FlightCard]]] = []
    for fname, boxes in all_boxes:
        cards = _group_into_cards(boxes)
        all_cards.append((fname, cards))

    # ---- Step 3: Parse each card into structured flight info ----
    for fname, cards in all_cards:
        for card in cards:
            item = _parse_card(card, platform, fname)
            if item:
                result.items.append(item)

    return result


# ---------------------------------------------------------------------------
# OCR output parsing
# ---------------------------------------------------------------------------

def _parse_ocr_output(ocr_output: list | None, fname: str) -> list[OcrBox]:
    """Convert PaddleOCR output to OcrBox list."""
    boxes: list[OcrBox] = []
    if not ocr_output:
        return boxes
    for row in ocr_output:
        if not row:
            continue
        for detection in row:
            try:
                bbox, (text, score) = detection
                box = [[float(p[0]), float(p[1])] for p in bbox]
                boxes.append(OcrBox(text=text, box=box, score=float(score)))
            except (ValueError, TypeError):
                continue
    # Sort top-to-bottom, left-to-right
    boxes.sort(key=lambda b: (b.y_min, b.x_min))
    return boxes


# ---------------------------------------------------------------------------
# Card grouping by y-coordinate proximity
# ---------------------------------------------------------------------------

def _group_into_cards(boxes: list[OcrBox], y_gap_ratio: float = 0.025) -> list[FlightCard]:
    """
    Group OCR boxes into flight cards based on vertical proximity.
    A new card starts when the y-gap between consecutive text lines exceeds
    y_gap_ratio * image_height.
    """
    if not boxes:
        return []

    # Estimate image height from max y coordinate
    max_y = max(b.y_max for b in boxes)
    gap_threshold = max_y * y_gap_ratio

    cards: list[FlightCard] = []
    current = FlightCard()
    current.boxes.append(boxes[0])

    for i in range(1, len(boxes)):
        prev = boxes[i - 1]
        curr = boxes[i]
        gap = curr.y_min - prev.y_max

        if gap > gap_threshold * 3:  # large gap = new card
            if len(current.boxes) >= 2:
                cards.append(current)
            current = FlightCard()
        current.boxes.append(curr)

    if len(current.boxes) >= 2:
        cards.append(current)

    # Compute card y bounds
    for card in cards:
        card.y_min = min(b.y_min for b in card.boxes)
        card.y_max = max(b.y_max for b in card.boxes)
        card.y_center = (card.y_min + card.y_max) / 2

    return cards


# ---------------------------------------------------------------------------
# Card-level parsing
# ---------------------------------------------------------------------------

def _parse_card(card: FlightCard, platform: str, fname: str) -> ParsedFlightItem | None:
    """Parse one flight card into structured data."""
    boxes = card.boxes
    card_width = max(b.x_max for b in boxes) - min(b.x_min for b in boxes)
    if card_width <= 0:
        card_width = 1

    item = ParsedFlightItem(source_file=fname)

    # ---- Flight number ----
    for b in boxes:
        fn = _extract_flight_number(b.text)
        if fn:
            item.flight_number = fn
            break

    if not item.flight_number:
        return None  # not a flight card

    # ---- Times ----
    times = _extract_times_from_boxes(boxes)
    if len(times) >= 2:
        item.departure_time = times[0]
        item.arrival_time = times[1]

    # ---- Price: right-side priority ----
    price_boxes = [b for b in boxes if b.center_x / card_width > PRICE_X_RATIO_MIN]
    price_boxes.sort(key=lambda b: b.center_y)  # top to bottom

    for b in price_boxes:
        p = _extract_price(b.text)
        if is_reasonable_price(p) and not is_low_confidence_price(p):
            item.price = int(p)
            break

    # Fallback: any price in the card
    if not item.price:
        for b in boxes:
            p = _extract_price(b.text)
            if is_reasonable_price(p):
                item.price = int(p)
                break

    # ---- Airline name ----
    for b in boxes:
        an = _extract_airline_name(b.text)
        if an:
            item.airline_name = an
            break

    # ---- Airports ----
    airports = _extract_airports_from_boxes(boxes)
    if len(airports) >= 2:
        item.departure_airport = airports[0]
        item.arrival_airport = airports[1]

    # ---- Cabin ----
    for b in boxes:
        cabin = _extract_cabin(b.text)
        if cabin:
            item.cabin = cabin
            break

    # ---- Confidence ----
    conf_parts = [
        1.0 if item.flight_number else 0.0,
        0.9 if item.departure_time and item.arrival_time else 0.0,
        0.85 if item.price >= LOW_PRICE_THRESHOLD else (0.5 if item.price > 0 else 0.0),
    ]
    item.confidence = round(sum(conf_parts) / len(conf_parts), 3)

    # ---- Warnings ----
    if item.price > 0 and item.price < LOW_PRICE_THRESHOLD:
        item.warnings.append(f"价格 ¥{item.price} 偏低，可能为优惠金额")
    if not item.departure_time:
        item.warnings.append("未提取到起飞时间")
    if not item.arrival_time:
        item.warnings.append("未提取到到达时间")

    # ---- Source blocks for UI review ----
    item.source_blocks = [
        {"text": b.text, "box": b.box, "score": round(b.score, 3)}
        for b in boxes
    ]

    return item


# ---------------------------------------------------------------------------
# Field extractors
# ---------------------------------------------------------------------------

FLIGHT_NUMBER_RE = re.compile(r"([A-Za-z]{2})\s*(\d{3,5})")

def _extract_flight_number(text: str) -> str:
    text = text.replace(" ", "").upper()
    m = FLIGHT_NUMBER_RE.search(text)
    if not m:
        return ""
    code = m.group(1)
    num = m.group(2)
    if code in AIRLINE_CODES:
        return f"{code}{num}"
    return ""

TIME_RE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")

def _extract_times_from_boxes(boxes: list[OcrBox]) -> list[str]:
    all_times: list[str] = []
    seen = set()
    for b in boxes:
        for m in TIME_RE.finditer(b.text):
            t = f"{m.group(1).zfill(2)}:{m.group(2)}"
            if t not in seen:
                seen.add(t)
                all_times.append(t)
    # Filter status bar times (phone time, typically 12:xx-23:xx appearing alone)
    if len(all_times) > 2:
        filtered = [t for t in all_times if not (12 <= int(t[:2]) <= 23 and all_times.count(t) == 1)]
        if filtered:
            all_times = filtered
    return sorted(all_times)


PRICE_RE = re.compile(r"[¥YyxX*#](\d{2,5})")
PRICE_MULTI_RE = re.compile(r"[¥YyxX*#](\d{2,5})[¥YyxX*#](\d{2,5})")

def _extract_price(text: str) -> float:
    clean = text.replace(",", "").replace(" ", "")

    # Exclude coupon/upgrade contexts
    for pat in EXCLUDE_PRICE_PATTERNS:
        if pat.search(clean):
            return 0

    # Multi-price: take second (discounted)
    mm = PRICE_MULTI_RE.search(clean)
    if mm:
        p = float(mm.group(2))
        if is_reasonable_price(p):
            return p

    # Single price
    for m in PRICE_RE.finditer(clean):
        p = float(m.group(1))
        if is_reasonable_price(p):
            return p

    return 0


AIRLINE_NAMES = {
    "中国国航": "中国国航", "国航": "中国国航",
    "东方航空": "东方航空", "东航": "东方航空",
    "南方航空": "南方航空", "南航": "南方航空",
    "海南航空": "海南航空", "海航": "海南航空",
    "四川航空": "四川航空", "川航": "四川航空",
    "深圳航空": "深圳航空", "深航": "深圳航空",
    "厦门航空": "厦门航空", "厦航": "厦门航空",
    "上海航空": "上海航空", "上航": "上海航空",
    "春秋航空": "春秋航空", "春秋": "春秋航空",
    "吉祥航空": "吉祥航空", "吉祥": "吉祥航空",
    "天津航空": "天津航空", "天航": "天津航空",
    "中联航": "中联航", "金鹏航空": "金鹏航空",
    "华夏航空": "华夏航空", "华夏": "华夏航空",
}

def _extract_airline_name(text: str) -> str:
    for key, name in AIRLINE_NAMES.items():
        if key in text:
            return name
    return ""


AIRPORT_NAMES = [
    "浦东T1", "浦东T2", "虹桥T1", "虹桥T2",
    "首都T1", "首都T2", "首都T3", "大兴",
    "白云T1", "白云T2", "宝安T3",
    "双流T1", "双流T2", "天府T1", "天府T2",
    "萧山T3", "江北T3", "天河T3", "咸阳T3",
    "禄口T2", "长水T1", "凤凰T1", "高崎T4", "黄花T2",
]

def _extract_airports_from_boxes(boxes: list[OcrBox]) -> list[str]:
    found: list[str] = []
    for b in boxes:
        for name in AIRPORT_NAMES:
            if name in b.text and name not in found:
                found.append(name)
    return found


CABIN_WORDS = ["经济舱", "商务舱", "头等舱", "超级经济舱", "公务舱", "明珠经济舱"]

def _extract_cabin(text: str) -> str:
    for kw in CABIN_WORDS:
        if kw in text:
            return kw
    return ""
