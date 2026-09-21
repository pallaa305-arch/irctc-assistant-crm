import pytest
from app.sessions.session_manager import SessionManager, SessionState

def test_session_creation_and_retrieval():
    mgr = SessionManager()
    session = mgr.get_or_create_session("web_test_1", channel="web", user_id="user_1")
    assert session.session_id == "web_test_1"
    assert session.channel == "web"
    assert session.current_step == "IDLE"

def test_session_state_updates():
    mgr = SessionManager()
    mgr.get_or_create_session("tg_123", channel="telegram", user_id="123")
    mgr.update_session("tg_123", current_step="SEARCHING", journey_data={"from_station": "NDLS", "to_station": "JAT"})
    session = mgr.get_session("tg_123")
    assert session.current_step == "SEARCHING"
    assert session.journey_data["from_station"] == "NDLS"

def test_session_message_history():
    mgr = SessionManager()
    mgr.get_or_create_session("s1", "web", "u1")
    mgr.add_message("s1", "user", "Book train from Delhi to Jaipur")
    mgr.add_message("s1", "assistant", "Searching trains...")
    history = mgr.get_history("s1")
    assert len(history) == 2
    assert history[0]["content"] == "Book train from Delhi to Jaipur"
    assert history[1]["content"] == "Searching trains..."
