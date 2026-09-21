import pytest
from unittest.mock import patch, AsyncMock
from app.notifications.telegram_channel_adapter import TelegramChannelAdapter

@pytest.mark.asyncio
async def test_telegram_adapter_translates_message():
    adapter = TelegramChannelAdapter()
    resp = await adapter.process_user_text(
        chat_id=7875481582,
        text="Delhi se Jammu 25 September ki train check karo"
    )
    assert resp is not None
    assert resp.text != ""
    assert resp.action_type in ("TRAIN_LIST", "STAGE_UPDATE")

@pytest.mark.asyncio
async def test_telegram_adapter_handles_pnr():
    adapter = TelegramChannelAdapter()
    resp = await adapter.process_user_text(
        chat_id=7875481582,
        text="PNR 2451234567"
    )
    assert resp is not None
    assert "2451234567" in resp.text or resp.payload.get("pnr") == "2451234567"

@pytest.mark.asyncio
async def test_telegram_adapter_event_dispatch():
    adapter = TelegramChannelAdapter()
    with patch("app.notifications.telegram_channel_adapter.send_telegram_message", new_callable=AsyncMock) as mock_send:
        await adapter.handle_bus_event({
            "session_id": "tg_7875481582",
            "type": "STAGE_UPDATE",
            "data": {"stage": "SEARCHING", "message": "Searching IRCTC..."}
        })
        mock_send.assert_called_once()
