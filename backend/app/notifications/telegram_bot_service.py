import asyncio
import re
from datetime import datetime, date, timedelta
from typing import Dict, Any, Optional, List
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

# Common Indian Cities & Station Codes Map
CITY_STATION_MAP = {
    "delhi": "NDLS", "new delhi": "NDLS", "ndls": "NDLS", "dli": "DLI", "old delhi": "DLI", "nizamuddin": "NZM", "nzm": "NZM",
    "mumbai": "MMCT", "bombay": "MMCT", "mmct": "MMCT", "cstm": "CSMT", "csmt": "CSMT", "bandra": "BDTS", "bdts": "BDTS",
    "kolkata": "HWH", "calcutta": "HWH", "howrah": "HWH", "hwh": "HWH", "sealdah": "SDAH", "sdah": "SDAH",
    "varanasi": "BSB", "banaras": "BSB", "kashi": "BSB", "bsb": "BSB",
    "bengaluru": "SBC", "bangalore": "SBC", "sbc": "SBC", "yesvantpur": "YPR", "ypr": "YPR",
    "bhopal": "BPL", "bpl": "BPL", "habibganj": "RKMP", "rkmp": "RKMP",
    "patna": "PNBE", "pnbe": "PNBE",
    "kanpur": "CNB", "cnb": "CNB",
    "lucknow": "LKO", "lko": "LKO",
    "chennai": "MAS", "madras": "MAS", "mas": "MAS",
    "hyderabad": "SC", "secunderabad": "SC", "sc": "SC",
    "ahmedabad": "ADI", "adi": "ADI",
    "pune": "PUNE", "pune": "PUNE",
    "jaipur": "JP", "jp": "JP",
    "chandigarh": "CDG", "cdg": "CDG",
    "amritsar": "ASR", "asr": "ASR",
    "goa": "MAO", "madgaon": "MAO", "mao": "MAO",
    "ayodhya": "AY", "ay": "AY",
    "agra": "AGC", "agc": "AGC",
    "gwalior": "GWL", "gwl": "GWL",
    "nagpur": "NGP", "ngp": "NGP",
    "surat": "ST", "st": "ST"
}

def resolve_station(text: str) -> Optional[str]:
    clean = text.strip().lower()
    if clean.upper() in CITY_STATION_MAP.values():
        return clean.upper()
    if clean in CITY_STATION_MAP:
        return CITY_STATION_MAP[clean]
    # Check if station code
    if len(clean) in [3, 4, 5] and clean.isalpha():
        return clean.upper()
    return None

def parse_date_natural(text: str) -> Optional[str]:
    t = text.strip().lower()
    today = date.today()
    if t in ["aaj", "today"]:
        return today.strftime("%d/%m/%Y")
    if t in ["kal", "tomorrow"]:
        return (today + timedelta(days=1)).strftime("%d/%m/%Y")
    if t in ["parso", "parson", "day after tomorrow"]:
        return (today + timedelta(days=2)).strftime("%d/%m/%Y")
    if t in ["next week", "agle hafte"]:
        return (today + timedelta(days=7)).strftime("%d/%m/%Y")

    # Match DD/MM/YYYY or DD-MM-YYYY or DD.MM.YYYY
    m = re.search(r'\b(\d{1,2})[/\-\.](\d{1,2})(?:[/\-\.](\d{2,4}))?\b', t)
    if m:
        day = int(m.group(1))
        month = int(m.group(2))
        year = int(m.group(3)) if m.group(3) else today.year
        if year < 100:
            year += 2000
        try:
            parsed = date(year, month, day)
            if parsed < today:
                parsed = date(today.year + 1, month, day)
            return parsed.strftime("%d/%m/%Y")
        except ValueError:
            pass

    # Match month names e.g. "15 oct", "25 march"
    months = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
    }
    for m_name, m_num in months.items():
        if m_name in t:
            day_match = re.search(r'\b(\d{1,2})\b', t)
            if day_match:
                day = int(day_match.group(1))
                year = today.year
                try:
                    parsed = date(year, m_num, day)
                    if parsed < today:
                        parsed = date(year + 1, m_num, day)
                    return parsed.strftime("%d/%m/%Y")
                except ValueError:
                    pass
    return None

def parse_class_natural(text: str) -> Optional[str]:
    t = text.strip().lower()
    if any(k in t for k in ["3a", "3 tier", "third ac", "3rd ac", "ac 3"]):
        return "3A"
    if any(k in t for k in ["2a", "2 tier", "second ac", "2nd ac", "ac 2"]):
        return "2A"
    if any(k in t for k in ["1a", "first ac", "1st ac", "ac 1"]):
        return "1A"
    if any(k in t for k in ["sl", "sleeper"]):
        return "SL"
    if any(k in t for k in ["cc", "chair car", "chaircar"]):
        return "CC"
    if any(k in t for k in ["2s", "second sitting"]):
        return "2S"
    return None

