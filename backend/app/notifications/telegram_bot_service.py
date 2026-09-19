import asyncio
import re
from datetime import datetime, date, timedelta
from typing import Dict, Any, Optional
import httpx

from app.config import settings
from app.database.connection import SessionLocal
from app.database.models import Booking, Passenger, SavedJourney
from app.automation.flow_state import get_session, get_latest_waiting_session, get_or_create_session
from app.automation.mock_flow import run_mock_booking_flow
from app.automation.irctc_flow import run_real_irctc_booking_flow
from app.notifications.telegram import (
    send_telegram_message, 
    send_telegram_photo, 
    answer_callback_query,
    format_booking_confirmation_telegram
)

# In-memory conversational state per Telegram chat
# Format: { chat_id: { "step": "...", "data": { ... } } }
user_chat_states: Dict[str, Dict[str, Any]] = {}

class TelegramBotService:
    _instance: Optional['TelegramBotService'] = None
    _is_running: bool = False
    _poll_task: Optional[asyncio.Task] = None
    _offset: int = 0

    @classmethod
    def get_instance(cls) -> 'TelegramBotService':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def is_running(self) -> bool:
        return self._is_running

    def start(self):
        if self._is_running:
            return
        if not settings.TELEGRAM_BOT_TOKEN:
            return
        self._is_running = True
        self._poll_task = asyncio.create_task(self._poll_loop())

    def stop(self):
        self._is_running = False
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()

    async def _poll_loop(self):
        token = settings.TELEGRAM_BOT_TOKEN
        url = f"https://api.telegram.org/bot{token}/getUpdates"

        while self._is_running:
            try:
                params = {
                    "offset": self._offset,
                    "timeout": 20
                }
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.get(url, params=params)
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("ok"):
                            for update in data.get("result", []):
                                self._offset = update["update_id"] + 1
                                await self._handle_update(update)
                    elif resp.status_code == 409:
                        await asyncio.sleep(5)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(3)

    async def _handle_update(self, update: Dict[str, Any]):
        # 1. Handle Inline Button Clicks (callback_query)
        if "callback_query" in update:
            await self._handle_callback(update["callback_query"])
            return

        # 2. Handle Text Messages
        if "message" in update and "text" in update["message"]:
            msg = update["message"]
            chat_id = str(msg["chat"]["id"])
            text = msg["text"].strip()
            await self._handle_text_message(chat_id, text)

    async def _handle_callback(self, cb: Dict[str, Any]):
        cb_id = cb["id"]
        data = cb.get("data", "")
        chat_id = str(cb["message"]["chat"]["id"])

        await answer_callback_query(cb_id)

        # Handle Action / Continue buttons
        if data == "action_continue":
            waiting_session = get_latest_waiting_session()
            if waiting_session:
                waiting_session.user_resumed()
                await send_telegram_message("✅ *Resumed!* Automation aage badh rahi hai...", chat_id=chat_id)
            else:
                await send_telegram_message("ℹ️ Koi active waiting booking nahi hai.", chat_id=chat_id)
            return

        if data == "action_cancel" or data == "cmd_cancel":
            await self._handle_cancel(chat_id)
            return

        if data == "cmd_book":
            user_chat_states[chat_id] = {"step": "ASK_ROUTE", "data": {}}
            await self._ask_route(chat_id)
            return

        if data == "cmd_status":
            await self._send_status(chat_id)
            return

        if data == "cmd_passengers":
            await self._send_passengers(chat_id)
            return

        if data == "cmd_routes":
            await self._send_routes(chat_id)
            return

        if data == "cmd_menu":
            await self._send_welcome_menu(chat_id)
            return

        # Handle conversational booking wizard button selections
        state = user_chat_states.get(chat_id, {})
        step = state.get("step")

        if data.startswith("route_"):
            route_parts = data.replace("route_", "").split("_")
            state["data"]["from_station"] = route_parts[0]
            state["data"]["to_station"] = route_parts[1]
            state["step"] = "ASK_DATE"
            await self._ask_date(chat_id)

        elif data.startswith("date_"):
            days = int(data.replace("date_", ""))
            target_date = (date.today() + timedelta(days=days)).strftime("%d/%m/%Y")
            state["data"]["journey_date"] = target_date
            state["step"] = "ASK_PASSENGER"
            await self._ask_passenger(chat_id)

        elif data.startswith("pax_"):
            pax_name = data.replace("pax_", "")
            state["data"]["passengers"] = [{"name": pax_name, "age": 30, "gender": "M", "berth_preference": "NONE"}]
            state["step"] = "ASK_CLASS"
            await self._ask_class(chat_id)

        elif data.startswith("class_"):
            cls_name = data.replace("class_", "")
            state["data"]["journey_class"] = cls_name
            state["step"] = "CONFIRM_SUMMARY"
            await self._show_summary_and_confirm(chat_id)

        elif data == "confirm_book":
            await self._execute_telegram_booking(chat_id, state.get("data", {}))
            user_chat_states.pop(chat_id, None)

        elif data == "cancel_book":
            user_chat_states.pop(chat_id, None)
            menu_btn = {"inline_keyboard": [[{"text": "🎫 Nayi Booking Karein", "callback_data": "cmd_book"}]]}
            await send_telegram_message("❌ Booking request cancel kar di gayi.", chat_id=chat_id, reply_markup=menu_btn)

    async def _handle_text_message(self, chat_id: str, text: str):
        # 1. Check if an active booking is waiting for manual input (CAPTCHA or OTP)
        waiting_session = get_latest_waiting_session()
        if waiting_session and waiting_session.waiting_input_type in ["CAPTCHA", "OTP"]:
            input_type = waiting_session.waiting_input_type
            waiting_session.provide_user_input(text)
            await send_telegram_message(
                f"✅ *{input_type} Received:* `{text}`\nIRCTC me enter karke submit kiya ja raha hai...",
                chat_id=chat_id
            )
            return

        clean = text.strip().lower()

        # 2. Command handlers (support /command, emojis, and plain words)
        if clean.startswith("/start") or clean.startswith("/help") or clean == "menu" or clean.startswith("/menu"):
            await self._send_welcome_menu(chat_id)
            return

        if clean.startswith("/cancel") or "cancel" in clean:
            await self._handle_cancel(chat_id)
            return

        if clean.startswith("/status") or "status" in clean:
            await self._send_status(chat_id)
            return

        if clean.startswith("/passengers") or "passenger" in clean or "traveler" in clean:
            await self._send_passengers(chat_id)
            return

        if clean.startswith("/routes") or "route" in clean:
            await self._send_routes(chat_id)
            return

        if clean.startswith("/book") or "book" in clean or "ticket" in clean:
            user_chat_states[chat_id] = {"step": "ASK_ROUTE", "data": {}}
            await self._ask_route(chat_id)
            return

    async def _send_welcome_menu(self, chat_id: str):
        buttons = {
            "inline_keyboard": [
                [
                    {"text": "🎫 Nayi Ticket Book Karein", "callback_data": "cmd_book"}
                ],
                [
                    {"text": "🔄 Current Status", "callback_data": "cmd_status"},
                    {"text": "👥 Saved Passengers", "callback_data": "cmd_passengers"}
                ],
                [
                    {"text": "📍 Saved Routes", "callback_data": "cmd_routes"},
                    {"text": "❌ Cancel Request", "callback_data": "cmd_cancel"}
                ]
            ]
        }
        welcome = (
            "🚆 *Namaste! Personal IRCTC Booking Assistant me aapka swagat hai.*\n\n"
            "Aap apne phone se seedha train ticket book kar sakte hain.\n"
            "Jab bhi CAPTCHA aayega, bot aapko photo bhejega aur aap yahi text reply karke solve kar denge!\n\n"
            "👉 *Kisi bhi option par tap karein:*"
        )
        await send_telegram_message(welcome, chat_id=chat_id, reply_markup=buttons)

    async def _handle_cancel(self, chat_id: str):
        waiting_session = get_latest_waiting_session()
        keyboard = {"inline_keyboard": [[{"text": "🎫 Nayi Booking Shuru Karein", "callback_data": "cmd_book"}]]}
        if chat_id in user_chat_states:
            user_chat_states.pop(chat_id, None)
            await send_telegram_message("❌ Current booking request cancel ho gayi.", chat_id=chat_id, reply_markup=keyboard)
        elif waiting_session:
            waiting_session.user_cancelled()
            await send_telegram_message("❌ Active booking session cancel ho gaya.", chat_id=chat_id, reply_markup=keyboard)
        else:
            await send_telegram_message("Koi active booking ya conversation nahi hai.", chat_id=chat_id, reply_markup=keyboard)

    async def _send_status(self, chat_id: str):
        waiting_session = get_latest_waiting_session()
        if waiting_session:
            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "🔄 Refresh Status", "callback_data": "cmd_status"},
                        {"text": "❌ Cancel Booking", "callback_data": "action_cancel"}
                    ]
                ]
            }
            await send_telegram_message(
                f"🔄 *Active Booking:* `{waiting_session.booking_ref}`\n"
                f"*Status:* `{waiting_session.status}`\n"
                f"*Stage:* `{waiting_session.stage}`\n"
                f"*Prompt:* {waiting_session.manual_prompt or 'Processing...'}",
                chat_id=chat_id,
                reply_markup=keyboard
            )
        else:
            keyboard = {
                "inline_keyboard": [
                    [{"text": "🎫 Nayi Ticket Book Karein", "callback_data": "cmd_book"}]
                ]
            }
            await send_telegram_message("✅ *Koi active booking in-progress nahi hai.*", chat_id=chat_id, reply_markup=keyboard)

    async def _send_passengers(self, chat_id: str):
        db = SessionLocal()
        pax_list = db.query(Passenger).all()
        db.close()
        if not pax_list:
            keyboard = {"inline_keyboard": [[{"text": "🏠 Main Menu", "callback_data": "cmd_menu"}]]}
            await send_telegram_message("Koi saved passenger profile nahi hai. Web dashboard se add karein.", chat_id=chat_id, reply_markup=keyboard)
        else:
            lines = [f"• *{p.name}* ({p.age}/{p.gender}) - Pref: {p.berth_preference}" for p in pax_list]
            keyboard = {
                "inline_keyboard": [
                    [{"text": "🎫 Nayi Booking Shuru Karein", "callback_data": "cmd_book"}],
                    [{"text": "🏠 Main Menu", "callback_data": "cmd_menu"}]
                ]
            }
            await send_telegram_message("👥 *Saved Passenger Profiles:*\n" + "\n".join(lines), chat_id=chat_id, reply_markup=keyboard)

    async def _send_routes(self, chat_id: str):
        db = SessionLocal()
        routes = db.query(SavedJourney).all()
        db.close()
        if not routes:
            keyboard = {"inline_keyboard": [[{"text": "🏠 Main Menu", "callback_data": "cmd_menu"}]]}
            await send_telegram_message("Koi saved route nahi hai. Web dashboard se add karein.", chat_id=chat_id, reply_markup=keyboard)
        else:
            lines = [f"• *{r.label}*: `{r.from_station}` ➔ `{r.to_station}` ({r.preferred_class})" for r in routes]
            buttons = []
            for r in routes:
                buttons.append([{"text": f"🚀 Book {r.label} ({r.from_station} ➔ {r.to_station})", "callback_data": f"route_{r.from_station}_{r.to_station}"}])
            buttons.append([{"text": "🏠 Main Menu", "callback_data": "cmd_menu"}])
            await send_telegram_message(
                "📍 *Saved Frequent Routes:*\n" + "\n".join(lines) + "\n\nQuick book karne ke liye kisi route par tap karein:",
                chat_id=chat_id,
                reply_markup={"inline_keyboard": buttons}
            )

        # 3. Conversational State Machine for /book
        state = user_chat_states.get(chat_id)
        if state:
            step = state.get("step")
            if step == "ASK_ROUTE_MANUAL":
                # Expecting format: "NDLS to BPL" or "NDLS - BPL"
                parts = re.split(r'to|-|➔|->', text, flags=re.IGNORECASE)
                if len(parts) >= 2:
                    state["data"]["from_station"] = parts[0].strip().upper()
                    state["data"]["to_station"] = parts[1].strip().upper()
                    state["step"] = "ASK_DATE"
                    await self._ask_date(chat_id)
                else:
                    await send_telegram_message("Format samajh nahi aaya. Please aise likhein: `NDLS to BPL`", chat_id=chat_id)

            elif step == "ASK_DATE_MANUAL":
                # Expecting DD/MM/YYYY
                state["data"]["journey_date"] = text.strip()
                state["step"] = "ASK_PASSENGER"
                await self._ask_passenger(chat_id)

            elif step == "ASK_PASSENGER_MANUAL":
                name = text.strip()
                state["data"]["passengers"] = [{"name": name, "age": 30, "gender": "M", "berth_preference": "NONE"}]
                state["step"] = "ASK_CLASS"
                await self._ask_class(chat_id)

    async def _ask_route(self, chat_id: str):
        db = SessionLocal()
        saved = db.query(SavedJourney).limit(4).all()
        db.close()

        buttons = []
        for r in saved:
            buttons.append([{"text": f"📍 {r.label} ({r.from_station} ➔ {r.to_station})", "callback_data": f"route_{r.from_station}_{r.to_station}"}])

        keyboard = {"inline_keyboard": buttons}
        user_chat_states[chat_id]["step"] = "ASK_ROUTE_MANUAL"

        msg = (
            "🚆 *Kahan se kahan travel karna hai?*\n\n"
            "Aap seedha likh sakte hain, jaise: `NDLS to BPL`\n"
            "Ya neeche diye gaye Saved Route par tap karein:"
        )
        await send_telegram_message(msg, chat_id=chat_id, reply_markup=keyboard if buttons else None)

    async def _ask_date(self, chat_id: str):
        today = date.today()
        d1 = (today + timedelta(days=1)).strftime("%d/%m")
        d2 = (today + timedelta(days=2)).strftime("%d/%m")
        d7 = (today + timedelta(days=7)).strftime("%d/%m")

        keyboard = {
            "inline_keyboard": [
                [
                    {"text": f"Kal ({d1})", "callback_data": "date_1"},
                    {"text": f"Parso ({d2})", "callback_data": "date_2"},
                    {"text": f"Next Week ({d7})", "callback_data": "date_7"}
                ],
                [
                    {"text": "❌ Cancel", "callback_data": "cancel_book"}
                ]
            ]
        }
        user_chat_states[chat_id]["step"] = "ASK_DATE_MANUAL"
        await send_telegram_message(
            "📅 *Journey Date kya hai?*\nQuick button select karein ya date type karein (`DD/MM/YYYY`):",
            chat_id=chat_id,
            reply_markup=keyboard
        )

    async def _ask_passenger(self, chat_id: str):
        db = SessionLocal()
        saved_pax = db.query(Passenger).limit(4).all()
        db.close()

        buttons = []
        for p in saved_pax:
            buttons.append([{"text": f"👤 {p.name} ({p.age}/{p.gender})", "callback_data": f"pax_{p.name}"}])
        buttons.append([{"text": "❌ Cancel", "callback_data": "cancel_book"}])

        keyboard = {"inline_keyboard": buttons}
        user_chat_states[chat_id]["step"] = "ASK_PASSENGER_MANUAL"

        msg = "👥 *Passenger kaun travel karega?*\nNeeche saved traveler select karein ya naya naam type karein:"
        await send_telegram_message(msg, chat_id=chat_id, reply_markup=keyboard if buttons else None)

    async def _ask_class(self, chat_id: str):
        keyboard = {
            "inline_keyboard": [
                [{"text": "AC 3 Tier (3A)", "callback_data": "class_3A"}, {"text": "AC 2 Tier (2A)", "callback_data": "class_2A"}],
                [{"text": "Sleeper (SL)", "callback_data": "class_SL"}, {"text": "Chair Car (CC)", "callback_data": "class_CC"}],
                [{"text": "❌ Cancel", "callback_data": "cancel_book"}]
            ]
        }
        await send_telegram_message("💺 *Preferred Class select karein:*", chat_id=chat_id, reply_markup=keyboard)

    async def _show_summary_and_confirm(self, chat_id: str):
        data = user_chat_states.get(chat_id, {}).get("data", {})
        pax_name = data.get("passengers", [{}])[0].get("name", "Traveler")

        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "✅ Confirm & Book", "callback_data": "confirm_book"},
                    {"text": "❌ Cancel", "callback_data": "cancel_book"}
                ]
            ]
        }

        summary = (
            "📋 *Ticket Booking Summary:*\n\n"
            f"• *Route:* {data.get('from_station')} ➔ {data.get('to_station')}\n"
            f"• *Date:* {data.get('journey_date')}\n"
            f"• *Class:* {data.get('journey_class', '3A')} | Quota: General (GN)\n"
            f"• *Passenger:* {pax_name}\n"
            f"• *Est. Fare:* ₹1,450.00\n\n"
            "Kya main browser me booking automation shuru karun?"
        )
        await send_telegram_message(summary, chat_id=chat_id, reply_markup=keyboard)

    async def _execute_telegram_booking(self, chat_id: str, data: Dict[str, Any]):
        db = SessionLocal()
        import uuid
        ref = f"BK-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

        # Parse date
        date_str = data.get("journey_date", "")
        try:
            if "/" in date_str:
                parts = [int(x) for x in date_str.split("/")]
                if len(parts) == 3:
                    j_date = date(parts[2], parts[1], parts[0])
                else:
                    j_date = date.today() + timedelta(days=7)
            else:
                j_date = date.today() + timedelta(days=7)
        except Exception:
            j_date = date.today() + timedelta(days=7)

        booking = Booking(
            booking_ref=ref,
            from_station=data.get("from_station", "NDLS"),
            to_station=data.get("to_station", "BPL"),
            boarding_station=data.get("from_station", "NDLS"),
            journey_date=j_date,
            journey_class=data.get("journey_class", "3A"),
            quota="GN",
            train_number="12002",
            train_name="Selected Train",
            passenger_count=len(data.get("passengers", [])),
            status="INITIATED",
            payment_status="PENDING"
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)

        from app.database.models import BookingPassenger
        for p in data.get("passengers", []):
            bp = BookingPassenger(
                booking_id=booking.id,
                name=p["name"],
                age=p.get("age", 30),
                gender=p.get("gender", "M"),
                berth_preference=p.get("berth_preference", "NONE"),
                status="CNF"
            )
            db.add(bp)
        db.commit()

        session_state = get_or_create_session(ref)
        session_state.set_stage("PREPARING", "INITIATED")

        # Start automation task
        target_flow = run_mock_booking_flow if settings.DEMO_MODE else run_real_irctc_booking_flow
        async def runner():
            db_inner = SessionLocal()
            try:
                await target_flow(db_inner, booking.id, session_state)
            finally:
                db_inner.close()

        asyncio.create_task(runner())
        db.close()

        await send_telegram_message(
            f"🚀 *Booking Initiated!*\nRef: `{ref}`\n"
            f"Browser automation shuru ho gayi hai. CAPTCHA / OTP aate hi main aapko yahan photo bhejunga.",
            chat_id=chat_id
        )

telegram_bot_service = TelegramBotService.get_instance()
