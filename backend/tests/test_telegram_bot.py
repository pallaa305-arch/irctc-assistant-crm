import pytest
from unittest.mock import AsyncMock, patch
from app.automation.flow_state import get_or_create_session, get_latest_waiting_session
from app.notifications.telegram_bot_service import telegram_bot_service

@pytest.mark.asyncio
async def test_telegram_captcha_reply_routing():
    # 1. Setup a waiting session
    ref = "BK-TEST-TG-001"
    session = get_or_create_session(ref)
    session.pause_for_user("Please solve CAPTCHA", is_payment=False, input_type="CAPTCHA")

    assert session.is_paused is True
    assert session.waiting_input_type == "CAPTCHA"

    # 2. Simulate user sending text message in Telegram
    with patch("app.notifications.telegram_bot_service.send_telegram_message", new_callable=AsyncMock) as mock_send:
        await telegram_bot_service._handle_text_message("12345678", "X9K2L")

        assert session.user_input_value == "X9K2L"
        assert session.is_paused is False
        assert session.input_event.is_set()
        mock_send.assert_called_once()
        assert "CAPTCHA Received" in mock_send.call_args[0][0]

@pytest.mark.asyncio
async def test_telegram_callback_continue_and_cancel():
    ref = "BK-TEST-TG-002"
    session = get_or_create_session(ref)
    session.pause_for_user("Payment required", is_payment=True, input_type="PAYMENT")

    with patch("app.notifications.telegram_bot_service.answer_callback_query", new_callable=AsyncMock), \
         patch("app.notifications.telegram_bot_service.send_telegram_message", new_callable=AsyncMock):

        cb = {
            "id": "cb_1",
            "data": "action_continue",
            "message": {"chat": {"id": 12345678}}
        }
        await telegram_bot_service._handle_callback(cb)

        assert session.is_paused is False
        assert session.status == "IN_PROGRESS"
