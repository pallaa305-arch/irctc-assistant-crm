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
    
    # Directories
    DATA_DIR: Path = DATA_DIR
    BROWSER_PROFILE_DIR: Path = BROWSER_PROFILE_DIR

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
    IRCTC_USERNAME: str = "randisumandalladeepak"
    IRCTC_PASSWORD: str = "Gandusuman@7323"
    DEFAULT_CONTACT_MOBILE: str = "9876543210"
    
    # Proxy Settings (for cloud deployments to bypass Akamai geo-blocking)
    PROXY_SERVER: str = ""    # e.g. "http://host:port" or "socks5://host:port"
    PROXY_USERNAME: str = ""
    PROXY_PASSWORD: str = ""

    # Network & Public URLs
    PUBLIC_BASE_URL: str = ""  # If using ngrok/tunnel, e.g. "https://xxxx.ngrok-free.app", otherwise auto-detected local IP
    
    @staticmethod
    def get_local_ip() -> str:
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def get_server_base_url(self) -> str:
        if self.PUBLIC_BASE_URL and self.PUBLIC_BASE_URL.strip():
            return self.PUBLIC_BASE_URL.strip().rstrip('/')
        return f"http://{self.get_local_ip()}:8000"

    class Config:
        env_file = str(BASE_DIR / ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()
