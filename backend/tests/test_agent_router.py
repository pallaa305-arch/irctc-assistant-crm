import pytest
from app.agents.router import AgentRouter, AgentResponse

@pytest.mark.asyncio
async def test_router_handles_train_search_hinglish():
    router = AgentRouter()
    resp = await router.handle_message(
        session_id="test_sess_web_1",
        user_message="Delhi se Jammu 25 September ki train check karo",
        channel="web"
    )
    assert isinstance(resp, AgentResponse)
    assert resp.text != ""
    assert resp.action_type in ("TRAIN_LIST", "STAGE_UPDATE")
    assert "trains" in resp.payload or "trains_count" in resp.payload

@pytest.mark.asyncio
async def test_router_handles_pnr_status():
    router = AgentRouter()
    resp = await router.handle_message(
        session_id="test_sess_web_2",
        user_message="Check PNR 2451234567",
        channel="web"
    )
    assert isinstance(resp, AgentResponse)
    assert "2451234567" in resp.text or resp.payload.get("pnr") == "2451234567"

@pytest.mark.asyncio
async def test_router_handles_fare_inquiry():
    router = AgentRouter()
    resp = await router.handle_message(
        session_id="test_sess_web_3",
        user_message="Calculate fare for 12952 class 3A 2 passengers",
        channel="web"
    )
    assert isinstance(resp, AgentResponse)
    assert resp.action_type == "FARE_BREAKDOWN"
    assert "total_fare" in resp.payload

@pytest.mark.asyncio
async def test_router_handles_greeting():
    router = AgentRouter()
    resp = await router.handle_message(
        session_id="test_sess_web_4",
        user_message="Hello, kaise ho?",
        channel="web"
    )
    assert isinstance(resp, AgentResponse)
    assert resp.text != ""
