import httpx
from typing import Optional, Dict, Any
from app.config import settings

_telegram_client: Optional[httpx.AsyncClient] = None

def get_telegram_client() -> httpx.AsyncClient:
    global _telegram_client
    if _telegram_client is None or _telegram_client.is_closed:
        _telegram_client = httpx.AsyncClient(
            timeout=15.0,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=50)
        )
    return _telegram_client

async def send_telegram_message_detailed(
    text: str, 
    chat_id: Optional[str] = None, 
    bot_token: Optional[str] = None,
    reply_markup: Optional[Dict[str, Any]] = None
) -> tuple[bool, Optional[str]]:
    token = bot_token or settings.TELEGRAM_BOT_TOKEN
    target_chat = chat_id or settings.TELEGRAM_CHAT_ID

    if not token:
        return False, "Bot token is missing"
    if not target_chat:
        return False, "Target chat ID is missing"

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": target_chat,
        "text": text,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        client = get_telegram_client()
        response = await client.post(url, json=payload)
        if response.status_code == 200:
            return True, None
        else:
            try:
                data = response.json()
                desc = data.get("description", response.text)
            except Exception:
                desc = response.text
            print(f"[TELEGRAM ERROR] status={response.status_code} error={desc}")
            return False, desc
    except Exception as e:
        print(f"[TELEGRAM EXCEPTION] {str(e)}")
        return False, str(e)

async def send_telegram_message(
    text: str, 
    chat_id: Optional[str] = None, 
    bot_token: Optional[str] = None,
    reply_markup: Optional[Dict[str, Any]] = None
) -> bool:
    success, _ = await send_telegram_message_detailed(text, chat_id, bot_token, reply_markup)
    return success

async def send_telegram_photo(
    photo_bytes: bytes,
    caption: str,
    chat_id: Optional[str] = None,
    bot_token: Optional[str] = None,
    reply_markup: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Sends a photo (CAPTCHA or UPI QR Code) directly to user's Telegram chat on mobile.
    """
    token = bot_token or settings.TELEGRAM_BOT_TOKEN
    target_chat = chat_id or settings.TELEGRAM_CHAT_ID

    if not token or not target_chat or not photo_bytes:
        return False

    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    data = {
        "chat_id": target_chat,
        "caption": caption,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        import json
        data["reply_markup"] = json.dumps(reply_markup)

    files = {
        "photo": ("image.png", photo_bytes, "image/png")
    }

    try:
        client = get_telegram_client()
        response = await client.post(url, data=data, files=files)
        return response.status_code == 200
    except Exception:
        return False

async def send_telegram_document(
    document_bytes: bytes,
    filename: str,
    caption: str = "",
    chat_id: Optional[str] = None,
    bot_token: Optional[str] = None,
    reply_markup: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Sends a PDF document (Ticket or Bill/Invoice) directly to user's Telegram chat.
    """
    token = bot_token or settings.TELEGRAM_BOT_TOKEN
    target_chat = chat_id or settings.TELEGRAM_CHAT_ID

    if not token or not target_chat or not document_bytes:
        return False

    url = f"https://api.telegram.org/bot{token}/sendDocument"
    data = {
        "chat_id": target_chat,
        "caption": caption,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        import json
        data["reply_markup"] = json.dumps(reply_markup)

    files = {
        "document": (filename, document_bytes, "application/pdf")
    }

    try:
        client = get_telegram_client()
        response = await client.post(url, data=data, files=files)
        return response.status_code == 200
    except Exception as e:
        print(f"[TELEGRAM DOCUMENT ERROR] {str(e)}")
        return False

async def answer_callback_query(
    callback_query_id: str,
    text: Optional[str] = None,
    bot_token: Optional[str] = None
) -> bool:
    token = bot_token or settings.TELEGRAM_BOT_TOKEN
    if not token or not callback_query_id:
        return False

    url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text

    try:
        client = get_telegram_client()
        response = await client.post(url, json=payload)
        return response.status_code == 200
    except Exception:
        return False

def format_booking_confirmation_telegram(booking, passengers) -> str:
    passenger_lines = []
    for p in passengers:
        seat_str = f" ({p.allocated_seat})" if p.allocated_seat else ""
        passenger_lines.append(f"• {p.name} ({p.age}/{p.gender}) - {p.status}{seat_str}")
    
    passengers_text = "\n".join(passenger_lines) if passenger_lines else "• As booked"

    return f"""🎫 *IRCTC Ticket Booking Confirmed!*

*PNR:* `{booking.pnr or 'N/A'}`
*Train:* {booking.train_number or ''} - {booking.train_name or 'N/A'}
*Route:* {booking.from_station} ➔ {booking.to_station}
*Journey Date:* {booking.journey_date.strftime('%d/%m/%Y')}
*Class / Quota:* {booking.journey_class} / {booking.quota}
*Passengers ({booking.passenger_count}):*
{passengers_text}

*Status:* {booking.status}
*Fare:* ₹{booking.fare or 0:.2f}
*Booking Ref:* `{booking.booking_ref}`
*Time:* {booking.created_at.strftime('%d/%m/%Y %H:%M:%S')}
"""

def format_action_required_telegram(booking, action_name: str) -> str:
    return f"""⚠️ *IRCTC Action Required*

Your booking for *{booking.from_station} ➔ {booking.to_station}* ({booking.train_number or ''}) has reached a manual verification step:

👉 *{action_name}*
"""