def parse_passenger_info(text: str) -> Dict[str, Any]:
    # e.g., "Deepak 28 M", "Deepak Kataria, 29, Male, Lower", "Priya"
    parts = [p.strip() for p in re.split(r'[, ]+', text.strip()) if p.strip()]
    name_parts = []
    age = 30
    gender = "M"
    berth = "NONE"

    for part in parts:
        if part.isdigit() and 1 <= int(part) <= 120:
            age = int(part)
        elif part.upper() in ["M", "MALE", "PURUSH"]:
            gender = "M"
        elif part.upper() in ["F", "FEMALE", "MAHILA", "WOMAN"]:
            gender = "F"
        elif part.upper() in ["T", "TRANSGENDER"]:
            gender = "T"
        elif part.upper() in ["LB", "LOWER"]:
            berth = "LB"
        elif part.upper() in ["MB", "MIDDLE"]:
            berth = "MB"
        elif part.upper() in ["UB", "UPPER"]:
            berth = "UB"
        elif part.upper() in ["SL", "SIDE LOWER"]:
            berth = "SL"
        elif part.upper() in ["SU", "SIDE UPPER"]:
            berth = "SU"
        else:
            name_parts.append(part.capitalize())

    name = " ".join(name_parts) if name_parts else text.strip()
    return {"name": name, "age": age, "gender": gender, "berth_preference": berth}

