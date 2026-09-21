"""
Chat REST & WebSocket Endpoints for Personal IRCTC Assistant.
Allows frontend web chat to communicate with the Unified Agent Router and receive real-time events.
"""
import json
import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel

from app.agents.router import agent_router, AgentResponse
from app.agents.event_bus import event_bus
from app.sessions.session_manager import session_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["AI Assistant Chat"])

class ChatRequest(BaseModel):
    session_id: str
    message: str
    channel: str = "web"
    user_id: Optional[str] = ""

@router.post("/api/chat")
async def handle_chat_message(req: ChatRequest):
    """
    Synchronous REST endpoint for conversational AI.
    """
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    resp = await agent_router.handle_message(
        session_id=req.session_id,
        user_message=req.message.strip(),
        channel=req.channel,
        user_id=req.user_id or ""
    )

    return {
        "text": resp.text,
        "action_type": resp.action_type,
        "payload": resp.payload,
        "session_state": resp.session_state
    }

@router.get("/api/chat/history/{session_id}")
async def get_chat_history(session_id: str):
    """
    Fetch message history for a given session.
    """
    history = session_manager.get_history(session_id)
    return {
        "session_id": session_id,
        "history": history
    }

@router.websocket("/ws/chat/{session_id}")
async def chat_websocket(websocket: WebSocket, session_id: str):
    """
    Bi-directional WebSocket for conversational chat and live IRCTC automation events.
    """
    await websocket.accept()

    async def event_listener(event: Dict[str, Any]):
        try:
            await websocket.send_json(event)
        except Exception:
            pass

    # Subscribe to real-time events for this session
    event_bus.subscribe(session_id, event_listener)

    try:
        # Initial greeting / connection established
        await websocket.send_json({
            "type": "STAGE_UPDATE",
            "data": {
                "stage": "CONNECTED",
                "message": "AI Assistant Connected. Ready for train booking."
            }
        })

        while True:
            raw_text = await websocket.receive_text()
            try:
                data = json.loads(raw_text)
                user_msg = data.get("message", "").strip()
            except Exception:
                user_msg = raw_text.strip()

            if user_msg:
                resp = await agent_router.handle_message(
                    session_id=session_id,
                    user_message=user_msg,
                    channel="web"
                )
                await websocket.send_json({
                    "type": "RESPONSE",
                    "data": {
                        "text": resp.text,
                        "action_type": resp.action_type,
                        "payload": resp.payload,
                        "session_state": resp.session_state
                    }
                })
    except WebSocketDisconnect:
        pass
    finally:
        event_bus.unsubscribe(session_id, event_listener)
