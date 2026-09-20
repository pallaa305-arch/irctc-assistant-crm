import pytest
from unittest.mock import patch, AsyncMock
from app.config import settings

@pytest.fixture(autouse=True)
def disable_live_telegram_and_external_calls(monkeypatch):
    """
    Ensure automated pytest test runs NEVER send messages, photos, 
    or QR codes to the user's live Telegram bot or mobile device.
    """
    monkeypatch.setattr(settings, "TELEGRAM_ENABLED", False)
    with patch("app.notifications.telegram.send_telegram_message", new_callable=AsyncMock), \
         patch("app.notifications.telegram.send_telegram_photo", new_callable=AsyncMock), \
         patch("app.notifications.telegram.send_telegram_document", new_callable=AsyncMock):
        yield
