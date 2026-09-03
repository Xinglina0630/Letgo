"""Flight comparison API — sessions, quotes, paste parsing, aggregation."""

import re
from datetime import date as date_type, datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.flight_compare import (
    FlightSearchSession, FlightCandidate, PlatformFlightQuote,
)
from app.schemas.flight_compare import (
    SessionCreate, SessionOut, SessionDetail,
    QuoteCreate, QuoteOut,
    PasteParseRequest, PasteParseResult,
    AggregatedRow,
)
from app.routers.auth import get_current_user, get_optional_user
from app.models.user import User

router = APIRouter(prefix="/api/flight-compare", tags=["flight-compare"])

# ---- Validation constants ----
VALID_CURRENCIES = {"CNY", "USD", "EUR", "JPY", "KRW", "HKD", "TWD", "SGD"}
VALID_SOURCES = {"manual", "paste", "api", "mock", "amap", "fallback", "external_api", "user_manual"}
VALID_CABINS = {"economy", "premium_economy", "business", "first"}
VALID_MODES = {"compare", "aggregate", "specific"}
MIN_FLIGHT_PRICE = 1
MAX_FLIGHT_PRICE = 999999
MAX_PASSENGERS = 9
MAX_PLATFORM_LEN = 100


def _validate_quote_data(data: QuoteCreate) -> None:
    """Validate quote fields before DB write."""
    if data.price <= MIN_FLIGHT_PRICE:
        raise HTTPException(status_code=422, detail=f"价格必须大于 {MIN_FLIGHT_PRICE}")
    if data.price > MAX_FLIGHT_PRICE:
        raise HTTPException(status_code=422, detail=f"价格不能超过 {MAX_FLIGHT_PRICE}")
    if data.currency not in VALID_CURRENCIES:
        raise HTTPException(status_code=422, detail=f"不支持的货币类型: {data.currency}")
    if data.source not in VALID_SOURCES:
        raise HTTPException(status_code=422, detail=f"不支持的来源类型: {data.source}")
    if data.cabin not in VALID_CABINS:
        raise HTTPException(status_code=422, detail=f"不支持的舱位类型: {data.cabin}")
    if len(data.platform) > MAX_PLATFORM_LEN:
        raise HTTPException(status_code=422, detail=f"平台名称过长 (最多 {MAX_PLATFORM_LEN} 字符)")


def _validate_date(date_str: str) -> date_type:
    """Parse and validate date string, raise 422 on invalid."""
    try:
        return date_type.fromisoformat(date_str)
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail=f"无效日期格式: {date_str}，请使用 YYYY-MM-DD")


def _validate_passengers(n: int) -> int:
    if n < 1 or n > MAX_PASSENGERS:
        raise HTTPException(status_code=422, detail=f"乘客数必须在 1-{MAX_PASSENGERS} 之间")
    return n


# ---- Session CRUD ----
@router.post("/sessions", response_model=SessionOut, status_code=201)
def create_session(
    data: SessionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        dep_date = _validate_date(data.departure_date)
    except HTTPException:
        raise
    passengers = _validate_passengers(data.passengers)
    if data.mode not in VALID_MODES:
        raise HTTPException(status_code=422, detail=f"不支持的模式: {data.mode}")
    if data.cabin not in VALID_CABINS:
        raise HTTPException(status_code=422, detail=f"不支持的舱位: {data.cabin}")

    try:
        s = FlightSearchSession(
            user_id=user.id,
            name=data.name or f"{data.departure_city}→{data.arrival_city} {data.departure_date}",
            departure_city=data.departure_city, arrival_city=data.arrival_city,
            departure_date=dep_date,
            passengers=passengers, cabin=data.cabin, mode=data.mode,
            specific_flight_number=data.specific_flight_number,
        )
        db.add(s); db.commit(); db.refresh(s)
        return SessionOut.from_orm_obj(s)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="创建会话失败")


