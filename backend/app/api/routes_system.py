import os
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database.connection import get_db
from app.automation.browser_manager import browser_manager
from app.config import settings

router = APIRouter(prefix="/api/system", tags=["System"])

@router.get("/status")
async def get_system_status(db: Session = Depends(get_db)):
    """Health check for all subcomponents."""
    # 1. Database
    db_connected = False
    try:
        db.execute(text("SELECT 1"))
        db_connected = True
    except Exception:
        db_connected = False

    # 2. Browser Automation status
    browser_status = "Busy" if browser_manager.is_busy else "Ready"

    # 3. Telegram
    telegram_connected = bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID and settings.TELEGRAM_ENABLED)

    # 4. WhatsApp
    whatsapp_connected = bool(settings.WHATSAPP_API_KEY and settings.WHATSAPP_PHONE_NUMBER_ID and settings.WHATSAPP_ENABLED)

    # 5. Excel
    excel_ready = True
    try:
        if not os.path.exists(settings.EXCEL_FILE_PATH):
            from app.crm.excel_exporter import init_excel_workbook
            init_excel_workbook(settings.EXCEL_FILE_PATH)
    except Exception:
        excel_ready = False

    return {
        "backend": "Online",
        "database": "Connected" if db_connected else "Disconnected",
        "browser_automation": browser_status,
        "telegram": "Connected" if telegram_connected else "Disconnected",
        "whatsapp": "Connected" if whatsapp_connected else "Disconnected",
        "excel": "Ready" if excel_ready else "Error",
        "demo_mode": settings.DEMO_MODE,
        "app_env": settings.APP_ENV
    }

@router.get("/diagnostics/page")
async def get_page_diagnostics():
    import base64
    try:
        page = await browser_manager.get_page()
        if not page.url or "irctc" not in page.url:
            await page.goto("https://www.irctc.co.in/nget/train-search", timeout=35000)
        title = await page.title()
        url = page.url
        body_text = await page.evaluate("() => document.body ? document.body.innerText.substring(0, 800) : ''")
        screenshot_bytes = await page.screenshot(full_page=False)
        return {
            "title": title,
            "url": url,
            "text": body_text,
            "screenshot_b64": base64.b64encode(screenshot_bytes).decode('ascii')
        }
    except Exception as e:
        return {"error": str(e)}
