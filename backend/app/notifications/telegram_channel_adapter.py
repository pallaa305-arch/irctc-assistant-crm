"""
Telegram Channel Adapter for Personal IRCTC Assistant.
Bridges Telegram Bot messages to the Unified Agent Router, ensuring 100% logic parity with the Web UI.
"""
import re
import logging
from typing import Dict, Any, Optional
from app.agents.router import agent_router, AgentResponse
from app.agents.event_bus import event_bus
from app.notifications.telegram import send_telegram_message, send_telegram_photo

logger = logging.getLogger(__name__)

class TelegramChannelAdapter:
    def __init__(self):
        # Register to global event bus to listen for telegram session updates
        event_bus.subscribe_global(self.handle_bus_event)

    async def process_user_text(self, chat_id: int, text: str) -> AgentResponse:
        """
        Receives user text from Telegram, routes to AgentRouter, and sends formatted response to Telegram.
        """
        session_id = f"tg_{chat_id}"
        resp = await agent_router.handle_message(
            session_id=session_id,
            user_message=text,
            channel="telegram",
            user_id=str(chat_id)
        )

        # Build inline keyboard buttons if action provides interactive choices
        reply_markup = None
        if resp.action_type == "TRAIN_LIST" and "trains" in resp.payload:
            keyboard = []
            for t in resp.payload["trains"][:3]:
                t_no = t.get("train_number")
                row = []
                for cls in t.get("classes", ["3A", "2A", "SL"]):
                    row.append({
                        "text": f"{t_no} {cls}",
                        "callback_data": f"select_train_{t_no}_{cls}"
                    })
                keyboard.append(row)
            if keyboard:
                reply_markup = {"inline_keyboard": keyboard}

        elif resp.action_type == "FARE_BREAKDOWN":
            t_no = resp.payload.get("train_number", "12952")
            cls = resp.payload.get("travel_class", "3A")
            reply_markup = {
                "inline_keyboard": [
                    [{"text": f"✅ Proceed to Book ({t_no} {cls})", "callback_data": f"select_train_{t_no}_{cls}"}],
                    [{"text": "❌ Cancel", "callback_data": "cmd_cancel"}]
                ]
            }

        # Send response text back to telegram chat
        await send_telegram_message(resp.text, chat_id=str(chat_id), reply_markup=reply_markup)
        return resp

    async def handle_bus_event(self, event: Dict[str, Any]):
        """
        Pushes real-time automation milestones from the EventBus to Telegram.
        """
        session_id = event.get("session_id", "")
        if not session_id.startswith("tg_"):
            return

        chat_id_str = session_id.replace("tg_", "")
        event_type = event.get("type")
        data = event.get("data", {})

        try:
            if event_type == "STAGE_UPDATE":
                msg = data.get("message", "")
                if msg:
                    await send_telegram_message(f"🔄 *IRCTC Update:*\n{msg}", chat_id=chat_id_str)

            elif event_type == "PAYMENT_QR_READY":
                qr_path = data.get("qr_path")
                amount = data.get("amount", 0.0)
                caption = (
                    f"💳 *IRCTC Official Payment QR Code*\n"
                    f"💵 Amount: ₹{amount}\n"
                    f"⏱ Valid for: 5 Minutes\n\n"
                    f"Google Pay, PhonePe, ya Paytm se scan karke payment complete karein."
                )
                if qr_path:
                    await send_telegram_photo(photo_path=qr_path, caption=caption, chat_id=chat_id_str)
                else:
                    await send_telegram_message(caption, chat_id=chat_id_str)

            elif event_type == "BOOKING_CONFIRMED":
                pnr = data.get("pnr", "")
                status = data.get("status", "CNF")
                await send_telegram_message(
                    f"🎉 *Booking Mubarak Ho!*\n"
                    f"🎫 *PNR:* {pnr}\n"
                    f"📊 *Status:* {status}\n\n"
                    f"Aapka official ticket PDF dashboard par ready hai.",
                    chat_id=chat_id_str
                )
        except Exception as e:
            logger.warning(f"Failed to push event to telegram: {e}")

telegram_adapter = TelegramChannelAdapter()
