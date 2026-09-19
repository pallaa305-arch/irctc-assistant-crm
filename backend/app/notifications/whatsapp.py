import httpx
from typing import Optional
from app.config import settings

async def send_whatsapp_message(
    body: str, 
    recipient_phone: Optional[str] = None, 
    api_key: Optional[str] = None, 
    phone_number_id: Optional[str] = None
) -> bool:
    """
    Sends an authorized WhatsApp notification via WhatsApp Business Cloud API.
    Does NOT use unofficial WhatsApp Web scrapers or bot automations.
    """
    token = api_key or settings.WHATSAPP_API_KEY
    phone_id = phone_number_id or settings.WHATSAPP_PHONE_NUMBER_ID
    to_phone = recipient_phone or settings.WHATSAPP_RECIPIENT_PHONE

    if not token or not phone_id or not to_phone:
        return False

    url = f"https://graph.facebook.com/v19.0/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone,
        "type": "text",
        "text": {"preview_url": False, "body": body}
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            return response.status_code in [200, 201]
    except Exception:
        return False

def format_booking_confirmation_whatsapp(booking) -> str:
    return (
        f"🎫 IRCTC Ticket Confirmed!\n"
        f"PNR: {booking.pnr or 'N/A'}\n"
        f"Train: {booking.train_number or ''} {booking.train_name or ''}\n"
        f"Route: {booking.from_station} -> {booking.to_station}\n"
        f"Date: {booking.journey_date.strftime('%d/%m/%Y')}\n"
        f"Class: {booking.journey_class} | Quota: {booking.quota}\n"
        f"Fare: Rs. {booking.fare or 0:.2f}\n"
        f"Status: {booking.status}"
    )
