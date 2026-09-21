import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_chat_post_endpoint():
    res = client.post("/api/chat", json={
        "session_id": "web_test_api",
        "message": "Hello assistant",
        "channel": "web"
    })
    assert res.status_code == 200
    data = res.json()
    assert "text" in data
    assert "action_type" in data
    assert "payload" in data

def test_chat_history_endpoint():
    # After posting, history should contain messages
    res = client.get("/api/chat/history/web_test_api")
    assert res.status_code == 200
    data = res.json()
    assert "history" in data
    assert len(data["history"]) >= 2

def test_chat_websocket_connection():
    with client.websocket_connect("/ws/chat/web_ws_test") as websocket:
        # Send a chat message over WebSocket
        websocket.send_json({
            "message": "Delhi se Jammu train check karo"
        })
        data = websocket.receive_json()
        assert "type" in data
        assert data["type"] in ("STAGE_UPDATE", "RESPONSE", "TRAINS_FOUND")
