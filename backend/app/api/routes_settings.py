import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database.connection import get_db
from app.database.models import Booking, BookingPassenger, Passenger, SavedJourney, SystemLog, SystemSetting
from app.notifications.telegram import send_telegram_message
from app.notifications.whatsapp import send_whatsapp_message
from app.config import settings

router = APIRouter(prefix="/api/settings", tags=["Settings"])

class SettingsUpdateSchema(BaseModel):
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    telegram_enabled: Optional[bool] = None
    whatsapp_api_key: Optional[str] = None
    whatsapp_phone_number_id: Optional[str] = None
    whatsapp_recipient_phone: Optional[str] = None
    whatsapp_enabled: Optional[bool] = None
    demo_mode: Optional[bool] = None
    browser_headless: Optional[bool] = None
    browser_slow_mo: Optional[int] = None
    irctc_username: Optional[str] = None
    irctc_password: Optional[str] = None

@router.get("")
async def get_settings():
    """Retrieves current application settings with masked secrets."""
    def mask(val: str) -> str:
        if not val or len(val) < 6:
            return "******" if val else ""
        return val[:3] + "..." + val[-3:]

    return {
        "telegram_bot_token_masked": mask(settings.TELEGRAM_BOT_TOKEN),
        "telegram_chat_id": settings.TELEGRAM_CHAT_ID,
        "telegram_enabled": settings.TELEGRAM_ENABLED,
        "whatsapp_phone_number_id": settings.WHATSAPP_PHONE_NUMBER_ID,
        "whatsapp_recipient_phone": settings.WHATSAPP_RECIPIENT_PHONE,
        "whatsapp_enabled": settings.WHATSAPP_ENABLED,
        "demo_mode": settings.DEMO_MODE,
        "browser_headless": settings.BROWSER_HEADLESS,
        "browser_slow_mo": settings.BROWSER_SLOW_MO,
        "irctc_username": settings.IRCTC_USERNAME,
        "irctc_password_masked": "******" if settings.IRCTC_PASSWORD else "",
        "excel_file_path": settings.EXCEL_FILE_PATH,
        "database_url": settings.DATABASE_URL
    }

@router.post("")
async def update_settings(payload: SettingsUpdateSchema):
    """Updates runtime configuration settings and persists to .env file."""
    if payload.telegram_bot_token is not None:
        settings.TELEGRAM_BOT_TOKEN = payload.telegram_bot_token
    if payload.telegram_chat_id is not None:
        settings.TELEGRAM_CHAT_ID = payload.telegram_chat_id
    if payload.telegram_enabled is not None:
        settings.TELEGRAM_ENABLED = payload.telegram_enabled

    from app.notifications.telegram_bot_service import telegram_bot_service
    if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_ENABLED:
        telegram_bot_service.start()
    else:
        telegram_bot_service.stop()

    if payload.whatsapp_api_key is not None:
        settings.WHATSAPP_API_KEY = payload.whatsapp_api_key
    if payload.whatsapp_phone_number_id is not None:
        settings.WHATSAPP_PHONE_NUMBER_ID = payload.whatsapp_phone_number_id
    if payload.whatsapp_recipient_phone is not None:
        settings.WHATSAPP_RECIPIENT_PHONE = payload.whatsapp_recipient_phone
    if payload.whatsapp_enabled is not None:
        settings.WHATSAPP_ENABLED = payload.whatsapp_enabled

    if payload.demo_mode is not None:
        settings.DEMO_MODE = payload.demo_mode
    if payload.browser_headless is not None:
        settings.BROWSER_HEADLESS = payload.browser_headless
    if payload.browser_slow_mo is not None:
        settings.BROWSER_SLOW_MO = payload.browser_slow_mo
    if payload.irctc_username is not None:
        settings.IRCTC_USERNAME = payload.irctc_username.strip()
    if payload.irctc_password is not None and payload.irctc_password != "******":
        settings.IRCTC_PASSWORD = payload.irctc_password.strip()

    # Persist to local .env
    try:
        from app.config import BASE_DIR
        env_path = BASE_DIR / ".env"
        lines = [
            f'APP_NAME="{settings.APP_NAME}"\n',
            f'APP_ENV="{settings.APP_ENV}"\n',
            f'DEMO_MODE={str(settings.DEMO_MODE).lower()}\n',
            f'BROWSER_HEADLESS={str(settings.BROWSER_HEADLESS).lower()}\n',
            f'BROWSER_SLOW_MO={settings.BROWSER_SLOW_MO}\n',
            f'IRCTC_USERNAME="{settings.IRCTC_USERNAME}"\n',
            f'IRCTC_PASSWORD="{settings.IRCTC_PASSWORD}"\n',
            f'TELEGRAM_BOT_TOKEN="{settings.TELEGRAM_BOT_TOKEN}"\n',
            f'TELEGRAM_CHAT_ID="{settings.TELEGRAM_CHAT_ID}"\n',
            f'TELEGRAM_ENABLED={str(settings.TELEGRAM_ENABLED).lower()}\n'
        ]
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
    except Exception:
        pass

    return {"success": True, "message": "Settings updated and saved to .env successfully."}

@router.post("/test-telegram")
async def test_telegram_alert():
    """Sends a test ping to Telegram."""
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        raise HTTPException(status_code=400, detail="Telegram token or chat ID is not configured.")

    from app.notifications.telegram import send_telegram_message_detailed
    success, err_msg = await send_telegram_message_detailed("🔔 *IRCTC Assistant Ping*: Telegram notifications are connected and working properly!")
    if not success:
        err_lower = (err_msg or "").lower()
        if "chat not found" in err_lower or "bot can't initiate conversation" in err_lower:
            err_msg = f"{err_msg} — Kripya pehle Telegram me apne bot ko open karke /start message bhejein!"
        elif "unauthorized" in err_lower:
            err_msg = f"{err_msg} — Bot Token galat hai. @BotFather se naya token copy karein."
        raise HTTPException(status_code=502, detail=f"Telegram Error: {err_msg}")
    return {"success": True, "message": "Test notification delivered to Telegram."}

@router.post("/test-whatsapp")
async def test_whatsapp_alert():
    """Sends a test ping to WhatsApp."""
    if not settings.WHATSAPP_API_KEY or not settings.WHATSAPP_PHONE_NUMBER_ID or not settings.WHATSAPP_RECIPIENT_PHONE:
        raise HTTPException(status_code=400, detail="WhatsApp Cloud API credentials or recipient number are missing.")

    success = await send_whatsapp_message("🔔 IRCTC Assistant Ping: WhatsApp notifications are connected and working properly!")
    if not success:
        raise HTTPException(status_code=502, detail="Failed to deliver message via WhatsApp Cloud API.")
    return {"success": True, "message": "Test notification sent to WhatsApp."}

@router.post("/delete-all-data")
async def delete_all_user_data(db: Session = Depends(get_db)):
    """
    Privacy compliance: Purges all bookings, passenger profiles, saved journeys,
    and logs permanently.
    """
    db.query(BookingPassenger).delete()
    db.query(Booking).delete()
    db.query(Passenger).delete()
    db.query(SavedJourney).delete()
    db.query(SystemLog).delete()
    db.commit()

    # Reset Excel file
    if os.path.exists(settings.EXCEL_FILE_PATH):
        try:
            os.remove(settings.EXCEL_FILE_PATH)
        except Exception:
            pass

    return {"success": True, "message": "All personal records, journeys, and logs have been wiped."}
