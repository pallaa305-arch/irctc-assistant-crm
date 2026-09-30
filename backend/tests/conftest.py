import os
import uuid
from pathlib import Path

# Existing integration tests delete all booking rows. Always isolate their database
# and exports before any app module imports settings / creates its SQLAlchemy engine.
TEST_ROOT = Path(__file__).resolve().parents[1] / ".pytest_cache"
TEST_ROOT.mkdir(exist_ok=True)
TEST_DATA = TEST_ROOT / f"runtime-{uuid.uuid4().hex}"
TEST_DATA.mkdir()
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DATA / 'test.db'}"
os.environ["EXCEL_FILE_PATH"] = str(TEST_DATA / "bookings.xlsx")
os.environ["TELEGRAM_BOT_TOKEN"] = ""
os.environ["TELEGRAM_ENABLED"] = "false"

import pytest
from unittest.mock import patch, AsyncMock
from app.config import settings
from app import config

for name, folder in (("DATA_DIR", "data"), ("TICKETS_DIR", "tickets"), ("INVOICES_DIR", "invoices"), ("EXPORTS_DIR", "exports"), ("BACKUPS_DIR", "backups"), ("BOOKINGS_DIR", "bookings"), ("BROWSER_PROFILE_DIR", "browser_profile")):
    path = TEST_DATA / folder
    path.mkdir()
    setattr(config, name, path)
settings.DATA_DIR = config.DATA_DIR
settings.BROWSER_PROFILE_DIR = config.BROWSER_PROFILE_DIR

@pytest.fixture(scope="session", autouse=True)
def initialize_test_database():
    from app.database.connection import init_db
    from app.database import models
    init_db()

@pytest.fixture(autouse=True)
def disable_live_telegram_and_external_calls(monkeypatch):
    """
    Ensure automated pytest test runs NEVER send messages, photos, 
    or QR codes to the user's live Telegram bot or mobile device.
    """
    monkeypatch.setattr(settings, "TELEGRAM_ENABLED", False)
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    with patch("app.notifications.telegram.send_telegram_message", new_callable=AsyncMock), \
         patch("app.notifications.telegram.send_telegram_photo", new_callable=AsyncMock), \
         patch("app.notifications.telegram.send_telegram_document", new_callable=AsyncMock):
        yield