@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List sessions for the current user only."""
    objs = (
        db.query(FlightSearchSession)
        .filter(FlightSearchSession.user_id == user.id)
        .order_by(FlightSearchSession.created_at.desc())
        .all()
    )
    return [SessionOut.from_orm_obj(o) for o in objs]


@router.get("/sessions/{sid}", response_model=SessionDetail)
def get_session(
    sid: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    s = db.query(FlightSearchSession).filter(FlightSearchSession.id == sid).first()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    # Verify ownership
    if s.user_id and s.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    all_quotes = db.query(PlatformFlightQuote).filter(PlatformFlightQuote.session_id == sid).all()
    rows: dict[str, dict] = {}

    for q in all_quotes:
        nk = _normalize_key(q.flight_number, q.airline_name, q.departure_time, q.arrival_time,
                            q.departure_airport, q.arrival_airport)
        if nk not in rows:
            rows[nk] = {
                "flight_number": q.flight_number or "", "airline_name": q.airline_name or "",
                "departure_time": q.departure_time or "", "arrival_time": q.arrival_time or "",
                "departure_airport": q.departure_airport or "", "arrival_airport": q.arrival_airport or "",
                "duration_minutes": 0, "stops": 0, "platform_prices": {}, "candidate_id": q.candidate_id or "",
            }
        rows[nk]["platform_prices"][q.platform_name or q.platform] = q.price

    aggregated = []
    for nk, r in rows.items():
        prices = [p for p in r["platform_prices"].values() if p > 0]
        lowest = min(prices) if prices else None
        lp = ""
        if lowest:
            for plat, pr in r["platform_prices"].items():
                if pr == lowest: lp = plat; break
        aggregated.append(AggregatedRow(
            flight_number=r["flight_number"], airline_name=r["airline_name"],
            departure_time=r["departure_time"], arrival_time=r["arrival_time"],
            departure_airport=r["departure_airport"], arrival_airport=r["arrival_airport"],
            duration_minutes=r["duration_minutes"], stops=r["stops"],
            platform_prices=r["platform_prices"], lowest_price=lowest, lowest_platform=lp,
            candidate_id=r["candidate_id"],
        ))

    aggregated.sort(key=lambda r: r.lowest_price if r.lowest_price else float("inf"))
    return SessionDetail(
        session=SessionOut.from_orm_obj(s),
        candidates=aggregated,
        quote_count=len(all_quotes),
    )


# ---- Quote CRUD ----
def _serialize_quote(q) -> dict:
    return {
        "id": q.id, "session_id": q.session_id, "candidate_id": q.candidate_id,
        "platform": q.platform, "platform_name": q.platform_name or "",
        "flight_number": q.flight_number or "", "airline_name": q.airline_name or "",
        "departure_time": q.departure_time or "", "arrival_time": q.arrival_time or "",
        "departure_airport": q.departure_airport or "", "arrival_airport": q.arrival_airport or "",
        "price": q.price, "currency": q.currency or "CNY", "cabin": q.cabin or "economy",
        "baggage": q.baggage or "", "refund_policy": q.refund_policy or "",
        "source": q.source or "manual",
        "captured_at": q.captured_at.isoformat() if q.captured_at else None,
        "created_at": q.created_at.isoformat() if q.created_at else None,
    }


@router.post("/quotes", status_code=201)
def create_quote(
    data: QuoteCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _validate_quote_data(data)
    # Verify session exists and belongs to user
    session = db.query(FlightSearchSession).filter(FlightSearchSession.id == data.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="关联的搜索会话不存在")
    if session.user_id and session.user_id != user.id:
        raise HTTPException(status_code=404, detail="关联的搜索会话不存在")
    try:
        q = PlatformFlightQuote(**data.model_dump())
        db.add(q); db.commit(); db.refresh(q)
        return _serialize_quote(q)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="保存报价失败")


@router.get("/sessions/{sid}/quotes", response_model=list[QuoteOut])
def list_quotes(
    sid: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Verify session exists and belongs to user
    s = db.query(FlightSearchSession).filter(FlightSearchSession.id == sid).first()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    if s.user_id and s.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    return db.query(PlatformFlightQuote).filter(PlatformFlightQuote.session_id == sid).all()


@router.delete("/quotes/{qid}")
def delete_quote(
    qid: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Verify quote exists, then check session ownership
    q = db.query(PlatformFlightQuote).filter(PlatformFlightQuote.id == qid).first()
    if not q:
        raise HTTPException(status_code=404, detail="报价不存在")
    # Verify the quote's session belongs to the user
    session = db.query(FlightSearchSession).filter(
        FlightSearchSession.id == q.session_id,
    ).first()
    if session and session.user_id and session.user_id != user.id:
        raise HTTPException(status_code=404, detail="报价不存在")
    try:
        db.delete(q); db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="删除报价失败")
    return {"ok": True}


# ---- Paste Parsing ----
def _normalize_key(fn: str, an: str, dt: str, at: str, da: str, aa: str) -> str:
    """Normalize flight identity for merging."""
    if fn and fn.strip():
        return f"FN:{fn.strip().upper()}"
    return f"TK:{an.strip()}|{dt.strip()}|{at.strip()}|{da.strip()}|{aa.strip()}"

def _parse_price(text: str) -> float:
    """Extract price from text like '¥1,280' or '1280元' or 'CNY1280'."""
    text = text.replace(",", "").replace("，", "")
    m = re.search(r'(?:¥|￥|CNY|cny|元)?\s*(\d+(?:\.\d{1,2})?)', text)
    return float(m.group(1)) if m else 0.0

def _parse_time(text: str) -> str:
    """Extract time like '08:30' or '14:00'."""
    m = re.search(r'(\d{1,2}:\d{2})', text)
    return m.group(1) if m else ""

def _parse_flight_number(text: str) -> str:
    m = re.search(r'([A-Za-z]{2}\d{3,5})', text)
    return m.group(1).upper() if m else ""

def _parse_airline(text: str) -> str:
    airlines = ["中国国航", "东方航空", "南方航空", "海南航空", "四川航空", "深圳航空", "厦门航空",
                "上海航空", "春秋航空", "天津航空", "吉祥航空", "国航", "东航", "南航", "海航"]
    for a in airlines:
        if a in text: return a
    return ""


@router.post("/parse-paste", response_model=PasteParseResult)
def parse_paste(
    data: PasteParseRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Parse structured text paste from a platform search result and save to DB."""
    # Validate session exists and belongs to user
    session = db.query(FlightSearchSession).filter(FlightSearchSession.id == data.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="关联的搜索会话不存在")
    if session.user_id and session.user_id != user.id:
        raise HTTPException(status_code=404, detail="关联的搜索会话不存在")

    if data.platform not in VALID_SOURCES and len(data.platform) > MAX_PLATFORM_LEN:
        raise HTTPException(status_code=422, detail=f"平台名称过长 (最多 {MAX_PLATFORM_LEN} 字符)")

    lines = [l.strip() for l in data.text.split("\n") if l.strip()]
    quotes = []
    current: dict = {}

    for line in lines:
        fn = _parse_flight_number(line)
        if fn and not current.get("flight_number"):
            current["flight_number"] = fn

        an = _parse_airline(line)
        if an and not current.get("airline_name"):
            current["airline_name"] = an

        tm = _parse_time(line)
        if tm:
            if not current.get("departure_time"):
                current["departure_time"] = tm
            elif not current.get("arrival_time") and tm != current.get("departure_time"):
                current["arrival_time"] = tm

        price = _parse_price(line)
        if price > 0:
            existing_price = current.get("price", 0)
            if price > existing_price or existing_price == 0:
                current["price"] = price

        codes = re.findall(r'\b([A-Z]{3})\b', line)
        if codes:
            if not current.get("departure_airport") and len(codes) >= 1:
                current["departure_airport"] = codes[0]
            if not current.get("arrival_airport") and len(codes) >= 2:
                current["arrival_airport"] = codes[1]

        if current.get("price", 0) > 0 and (current.get("flight_number") or current.get("departure_time")):
            quotes.append(QuoteCreate(
                session_id=data.session_id,
                platform=data.platform, platform_name=data.platform_name or data.platform,
                flight_number=current.get("flight_number", ""),
                airline_name=current.get("airline_name", ""),
                departure_time=current.get("departure_time", ""),
                arrival_time=current.get("arrival_time", ""),
                departure_airport=current.get("departure_airport", ""),
                arrival_airport=current.get("arrival_airport", ""),
                price=current.get("price", 0),
                currency="CNY", cabin="economy",
                source="paste",
            ))
            current = {}

    if current.get("price", 0) > 0:
        quotes.append(QuoteCreate(
            session_id=data.session_id,
            platform=data.platform, platform_name=data.platform_name or data.platform,
            flight_number=current.get("flight_number", ""),
            airline_name=current.get("airline_name", ""),
            departure_time=current.get("departure_time", ""),
            arrival_time=current.get("arrival_time", ""),
            departure_airport=current.get("departure_airport", ""),
            arrival_airport=current.get("arrival_airport", ""),
            price=current.get("price", 0),
            currency="CNY", cabin="economy",
            source="paste",
        ))

    # Save to DB using DI session
    saved_count = 0
    try:
        for qc in quotes:
            _validate_quote_data(qc)
            q = PlatformFlightQuote(**qc.model_dump())
            db.add(q)
            saved_count += 1
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="保存解析结果失败")

    return PasteParseResult(quotes=quotes)


@router.delete("/sessions/{sid}")
def delete_session(
    sid: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    s = db.query(FlightSearchSession).filter(FlightSearchSession.id == sid).first()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    if s.user_id and s.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        db.query(PlatformFlightQuote).filter(PlatformFlightQuote.session_id == sid).delete()
        db.query(FlightCandidate).filter(FlightCandidate.session_id == sid).delete()
        db.delete(s); db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="删除会话失败")
    return {"ok": True}