def auto_save_passenger_to_db(pax: Dict[str, Any]):
    name = pax.get("name", "").strip()
    if not name or len(name) < 2:
        return
    db = SessionLocal()
    try:
        existing = db.query(Passenger).filter(Passenger.name.ilike(name)).first()
        if not existing:
            new_p = Passenger(
                name=name,
                age=pax.get("age", 30),
                gender=pax.get("gender", "M"),
                berth_preference=pax.get("berth_preference", "NONE"),
                is_default=False
            )
            db.add(new_p)
            db.commit()
    except Exception:
        pass
    finally:
        db.close()

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

        if data.startswith("route_"):
            route_parts = data.replace("route_", "").split("_")
            state["data"] = state.get("data", {})
            state["data"]["from_station"] = route_parts[0]
            state["data"]["to_station"] = route_parts[1]
            state["step"] = "ASK_DATE"
            user_chat_states[chat_id] = state
            await self._ask_date(chat_id)

        elif data.startswith("date_"):
            days = int(data.replace("date_", ""))
            target_date = (date.today() + timedelta(days=days)).strftime("%d/%m/%Y")
            state["data"] = state.get("data", {})
            state["data"]["journey_date"] = target_date
            state["step"] = "ASK_PASSENGER"
            user_chat_states[chat_id] = state
            await self._ask_passenger(chat_id)

        elif data.startswith("pax_"):
            pax_name = data.replace("pax_", "")
            db = SessionLocal()
            p_obj = db.query(Passenger).filter(Passenger.name == pax_name).first()
            age = p_obj.age if p_obj else 30
            gender = p_obj.gender if p_obj else "M"
            berth = p_obj.berth_preference if p_obj else "NONE"
            db.close()

            state["data"] = state.get("data", {})
            state["data"]["passengers"] = [{"name": pax_name, "age": age, "gender": gender, "berth_preference": berth}]
            state["step"] = "ASK_CLASS"
            user_chat_states[chat_id] = state
            await self._ask_class(chat_id)

        elif data.startswith("class_"):
            cls_name = data.replace("class_", "")
            state["data"] = state.get("data", {})
            state["data"]["journey_class"] = cls_name
            state["step"] = "CONFIRM_SUMMARY"
            user_chat_states[chat_id] = state
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

        # 2. Main menu commands
        if clean in ["/start", "/help", "hi", "hello", "namaste", "menu", "/menu"]:
            await self._send_welcome_menu(chat_id)
            return

        if clean.startswith("/cancel") or clean == "cancel":
            await self._handle_cancel(chat_id)
            return

        if clean.startswith("/status") or clean == "status":
            await self._send_status(chat_id)
            return

        if clean.startswith("/passengers") or clean in ["passengers", "passenger", "travelers"]:
            await self._send_passengers(chat_id)
            return

        if clean.startswith("/routes") or clean in ["routes", "route"]:
            await self._send_routes(chat_id)
            return

        if clean.startswith("/book") or clean in ["book", "booking", "ticket"]:
            user_chat_states[chat_id] = {"step": "ASK_ROUTE", "data": {}}
            await self._ask_route(chat_id)
            return

        # 3. Conversational State Machine + Smart Free-Text Processing
        state = user_chat_states.get(chat_id)

        # A) If user is in ASK_ROUTE step
        if state and state.get("step") in ["ASK_ROUTE", "ASK_ROUTE_MANUAL"]:
            parts = re.split(r'\bto\b|\bse\b|\b-\b|\b➔\b|\b->\b', text, flags=re.IGNORECASE)
            if len(parts) >= 2:
                from_code = resolve_station(parts[0])
                to_code = resolve_station(parts[1])
                if from_code and to_code:
                    state["data"]["from_station"] = from_code
                    state["data"]["to_station"] = to_code
                    state["step"] = "ASK_DATE"
                    user_chat_states[chat_id] = state
                    await send_telegram_message(f"✅ Route Set: *{from_code} ➔ {to_code}*", chat_id=chat_id)
                    await self._ask_date(chat_id)
                    return
            # Could not resolve route
            buttons = {"inline_keyboard": [
                [{"text": "📍 Delhi ➔ Mumbai", "callback_data": "route_NDLS_MMCT"}, {"text": "📍 Delhi ➔ Kolkata", "callback_data": "route_NDLS_HWH"}],
                [{"text": "📍 Delhi ➔ Varanasi", "callback_data": "route_NDLS_BSB"}, {"text": "📍 Delhi ➔ Bengaluru", "callback_data": "route_NDLS_SBC"}],
                [{"text": "❌ Cancel", "callback_data": "cmd_cancel"}]
            ]}
            await send_telegram_message(
                "⚠️ Station samajh nahi aaya. Please aise likhein: `Delhi to Mumbai` ya `NDLS to BSB`\nYa neeche diye gaye popular route par tap karein:",
                chat_id=chat_id,
                reply_markup=buttons
            )
            return

        # B) If user is in ASK_DATE step
        if state and state.get("step") in ["ASK_DATE", "ASK_DATE_MANUAL"]:
            parsed_d = parse_date_natural(text)
            if parsed_d:
                state["data"]["journey_date"] = parsed_d
                state["step"] = "ASK_PASSENGER"
                user_chat_states[chat_id] = state
                await send_telegram_message(f"✅ Journey Date: *{parsed_d}*", chat_id=chat_id)
                await self._ask_passenger(chat_id)
                return
            else:
                date_keyboard = {
                    "inline_keyboard": [
                        [{"text": "Kal (Tomorrow)", "callback_data": "date_1"}, {"text": "Parso (Day After)", "callback_data": "date_2"}],
                        [{"text": "Next Week", "callback_data": "date_7"}, {"text": "❌ Cancel", "callback_data": "cancel_book"}]
                    ]
                }
                await send_telegram_message(
                    "⚠️ Date samajh nahi aayi. Please aise likhein: `15 Oct` ya `25/10/2026` ya `Kal`, ya neeche button select karein:",
                    chat_id=chat_id,
                    reply_markup=date_keyboard
                )
                return

        # C) If user is in ASK_PASSENGER step
        if state and state.get("step") in ["ASK_PASSENGER", "ASK_PASSENGER_MANUAL"]:
            pax = parse_passenger_info(text)
            auto_save_passenger_to_db(pax)
            state["data"]["passengers"] = [pax]
            state["step"] = "ASK_CLASS"
            user_chat_states[chat_id] = state
            await send_telegram_message(
                f"✅ Traveler Added & Saved: *{pax['name']}* ({pax['age']}/{pax['gender']})",
                chat_id=chat_id
            )
            await self._ask_class(chat_id)
            return

        # D) If user is in ASK_CLASS step
        if state and state.get("step") in ["ASK_CLASS"]:
            cls = parse_class_natural(text)
            if cls:
                state["data"]["journey_class"] = cls
                state["step"] = "CONFIRM_SUMMARY"
                user_chat_states[chat_id] = state
                await send_telegram_message(f"✅ Class Selected: *{cls}*", chat_id=chat_id)
                await self._show_summary_and_confirm(chat_id)
                return
            else:
                cls_keyboard = {
                    "inline_keyboard": [
                        [{"text": "AC 3 Tier (3A)", "callback_data": "class_3A"}, {"text": "AC 2 Tier (2A)", "callback_data": "class_2A"}],
                        [{"text": "Sleeper (SL)", "callback_data": "class_SL"}, {"text": "Chair Car (CC)", "callback_data": "class_CC"}],
                        [{"text": "❌ Cancel", "callback_data": "cancel_book"}]
                    ]
                }
                await send_telegram_message(
                    "⚠️ Class samajh nahi aayi. `3A`, `2A`, `SL`, ya `CC` likhein ya button dabayein:",
                    chat_id=chat_id,
                    reply_markup=cls_keyboard
                )
                return

        # E) One-shot Full Sentence Parsing (e.g. "Delhi to Varanasi 15 oct Deepak 28 M 3A")
        parts = re.split(r'\bto\b|\bse\b|\b-\b|\b➔\b|\b->\b', text, flags=re.IGNORECASE)
        if len(parts) >= 2:
            from_c = resolve_station(parts[0])
            # Try to see if rest has to_station
            to_parts = parts[1].strip().split()
            if to_parts:
                to_c = resolve_station(to_parts[0])
                if from_c and to_c:
                    user_chat_states[chat_id] = {
                        "step": "ASK_DATE",
                        "data": {"from_station": from_c, "to_station": to_c}
                    }
                    await send_telegram_message(f"🚆 Route detected: *{from_c} ➔ {to_c}*", chat_id=chat_id)
                    await self._ask_date(chat_id)
                    return

        # If passenger is added from outside /passengers mode
        if len(text.split()) <= 4 and any(c.isalpha() for c in text):
            pax = parse_passenger_info(text)
            if pax["name"] and len(pax["name"]) >= 2 and pax["name"].lower() not in ["hi", "hello", "ok", "yes", "no"]:
                auto_save_passenger_to_db(pax)
                menu_btn = {"inline_keyboard": [[{"text": "🎫 Nayi Ticket Book Karein", "callback_data": "cmd_book"}], [{"text": "👥 Saved Passengers Dekhein", "callback_data": "cmd_passengers"}]]}
                await send_telegram_message(
                    f"✅ Naya passenger save ho gaya: *{pax['name']}* ({pax['age']}/{pax['gender']})!\nAb aap kabhi bhi inke naam par ticket book kar sakte hain.",
                    chat_id=chat_id,
                    reply_markup=menu_btn
                )
                return

        # Default fallback: Show interactive menu
        await self._send_welcome_menu(chat_id)

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
            "Aap apne phone se button click karke ya text chat me likh kar ticket book kar sakte hain.\n"
            "Jab bhi CAPTCHA aayega, bot aapko photo bhejega aur aap yahi text reply kar denge!\n\n"
            "👉 *Neeche diye gaye buttons par tap karein ya chat me likhein:*"
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
            keyboard = {
                "inline_keyboard": [
                    [{"text": "🎫 Nayi Booking Shuru Karein", "callback_data": "cmd_book"}],
                    [{"text": "🏠 Main Menu", "callback_data": "cmd_menu"}]
                ]
            }
            msg = (
                "👥 *Saved Passengers:*\n"
                "Abhi koi saved traveler nahi hai.\n\n"
                "💡 *Kaise add karein?*\n"
                "Aap chat me seedha naam likh kar bhej sakte hain (jaise: `Deepak 28 M`), wo automatically save ho jayega!"
            )
            await send_telegram_message(msg, chat_id=chat_id, reply_markup=keyboard)
        else:
            lines = [f"• *{p.name}* ({p.age}/{p.gender}) - Pref: {p.berth_preference}" for p in pax_list]
            keyboard = {
                "inline_keyboard": [
                    [{"text": "🎫 In Travelers Ke Saath Book Karein", "callback_data": "cmd_book"}],
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
            await send_telegram_message("Koi saved route nahi hai.", chat_id=chat_id, reply_markup=keyboard)
        else:
            buttons = []
            for r in routes:
                buttons.append([{"text": f"🚀 {r.label} ({r.from_station} ➔ {r.to_station})", "callback_data": f"route_{r.from_station}_{r.to_station}"}])
            buttons.append([{"text": "🏠 Main Menu", "callback_data": "cmd_menu"}])
            await send_telegram_message(
                "📍 *Top Popular Routes of India:*\nNeeche kisi bhi route par tap karein ya chat me naya route likhein:",
                chat_id=chat_id,
                reply_markup={"inline_keyboard": buttons}
            )

    async def _ask_route(self, chat_id: str):
        db = SessionLocal()
        saved = db.query(SavedJourney).limit(4).all()
        db.close()

        buttons = []
        for r in saved:
            buttons.append([{"text": f"📍 {r.label} ({r.from_station} ➔ {r.to_station})", "callback_data": f"route_{r.from_station}_{r.to_station}"}])
        buttons.append([{"text": "❌ Cancel", "callback_data": "cancel_book"}])

        keyboard = {"inline_keyboard": buttons}
        user_chat_states[chat_id] = {"step": "ASK_ROUTE_MANUAL", "data": {}}

        msg = (
            "🚆 *Kahan se kahan travel karna hai?*\n\n"
            "👉 *Option 1 (Button):* Neeche popular route select karein.\n"
            "💬 *Option 2 (Manual Chat):* Seedha likhein, jaise:\n"
            "`Delhi to Varanasi` ya `NDLS to BSB`"
        )
        await send_telegram_message(msg, chat_id=chat_id, reply_markup=keyboard)

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
        msg = (
            "📅 *Journey Date kya hai?*\n\n"
            "👉 *Option 1 (Button):* Quick date button dabayein.\n"
            "💬 *Option 2 (Manual Chat):* Date likhein jaise: `15 Oct`, `25/10/2026`, ya `Kal`"
        )
        await send_telegram_message(msg, chat_id=chat_id, reply_markup=keyboard)

    async def _ask_passenger(self, chat_id: str):
        db = SessionLocal()
        saved_pax = db.query(Passenger).limit(6).all()
        db.close()

        buttons = []
        for p in saved_pax:
            buttons.append([{"text": f"👤 {p.name} ({p.age}/{p.gender})", "callback_data": f"pax_{p.name}"}])
        buttons.append([{"text": "❌ Cancel", "callback_data": "cancel_book"}])

        keyboard = {"inline_keyboard": buttons}
        user_chat_states[chat_id]["step"] = "ASK_PASSENGER_MANUAL"

        if saved_pax:
            msg = (
                "👥 *Passenger kaun travel karega?*\n\n"
                "👉 *Option 1 (Button):* Saved traveler par tap karein.\n"
                "💬 *Option 2 (Manual Chat):* Naya naam likhein jaise:\n"
                "`Deepak 28 M` (ye automatically save ho jayega)"
            )
        else:
            msg = (
                "👥 *Passenger kaun travel karega?*\n\n"
                "💬 Chat me traveler ka naam aur age likhein:\n"
                "Jaise: `Deepak 28 M` ya `Priya 25 F`\n"
                "(Ye automatically aapke account me save ho jayega!)"
            )
        await send_telegram_message(msg, chat_id=chat_id, reply_markup=keyboard)

    async def _ask_class(self, chat_id: str):
        keyboard = {
            "inline_keyboard": [
                [{"text": "AC 3 Tier (3A)", "callback_data": "class_3A"}, {"text": "AC 2 Tier (2A)", "callback_data": "class_2A"}],
                [{"text": "Sleeper (SL)", "callback_data": "class_SL"}, {"text": "Chair Car (CC)", "callback_data": "class_CC"}],
                [{"text": "❌ Cancel", "callback_data": "cancel_book"}]
            ]
        }
        msg = (
            "💺 *Preferred Class select karein:*\n\n"
            "👉 *Option 1 (Button):* Button par tap karein.\n"
            "💬 *Option 2 (Manual Chat):* Type karein: `3A`, `2A`, `SL`, ya `Sleeper`"
        )
        await send_telegram_message(msg, chat_id=chat_id, reply_markup=keyboard)

    async def _show_summary_and_confirm(self, chat_id: str):
        data = user_chat_states.get(chat_id, {}).get("data", {})
        pax_list = data.get("passengers", [{}])
        pax_name = pax_list[0].get("name", "Traveler") if pax_list else "Traveler"
        pax_age = pax_list[0].get("age", 30) if pax_list else 30
        pax_gender = pax_list[0].get("gender", "M") if pax_list else "M"

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
            f"• *Route:* `{data.get('from_station')}` ➔ `{data.get('to_station')}`\n"
            f"• *Date:* {data.get('journey_date')}\n"
            f"• *Class:* {data.get('journey_class', '3A')} | Quota: General (GN)\n"
            f"• *Passenger:* {pax_name} ({pax_age}/{pax_gender})\n"
            f"• *Est. Fare:* ₹1,450.00\n\n"
            "Kya main browser me booking automation shuru karun?\n"
            "Neeche *'✅ Confirm & Book'* button dabayein:"
        )
        await send_telegram_message(summary, chat_id=chat_id, reply_markup=keyboard)

    async def _execute_telegram_booking(self, chat_id: str, data: Dict[str, Any]):
        db = SessionLocal()
        import uuid
        ref = f"BK-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

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
            auto_save_passenger_to_db(p)
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
            f"Browser automation shuru ho gayi hai. CAPTCHA aate hi main photo bhejunga.",
            chat_id=chat_id
        )

telegram_bot_service = TelegramBotService.get_instance()
