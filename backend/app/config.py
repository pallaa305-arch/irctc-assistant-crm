import os
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
BOOKINGS_DIR = DATA_DIR / "bookings"
EXPORTS_DIR = DATA_DIR / "exports"
BACKUPS_DIR = DATA_DIR / "backups"
TICKETS_DIR = DATA_DIR / "tickets"
INVOICES_DIR = DATA_DIR / "invoices"

BROWSER_PROFILE_DIR = DATA_DIR / "browser_profile"

for directory in (DATA_DIR, BOOKINGS_DIR, EXPORTS_DIR, BACKUPS_DIR, TICKETS_DIR, INVOICES_DIR, BROWSER_PROFILE_DIR):
    directory.mkdir(parents=True, exist_ok=True)

class Settings(BaseSettings):
    APP_NAME: str = "Personal IRCTC Booking Assistant & CRM"
    APP_ENV: str = "development"
    SECRET_KEY: str = "irctc-assistant-secret-key-change-in-production"
    
    # Database
    DATABASE_URL: str = f"sqlite:///{DATA_DIR / 'assistant.db'}"
    
    # Excel path
    EXCEL_FILE_PATH: str = str(BOOKINGS_DIR / "bookings.xlsx")
    
    # Telegram Bot config
    TELEGRAM_BOT_TOKEN: str = "8620217080:AAFUlVeFp-IqLvWmH5u4mI-Em3_9pZptTP4"
    TELEGRAM_CHAT_ID: str = "7875481582"
    TELEGRAM_ENABLED: bool = True
    
    # WhatsApp API config (Official Cloud API / Provider)
    WHATSAPP_API_KEY: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_RECIPIENT_PHONE: str = ""
    WHATSAPP_ENABLED: bool = False
    
    # Browser Automation Settings
    BROWSER_HEADLESS: bool = False  # Visible browser by default as requested
    BROWSER_SLOW_MO: int = 150      # Slower pace for visual inspection
    DEMO_MODE: bool = False         # Live Official IRCTC Mode by default
    IRCTC_USERNAME: str = ""
    IRCTC_PASSWORD: str = ""
    
    # Low-spec optimization
    MAX_BROWSER_INSTANCES: int = 1
    AUTO_CLOSE_IDLE_BROWSER_SECONDS: int = 300
    
    class Config:
        env_file = str(BASE_DIR / ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()
