import pytest
from app.agents.router import agent_router
from app.notifications.telegram_channel_adapter import telegram_adapter
from app.sessions.session_manager import session_manager
from app.agents.event_bus import event_bus

@pytest.mark.asyncio
async def test_e2e_multi_channel_unified_agent():
    # 1. Test Web Channel Flow
    web_session_id = "web_e2e_test_session"
    resp_search = await agent_router.handle_message(
        session_id=web_session_id,
        user_message="Delhi to Mumbai tomorrow 3A",
        channel="web"
    )
    assert resp_search.action_type in ("TRAIN_LIST", "STAGE_UPDATE")
    assert "trains" in resp_search.payload

    # 2. Check Session State was preserved
    web_sess = session_manager.get_session(web_session_id)
    assert web_sess is not None
    assert len(web_sess.history) >= 2

    # 3. Test Fare Inquiry
    resp_fare = await agent_router.handle_message(
        session_id=web_session_id,
        user_message="Fare calculate karo 12952 class 3A 2 passengers",
        channel="web"
    )
    assert resp_fare.action_type == "FARE_BREAKDOWN"
    assert resp_fare.payload["total_fare"] > 0
    assert resp_fare.payload["passengers_count"] == 2

    # 4. Test Telegram Channel Flow with Same Logic
    tg_chat_id = 7875481582
    tg_resp = await telegram_adapter.process_user_text(
        chat_id=tg_chat_id,
        text="Delhi se Jammu 25 Sep ki train check karo"
    )
    assert tg_resp is not None
    assert tg_resp.action_type == "TRAIN_LIST"

    tg_sess = session_manager.get_session(f"tg_{tg_chat_id}")
    assert tg_sess is not None
    assert tg_sess.channel == "telegram"
