import asyncio
from datetime import datetime, timezone
from typing import Dict, Optional, Any

class BookingSessionState:
    def __init__(self, booking_ref: str):
        self.booking_ref = booking_ref
        self.stage: str = "PREPARING"  # Current stage
        self.status: str = "INITIATED"  # INITIATED, IN_PROGRESS, WAITING_MANUAL, PAYMENT_PENDING, CONFIRMED, FAILED, CANCELLED
        self.manual_prompt: Optional[str] = None
        self.error_message: Optional[str] = None
        self.is_paused: bool = False
        self.latest_screenshot_bytes: Optional[bytes] = None
        
        # User input handling (CAPTCHA text, OTP, or Payment confirmation)
        self.waiting_input_type: str = "NONE"  # "CAPTCHA", "OTP", "PAYMENT", "NONE"
        self.user_input_value: Optional[str] = None
        self.input_event = asyncio.Event()

        self.continue_event = asyncio.Event()
        self.cancel_event = asyncio.Event()
        self.captured_data: Dict[str, Any] = {}
        self.last_updated: datetime = datetime.now(timezone.utc)

    def set_stage(self, stage: str, status: Optional[str] = None):
        self.stage = stage
        if status:
            self.status = status
        self.last_updated = datetime.now(timezone.utc)

    def pause_for_user(self, prompt: str, is_payment: bool = False, input_type: str = "NONE", screenshot_bytes: Optional[bytes] = None):
        self.is_paused = True
        self.manual_prompt = prompt
        self.waiting_input_type = input_type
        if screenshot_bytes:
            self.latest_screenshot_bytes = screenshot_bytes
        self.status = "PAYMENT_PENDING" if is_payment else "WAITING_MANUAL"
        self.continue_event.clear()
        self.input_event.clear()
        self.user_input_value = None
        self.last_updated = datetime.now(timezone.utc)

    def provide_user_input(self, value: str):
        """Called when user types CAPTCHA/OTP via Telegram or Web"""
        self.user_input_value = value
        self.input_event.set()
        self.user_resumed()

    def user_resumed(self):
        self.is_paused = False
        self.manual_prompt = None
        self.waiting_input_type = "NONE"
        self.status = "IN_PROGRESS"
        self.continue_event.set()
        self.last_updated = datetime.now(timezone.utc)

    def user_cancelled(self, reason: str = "Cancelled by user"):
        self.is_paused = False
        self.status = "CANCELLED"
        self.waiting_input_type = "NONE"
        self.error_message = reason
        self.cancel_event.set()
        self.continue_event.set()
        self.input_event.set()
        self.last_updated = datetime.now(timezone.utc)

# In-memory registry of active booking sessions
active_sessions: Dict[str, BookingSessionState] = {}

def get_or_create_session(booking_ref: str) -> BookingSessionState:
    if booking_ref not in active_sessions:
        active_sessions[booking_ref] = BookingSessionState(booking_ref)
    return active_sessions[booking_ref]

def get_session(booking_ref: str) -> Optional[BookingSessionState]:
    return active_sessions.get(booking_ref)

def get_latest_waiting_session(max_age_seconds: int = 600) -> Optional[BookingSessionState]:
    """Finds the active session currently waiting for manual input/payment that hasn't timed out"""
    now = datetime.now(timezone.utc)
    for session in reversed(list(active_sessions.values())):
        if (session.is_paused or session.waiting_input_type != "NONE") and session.status in ["WAITING_MANUAL", "PAYMENT_PENDING"]:
            age = (now - session.last_updated).total_seconds()
            if age <= max_age_seconds:
                return session
    return None

def clear_all_waiting_sessions():
    """Cancels and clears any active or stale waiting sessions"""
    for session in list(active_sessions.values()):
        session.user_cancelled("Cleared by user request")
    active_sessions.clear()

