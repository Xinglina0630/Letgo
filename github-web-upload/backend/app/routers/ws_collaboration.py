"""
WebSocket endpoint for real-time collaboration notifications.

Single-instance, in-process broadcast. No Redis needed.
Extension point: replace ConnectionManager with Redis Pub/Sub for multi-instance.

Architecture:
- POST /api/ws/ticket -> get short-lived socket ticket
- WS /ws/projects/{project_id}?ticket=... -> connect and receive events
"""

import asyncio
import json
import secrets
import time
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.services.permissions import check_project_member

router = APIRouter(tags=["websocket"])

# In-memory ticket store (per-instance, not persistent)
_tickets: dict[str, dict] = {}  # ticket -> {user_id, project_id, expires_at}

# In-memory connection pool
_active_connections: dict[str, list[WebSocket]] = {}  # project_id -> [ws, ...]

TICKET_TTL_S = 30
TICKET_CLEANUP_INTERVAL = 60


# ====================================================================
# Ticket issuance
# ====================================================================

@router.post("/api/ws/ticket")
def get_socket_ticket(
    project_id: str = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a short-lived ticket for WebSocket connection."""
    # Verify user is project member
    check_project_member(db, project_id, user.id)

    # Generate ticket
    ticket = secrets.token_urlsafe(32)
    _tickets[ticket] = {
        "user_id": user.id,
        "project_id": project_id,
        "expires_at": time.time() + TICKET_TTL_S,
    }

    # Cleanup expired tickets periodically
    _cleanup_expired_tickets()

    return {"ticket": ticket, "expires_in_seconds": TICKET_TTL_S}


# ====================================================================
# WebSocket connection
# ====================================================================

@router.websocket("/ws/projects/{project_id}")
async def project_websocket(
    websocket: WebSocket,
    project_id: str,
    ticket: str = Query(...),
):
    """
    WebSocket for real-time project collaboration events.

    Messages received from server:
    {
      "type": "event",
      "event": {
        "event_id": "...", "event_type": "...", "actor": {...},
        "entity_id": "...", "new_version": 1, "occurred_at": "..."
      }
    }

    Messages sent by client:
    {"type": "ping"}
    Server responds: {"type": "pong"}
    """
    # Validate ticket
    ticket_data = _tickets.pop(ticket, None)
    if not ticket_data:
        await websocket.close(code=4001, reason="Invalid or expired ticket")
        return

    if ticket_data["expires_at"] < time.time():
        await websocket.close(code=4001, reason="Ticket expired")
        return

    if ticket_data["project_id"] != project_id:
        await websocket.close(code=4003, reason="Ticket not for this project")
        return

    user_id = ticket_data["user_id"]

    # Accept connection
    await websocket.accept()

    # Register connection
    if project_id not in _active_connections:
        _active_connections[project_id] = []
    _active_connections[project_id].append(websocket)

    try:
        while True:
            # Wait for client messages (pings mainly)
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=120)
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                # Send heartbeat
                try:
                    await websocket.send_json({"type": "heartbeat"})
                except Exception:
                    break
            except WebSocketDisconnect:
                break
            except Exception:
                break
    finally:
        # Cleanup
        if project_id in _active_connections:
            try:
                _active_connections[project_id].remove(websocket)
            except ValueError:
                pass


# ====================================================================
# Broadcast helper (called by other routers/services)
# ====================================================================

async def broadcast_project_event(project_id: str, event_data: dict):
    """
    Broadcast an event to all active WebSocket connections for a project.

    Args:
        project_id: The project to broadcast to
        event_data: Event dict with event_type, actor, entity_id, etc.
    """
    connections = _active_connections.get(project_id, [])
    if not connections:
        return

    message = {
        "type": "event",
        "event": {
            "event_id": event_data.get("event_id", ""),
            "project_id": project_id,
            "actor": event_data.get("actor", {}),
            "event_type": event_data.get("event_type", ""),
            "entity_id": event_data.get("entity_id", ""),
            "entity_type": event_data.get("entity_type", ""),
            "new_version": event_data.get("new_version"),
            "summary": event_data.get("summary", ""),
            "occurred_at": datetime.utcnow().isoformat(),
        },
    }

    disconnected = []
    for ws in connections:
        try:
            await ws.send_json(message)
        except Exception:
            disconnected.append(ws)

    for ws in disconnected:
        try:
            connections.remove(ws)
        except ValueError:
            pass


# ====================================================================
# Internal helpers
# ====================================================================

def _cleanup_expired_tickets():
    """Remove expired tickets from the in-memory store."""
    now = time.time()
    expired = [t for t, d in _tickets.items() if d["expires_at"] < now]
    for t in expired:
        _tickets.pop(t, None)
