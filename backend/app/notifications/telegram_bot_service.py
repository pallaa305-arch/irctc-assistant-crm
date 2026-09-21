import asyncio
import re
import json
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Dict, Any, Optional, List
import httpx

from app.config import settings
from app.database.connection import SessionLocal
from app.database.models import Booking, Passenger, SavedJourney
from app.automation.flow_state import get_session, get_latest_waiting_session, get_or_create_session, clear_all_waiting_sessions
from app.automation.mock_flow import run_mock_booking_flow
from app.automation.irctc_flow import run_real_irctc_booking_flow
from app.notifications.telegram import (
    send_telegram_message, 
    send_telegram_photo, 
    send_telegram_document,
    answer_callback_query,
    format_booking_confirmation_telegram
)
from app.services.railway_service import railway_service
from app.services.pdf_service import pdf_service

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
    if t in ["aaj", "today", "आज"]:
        return today.strftime("%d/%m/%Y")
    if t in ["kal", "tomorrow", "कल"]:
        return (today + timedelta(days=1)).strftime("%d/%m/%Y")
    if t in ["parso", "parson", "day after tomorrow", "परसों", "परसो"]:
        return (today + timedelta(days=2)).strftime("%d/%m/%Y")
    if t in ["next week", "agle hafte", "अगले हफ्ते", "अगले सप्ताह"]:
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
    if not name or len(name) < 2 or len(name) > 30:
        return
    lower_n = name.lower()
    invalid_keywords = {
        "tomorrow", "kal", "parso", "parson", "today", "aaj", "next week", 
        "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec",
        "cancel", "radd", "menu", "status", "pnr", "live", "train", "jaana", "chahiye", "ticket",
        "hi", "hii", "hello", "hey", "namaste", "yes", "no", "haan", "nahi"
    }
    if any(k in lower_n for k in invalid_keywords):
        return
    if re.search(r'\d{1,2}[/\-\.]\d{1,2}', lower_n):
        return
    if not any(c.isalpha() for c in name):
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

def extract_one_shot_booking_data(text: str) -> Optional[Dict[str, Any]]:
    # Requires at least a route mention (from -> to or city to city)
    parts = re.split(r'\bto\b|\bse\b|\b-\b|\b➔\b|\b->\b', text, flags=re.IGNORECASE)
    if len(parts) < 2:
        return None

    data: Dict[str, Any] = {}
    remaining = text

    # 1. Class extraction
    cls_match = re.search(r'\b(3a|2a|1a|sl|cc|2s|3\s*tier|2\s*tier|first\s*ac|third\s*ac|second\s*ac|sleeper|chair\s*car)\b', remaining, re.IGNORECASE)
    if cls_match:
        c_raw = cls_match.group(1).upper()
        if '3' in c_raw or 'THIRD' in c_raw: data['journey_class'] = '3A'
        elif '2' in c_raw or 'SECOND' in c_raw: data['journey_class'] = '2A'
        elif '1' in c_raw or 'FIRST' in c_raw: data['journey_class'] = '1A'
        elif 'SL' in c_raw or 'SLEEP' in c_raw: data['journey_class'] = 'SL'
        elif 'CC' in c_raw or 'CHAIR' in c_raw: data['journey_class'] = 'CC'
        elif '2S' in c_raw: data['journey_class'] = '2S'
        else: data['journey_class'] = '3A'
        remaining = remaining[:cls_match.start()] + ' ' + remaining[cls_match.end():]

    # 2. Date extraction
    today = date.today()
    date_found = None
    if re.search(r'\bkal\b|\btomorrow\b', remaining, re.IGNORECASE):
        date_found = (today + timedelta(days=1)).strftime('%d/%m/%Y')
        remaining = re.sub(r'\bkal\b|\btomorrow\b', ' ', remaining, flags=re.IGNORECASE)
    elif re.search(r'\bparso\b|\bparson\b|\bday\s*after\s*tomorrow\b', remaining, re.IGNORECASE):
        date_found = (today + timedelta(days=2)).strftime('%d/%m/%Y')
        remaining = re.sub(r'\bparso\b|\bparson\b|\bday\s*after\s*tomorrow\b', ' ', remaining, flags=re.IGNORECASE)
    elif re.search(r'\baaj\b|\btoday\b', remaining, re.IGNORECASE):
        date_found = today.strftime('%d/%m/%Y')
        remaining = re.sub(r'\baaj\b|\btoday\b', ' ', remaining, flags=re.IGNORECASE)
    else:
        # DD/MM/YYYY or DD-MM-YYYY
        dm = re.search(r'\b(\d{1,2})[/\-\.](\d{1,2})(?:[/\-\.](\d{2,4}))?\b', remaining)
        if dm:
            d, m = int(dm.group(1)), int(dm.group(2))
            y = int(dm.group(3)) if dm.group(3) else today.year
            if y < 100: y += 2000
            try:
                date_found = date(y, m, d).strftime('%d/%m/%Y')
                remaining = remaining[:dm.start()] + ' ' + remaining[dm.end():]
            except Exception: pass
        if not date_found:
            # 15 oct, 25 march
            months = {'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6, 'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12}
            for m_name, m_num in months.items():
                match_m = re.search(rf'\b(\d{{1,2}})\s+{m_name}\w*\b', remaining, re.IGNORECASE)
                if match_m:
                    d = int(match_m.group(1))
                    date_found = date(today.year, m_num, d).strftime('%d/%m/%Y')
                    remaining = remaining[:match_m.start()] + ' ' + remaining[match_m.end():]
                    break
    if date_found:
        data['journey_date'] = date_found

    # 3. Route extraction (From and To)
    route_split = re.split(r'\bto\b|\bse\b|\b-\b|\b➔\b|\b->\b', remaining, flags=re.IGNORECASE)
    if len(route_split) >= 2:
        from_part = route_split[0].strip()
        to_part = route_split[1].strip()

        # Find from_station
        for city, code in CITY_STATION_MAP.items():
            if re.search(rf'\b{city}\b', from_part, re.IGNORECASE):
                data['from_station'] = code
                remaining = re.sub(rf'\b{city}\b', ' ', remaining, flags=re.IGNORECASE)
                break
        if not data.get('from_station'):
            for t in from_part.split():
                c = resolve_station(t)
                if c:
                    data['from_station'] = c
                    remaining = re.sub(rf'\b{t}\b', ' ', remaining, flags=re.IGNORECASE)
                    break

        # Find to_station
        for city, code in CITY_STATION_MAP.items():
            if re.search(rf'\b{city}\b', to_part, re.IGNORECASE):
                data['to_station'] = code
                remaining = re.sub(rf'\b{city}\b', ' ', remaining, flags=re.IGNORECASE)
                break
        if not data.get('to_station'):
            for t in to_part.split():
                c = resolve_station(t)
                if c:
                    data['to_station'] = c
                    remaining = re.sub(rf'\b{t}\b', ' ', remaining, flags=re.IGNORECASE)
                    break

    if not data.get('from_station') or not data.get('to_station'):
        return None

    # 4. Clean out stop words from remaining text to find Passenger
    stop_words = r'\b(train|gadi|gaadi|railway|irctc|express|to|se|ki|ka|ke|ko|par|wali|wala|liye|ticket|book|kardo|karo|karna|hai|chahiye|please|me|mein)\b'
    remaining = re.sub(stop_words, ' ', remaining, flags=re.IGNORECASE)
    remaining = ' '.join(remaining.split())

    # 5. Extract Passenger details
    if remaining:
        parts_pax = remaining.split()
        name_parts = []
        age = 30
        gender = 'M'
        for p in parts_pax:
            if p.isdigit() and 1 <= int(p) <= 120:
                age = int(p)
            elif p.upper() in ['M', 'MALE', 'PURUSH']:
                gender = 'M'
            elif p.upper() in ['F', 'FEMALE', 'MAHILA']:
                gender = 'F'
            elif p.isalpha():
                name_parts.append(p.capitalize())
        pax_name = ' '.join(name_parts)
        if pax_name and len(pax_name) >= 2:
            data['passengers'] = [{'name': pax_name, 'age': age, 'gender': gender, 'berth_preference': 'NONE'}]

    return data

# Language preferences persisted per chat_id
LANG_FILE = Path("data/telegram_languages.json")
user_languages: Dict[str, str] = {}

def load_user_languages():
    try:
        if LANG_FILE.exists():
            with open(LANG_FILE, "r", encoding="utf-8") as f:
                user_languages.update(json.load(f))
    except Exception:
        pass

def save_user_languages():
    try:
        LANG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LANG_FILE, "w", encoding="utf-8") as f:
            json.dump(user_languages, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

load_user_languages()

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

        # Persistent connection pool for fast, low-latency updates
        async with httpx.AsyncClient(timeout=35.0, limits=httpx.Limits(max_keepalive_connections=5)) as client:
            while self._is_running:
                try:
                    params = {
                        "offset": self._offset,
                        "timeout": 12
                    }
                    resp = await client.get(url, params=params)
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("ok"):
                            for update in data.get("result", []):
                                self._offset = update["update_id"] + 1
                                asyncio.create_task(self._handle_update(update))
                    elif resp.status_code == 409:
                        await asyncio.sleep(2)
                except asyncio.CancelledError:
                    break
                except Exception:
                    await asyncio.sleep(1)

    async def _send_irctc_greeting_and_language_selection(self, chat_id: str):
        greeting_text = (
            "🚆 *IRCTC (Indian Railway Catering and Tourism Corporation)*\n"
            "🇮🇳 *भारतीय रेल खानपान एवं पर्यटन निगम*\n"
            "═════════════════════════════════════\n"
            "✨ *Personal Fast-Track Ticket Booking AI Assistant*\n\n"
            "Namaste & Welcome! 🙏\n"
            "IRCTC automated ticket booking service me aapka swagat hai.\n\n"
            "👉 *Kripya aage badhne ke liye apni bhasha chunein:*\n"
            "👉 *कृपया आगे बढ़ने के लिए अपनी भाषा का चयन करें:*\n"
            "👉 *Please select your preferred language to proceed:*"
        )
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "🇮🇳 हिन्दी (Hindi)", "callback_data": "setlang_hi"},
                    {"text": "🇬🇧 English", "callback_data": "setlang_en"},
                    {"text": "🇮🇳 Hinglish", "callback_data": "setlang_hinglish"}
                ]
            ]
        }
        await send_telegram_message(greeting_text, chat_id=chat_id, reply_markup=keyboard)

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

        # Handle Language Selection & Switching
        if data == "cmd_lang":
            await self._send_irctc_greeting_and_language_selection(chat_id)
            return

        if data.startswith("setlang_"):
            chosen_lang = data.replace("setlang_", "")
            user_languages[chat_id] = chosen_lang
            save_user_languages()
            if chosen_lang == "hi":
                ack = "✅ आपकी भाषा *हिन्दी* चुन ली गई है। 🇮🇳\nआइए IRCTC में आपकी यात्रा की टिकट बुक करते हैं!"
            elif chosen_lang == "en":
                ack = "✅ Language set to: *English*. 🇬🇧\nWelcome to IRCTC automated booking assistance!"
            else:
                ack = "✅ Language set to: *Hinglish*. 🇮🇳\nAapki IRCTC ticket booking shuru karte hain!"
            await send_telegram_message(ack, chat_id=chat_id)
            await self._send_welcome_menu(chat_id)
            return

        # Handle Action / Continue buttons
        if data == "action_continue":
            waiting_session = get_latest_waiting_session()
            if waiting_session:
                waiting_session.user_resumed()
                lang = user_languages.get(chat_id, "hinglish")
                msg = "✅ *प्रक्रिया पुनः प्रारंभ!* ऑटोमेशन आगे बढ़ रहा है..." if lang == "hi" else ("✅ *Resumed!* Automation progressing..." if lang == "en" else "✅ *Resumed!* Automation aage badh rahi hai...")
                await send_telegram_message(msg, chat_id=chat_id)
            else:
                lang = user_languages.get(chat_id, "hinglish")
                msg = "ℹ️ कोई प्रतीक्षा कर रही बुकिंग नहीं है।" if lang == "hi" else ("ℹ️ No active waiting booking." if lang == "en" else "ℹ️ Koi active waiting booking nahi hai.")
                await send_telegram_message(msg, chat_id=chat_id)
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

        # Engine Mode Toggle (Safe Demo vs Live Official IRCTC)
        if data == "cmd_mode":
            await self._send_mode_menu(chat_id)
            return

        if data == "setmode_live":
            settings.DEMO_MODE = False
            lang = user_languages.get(chat_id, "hinglish")
            msg = (
                "🚀 *Live Official IRCTC Mode Active!*\n\n"
                "अब सभी बुकिंग सीधे IRCTC की आधिकारिक वेबसाइट (irctc.co.in) पर होंगी।\n"
                "• ब्राउज़र आपकी स्क्रीन पर खुलेगा\n"
                "• CAPTCHA आते ही फ़ोटो टेलीग्राम पर आएगी\n"
                "• UPI QR कोड पेमेंट के लिए भेजा जाएगा"
            ) if lang == "hi" else (
                "🚀 *Live Official IRCTC Mode Active!*\n\n"
                "Now all bookings will run directly on the official IRCTC portal (irctc.co.in).\n"
                "• Browser opens visibly\n"
                "• CAPTCHA image is forwarded to Telegram\n"
                "• UPI QR code is sent for your secure manual payment"
            ) if lang == "en" else (
                "🚀 *Live Official IRCTC Mode Active!*\n\n"
                "Ab sabhi bookings direct official IRCTC website (irctc.co.in) par execute hongi.\n"
                "• Browser screen par visible khulega\n"
                "• CAPTCHA aane par photo yaha Telegram me aayegi\n"
                "• UPI QR code payment ke liye chat me aayega"
            )
            await send_telegram_message(msg, chat_id=chat_id)
            await self._send_welcome_menu(chat_id)
            return

        if data == "setmode_demo":
            settings.DEMO_MODE = True
            lang = user_languages.get(chat_id, "hinglish")
            msg = "🛡️ *Safe Demo Mode Active!* Bookings will now run in safe simulation mode."
            await send_telegram_message(msg, chat_id=chat_id)
            await self._send_welcome_menu(chat_id)
            return

        if data == "cmd_credentials":
            await self._send_credentials_info(chat_id)
            return

        # PNR Status Check Callback
        if data == "cmd_pnr":
            user_chat_states[chat_id] = {"step": "WAIT_PNR_INPUT", "data": {}}
            lang = user_languages.get(chat_id, "hinglish")
            if lang == "hi":
                pnr_prompt = (
                    "🔍 *PNR स्थिति जांच*\n"
                    "═════════════════════════════════════\n"
                    "कृपया अपना 10 अंकों का PNR नंबर चैट में लिखकर भेजें:\n"
                    "(उदा. `2451234567`)"
                )
                cancel_txt = "❌ रद्द करें"
            elif lang == "en":
                pnr_prompt = (
                    "🔍 *PNR Status Check*\n"
                    "═════════════════════════════════════\n"
                    "Please send your 10-digit PNR number:\n"
                    "(e.g., `2451234567`)"
                )
                cancel_txt = "❌ Cancel"
            else:
                pnr_prompt = (
                    "🔍 *PNR Status Check*\n"
                    "═════════════════════════════════════\n"
                    "Kripya apna 10-digit PNR number chat me likh kar bhejein:\n"
                    "(e.g., `2451234567`)"
                )
                cancel_txt = "❌ Cancel"
            await send_telegram_message(pnr_prompt, chat_id=chat_id, reply_markup={"inline_keyboard": [[{"text": cancel_txt, "callback_data": "cmd_cancel"}]]})
            return

        # Live Train Status Callback
        if data == "cmd_live_train":
            user_chat_states[chat_id] = {"step": "WAIT_TRAIN_INPUT", "data": {}}
            lang = user_languages.get(chat_id, "hinglish")
            if lang == "hi":
                train_prompt = (
                    "📍 *लाइव ट्रेन रनिंग स्थिति*\n"
                    "═════════════════════════════════════\n"
                    "कृपया 5 अंकों का ट्रेन नंबर चैट में लिखकर भेजें:\n"
                    "(उदा. `12952`, `22436`, `12301`)"
                )
                cancel_txt = "❌ रद्द करें"
            elif lang == "en":
                train_prompt = (
                    "📍 *Live Train Running Status*\n"
                    "═════════════════════════════════════\n"
                    "Please send the 5-digit Train Number:\n"
                    "(e.g., `12952`, `22436`, `12301`)"
                )
                cancel_txt = "❌ Cancel"
            else:
                train_prompt = (
                    "📍 *Live Train Running Status*\n"
                    "═════════════════════════════════════\n"
                    "Kripya 5-digit Train Number chat me likh kar bhejein:\n"
                    "(e.g., `12952`, `22436`, `12301`)"
                )
                cancel_txt = "❌ Cancel"
            await send_telegram_message(train_prompt, chat_id=chat_id, reply_markup={"inline_keyboard": [[{"text": cancel_txt, "callback_data": "cmd_cancel"}]]})
            return

        if data.startswith("pnr_refresh_"):
            pnr_val = data.replace("pnr_refresh_", "")
            await self._lookup_and_send_pnr(chat_id, pnr_val)
            return

        if data.startswith("live_refresh_"):
            train_val = data.replace("live_refresh_", "")
            await self._lookup_and_send_live_train(chat_id, train_val)
            return

        if data.startswith("live_train_"):
            train_val = data.replace("live_train_", "")
            await self._lookup_and_send_live_train(chat_id, train_val)
            return

        if data.startswith("get_ticket_"):
            b_id_str = data.replace("get_ticket_", "")
            try:
                b_id = int(b_id_str)
                await self._send_booking_ticket_pdf(chat_id, b_id)
            except Exception:
                await self._send_booking_ticket_pdf(chat_id)
            return

        if data.startswith("get_invoice_"):
            b_id_str = data.replace("get_invoice_", "")
            try:
                b_id = int(b_id_str)
                await self._send_booking_invoice_pdf(chat_id, b_id)
            except Exception:
                await self._send_booking_invoice_pdf(chat_id)
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
            pax_val = data.replace("pax_id_", "").replace("pax_", "")
            db = SessionLocal()
            p_obj = None
            if pax_val.isdigit():
                p_obj = db.query(Passenger).filter(Passenger.id == int(pax_val)).first()
            if not p_obj:
                p_obj = db.query(Passenger).filter(Passenger.name == pax_val).first()

            pax_name = p_obj.name if p_obj else (pax_val if not pax_val.isdigit() else "Traveler")
            age = p_obj.age if p_obj else 30
            gender = p_obj.gender if p_obj else "M"
            berth = p_obj.berth_preference if p_obj else "NONE"
            db.close()

            state["data"] = state.get("data", {})
            state["data"]["passengers"] = [{"name": pax_name, "age": age, "gender": gender, "berth_preference": berth}]
            if state["data"].get("journey_class"):
                state["step"] = "CONFIRM_SUMMARY"
                user_chat_states[chat_id] = state
                await self._show_summary_and_confirm(chat_id)
            else:
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
            lang = user_languages.get(chat_id, "hinglish")
            btn_txt = "🎫 नई टिकट बुक करें" if lang == "hi" else ("🎫 Book New Ticket" if lang == "en" else "🎫 Nayi Booking Karein")
            msg_txt = "❌ बुकिंग अनुरोध रद्द कर दिया गया।" if lang == "hi" else ("❌ Booking request has been cancelled." if lang == "en" else "❌ Booking request cancel kar di gayi.")
            menu_btn = {"inline_keyboard": [[{"text": btn_txt, "callback_data": "cmd_book"}]]}
            await send_telegram_message(msg_txt, chat_id=chat_id, reply_markup=menu_btn)

    async def _render_current_booking_step(self, chat_id: str, state: Dict[str, Any]):
        step = state.get("step", "")
        if step in ["ASK_ROUTE", "ASK_ROUTE_MANUAL"]:
            await self._ask_route(chat_id)
        elif step in ["ASK_DATE", "ASK_DATE_MANUAL"]:
            await self._ask_date(chat_id)
        elif step in ["ASK_PASSENGER", "ASK_PASSENGER_MANUAL"]:
            await self._ask_passenger(chat_id)
        elif step in ["ASK_CLASS"]:
            await self._ask_class(chat_id)
        elif step in ["CONFIRM_SUMMARY"]:
            await self._show_summary_and_confirm(chat_id)

    async def _handle_text_message(self, chat_id: str, text: str):
        lang = user_languages.get(chat_id, "hinglish")
        clean = text.strip().lower()

        # -------------------------------------------------------------
        # 1. Check for Cancellation FIRST (Always top priority)
        # -------------------------------------------------------------
        if clean in ["/cancel", "cancel", "radd", "stop", "abort", "band karo", "khatam", "close", "ruk jao", "nahi chahiye", "रद्द"] or clean.startswith("/cancel"):
            await self._handle_cancel(chat_id)
            return

        # -------------------------------------------------------------
        # 2. Check for Greetings / Hello / Start
        # -------------------------------------------------------------
        GREETING_WORDS = {
            "hi", "hii", "hiii", "hello", "helloo", "hey", "heyy", 
            "namaste", "namaskar", "namaskaram", "pranam", "pranaam", 
            "shubh prabhat", "good morning", "good evening", "good afternoon", 
            "radhe radhe", "ram ram", "salaam", "kem cho", "kaise ho", "kya haal hai", 
            "menu", "/menu", "/start", "/help", "नमस्ते", "हेलो", "हाय"
        }
        is_greeting = clean in GREETING_WORDS or clean.startswith("/start") or clean.startswith("/help") or clean.startswith("/menu")

        if is_greeting:
            # 1. Clear any active or waiting booking sessions so greeting is completely clean
            clear_all_waiting_sessions()
            user_chat_states.pop(chat_id, None)

            # 2. If user has not selected language yet or explicitly typed /start or /help
            if chat_id not in user_languages or clean in ["/start", "/help"]:
                await self._send_irctc_greeting_and_language_selection(chat_id)
                return

            # 3. Always send official friendly welcome menu with all options
            await self._send_welcome_menu(chat_id)
            return

        # -------------------------------------------------------------
        # 3. Check for Language Selection Command / Query
        # -------------------------------------------------------------
        if clean in ["/language", "/lang", "language", "bhasha", "भाषा", "change language", "hindi", "english", "hinglish"]:
            await self._send_irctc_greeting_and_language_selection(chat_id)
            return

        # -------------------------------------------------------------
        # 3b. Check for Mode Command / Query (Demo vs Live IRCTC)
        # -------------------------------------------------------------
        if clean in ["/mode", "mode", "engine", "demo mode", "live mode", "change mode", "मोड"]:
            await self._send_mode_menu(chat_id)
            return

        # -------------------------------------------------------------
        # 3c. Check for IRCTC Credentials Command (/credentials)
        # -------------------------------------------------------------
        if clean.startswith("/credentials") or clean in ["credentials", "irctc login", "login id", "id password"]:
            parts = text.strip().split()
            if len(parts) >= 3:
                u = parts[1].strip()
                p = parts[2].strip()
                settings.IRCTC_USERNAME = u
                settings.IRCTC_PASSWORD = p

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

                ack = (
                    f"✅ *IRCTC Official Credentials Saved!*\n\n"
                    f"• *Username:* `{u}`\n"
                    f"• *Password:* Saved safely in local `.env`\n\n"
                    f"Ab booking ke samay IRCTC login page par username aur password automatically fill honge aur OTP checkbox tick rahega!"
                )
                await send_telegram_message(ack, chat_id=chat_id)
                return
            else:
                await self._send_credentials_info(chat_id)
                return

        # -------------------------------------------------------------
        # 4. Check for PNR Enquiry Intent or Standalone 10-Digit PNR
        # -------------------------------------------------------------
        pnr_match = re.search(r'\b\d{10}\b', text)
        if pnr_match:
            user_chat_states.pop(chat_id, None)
            await self._lookup_and_send_pnr(chat_id, pnr_match.group(0))
            return

        if clean in ["pnr", "pnr status", "check pnr", "pnr check", "pnr enquiry", "pnr kya hai", "/pnr", "पीएनआर"] or clean.startswith("/pnr") or clean.startswith("pnr "):
            user_chat_states[chat_id] = {"step": "WAIT_PNR_INPUT", "data": {}}
            if lang == "hi":
                p_msg = "🔍 *PNR स्थिति जांच*\n\nकृपया अपना 10 अंकों का PNR नंबर चैट में लिखकर भेजें:"
                btn_c = "❌ रद्द करें"
            elif lang == "en":
                p_msg = "🔍 *PNR Status Enquiry*\n\nPlease send your 10-digit PNR number:"
                btn_c = "❌ Cancel"
            else:
                p_msg = "🔍 *PNR Status Enquiry*\n\nKripya apna 10-digit PNR number chat me likh kar bhejein:"
                btn_c = "❌ Cancel"
            await send_telegram_message(p_msg, chat_id=chat_id, reply_markup={"inline_keyboard": [[{"text": btn_c, "callback_data": "cancel_book"}]]})
            return

        # If user was asked for PNR and sent text
        if user_chat_states.get(chat_id, {}).get("step") == "WAIT_PNR_INPUT":
            user_chat_states.pop(chat_id, None)
            await self._lookup_and_send_pnr(chat_id, text)
            return

        # -------------------------------------------------------------
        # 5. Check for Live Train Running Intent or 5-Digit Train Number
        # -------------------------------------------------------------
        train_match = re.search(r'\b\d{4,5}\b', text)
        is_standalone_train = bool(re.fullmatch(r'\d{5}', text.strip()))
        is_train_query = any(k in clean for k in ["train", "live", "running", "status", "gadi", "gaadi", "express", "track", "kahan", "गाड़ी"])

        if is_standalone_train or (train_match and is_train_query):
            user_chat_states.pop(chat_id, None)
            t_no = train_match.group(0) if train_match else text.strip()
            await self._lookup_and_send_live_train(chat_id, t_no)
            return

        if clean in ["live", "live train", "train status", "running status", "gadi kahan hai", "train kahan hai", "/live", "/train", "live train status", "गाड़ी कहां है"] or clean.startswith("/live") or clean.startswith("/train"):
            user_chat_states[chat_id] = {"step": "WAIT_TRAIN_INPUT", "data": {}}
            if lang == "hi":
                t_msg = "📍 *लाइव ट्रेन रनिंग स्थिति*\n\nकृपया 5 अंकों का ट्रेन नंबर चैट में भेजें (उदा. `12004`, `22435`):"
                btn_c = "❌ रद्द करें"
            elif lang == "en":
                t_msg = "📍 *Live Train Running Status*\n\nPlease send the 5-digit train number (e.g. `12004`, `22435`):"
                btn_c = "❌ Cancel"
            else:
                t_msg = "📍 *Live Train Running Status*\n\nKripya 5-digit train number chat me bhejein (e.g. `12004`, `22435`):"
                btn_c = "❌ Cancel"
            await send_telegram_message(t_msg, chat_id=chat_id, reply_markup={"inline_keyboard": [[{"text": btn_c, "callback_data": "cancel_book"}]]})
            return

        # If user was asked for Train Number and sent text
        if user_chat_states.get(chat_id, {}).get("step") == "WAIT_TRAIN_INPUT":
            user_chat_states.pop(chat_id, None)
            await self._lookup_and_send_live_train(chat_id, text)
            return

        # -------------------------------------------------------------
        # 6. Check for PDF Downloads (Ticket / Invoice)
        # -------------------------------------------------------------
        if clean in ["/ticket", "ticket", "tikket", "टिकट", "download ticket", "ticket pdf", "pdf ticket"]:
            await self._send_booking_ticket_pdf(chat_id)
            return

        if clean in ["/bill", "/invoice", "bill", "invoice", "बिल", "invois", "download bill", "bill pdf", "invoice pdf"]:
            await self._send_booking_invoice_pdf(chat_id)
            return

        # -------------------------------------------------------------
        # 7. Check for Passengers / Routes Commands
        # -------------------------------------------------------------
        if clean in ["/passengers", "passengers", "passenger", "travelers", "yatri", "yatri list"] or clean.startswith("/passengers"):
            await self._send_passengers(chat_id)
            return

        if clean in ["/routes", "routes", "route", "popular routes"] or clean.startswith("/routes"):
            await self._send_routes(chat_id)
            return

        if clean in ["/status", "status", "sthiti"] or clean.startswith("/status"):
            await self._send_status(chat_id)
            return

        # -------------------------------------------------------------
        # 8. Check for Active CAPTCHA or OTP Input
        # (Must be a clean alphanumeric token, not a sentence or greeting)
        # -------------------------------------------------------------
        waiting_session = get_latest_waiting_session()
        if waiting_session and waiting_session.waiting_input_type in ["CAPTCHA", "OTP"]:
            token = text.strip()
            if 3 <= len(token) <= 8 and not any(ch in token for ch in " \t\n,./!?:;@#") and token.lower() not in GREETING_WORDS:
                input_type = waiting_session.waiting_input_type
                waiting_session.provide_user_input(token)
                if lang == "hi":
                    rec_msg = f"✅ *{input_type} Received (प्राप्त हुआ):* `{token}`\nIRCTC में दर्ज करके आगे बढ़ा जा रहा है..."
                elif lang == "en":
                    rec_msg = f"✅ *{input_type} Received:* `{token}`\nProcessing in IRCTC..."
                else:
                    rec_msg = f"✅ *{input_type} Received:* `{token}`\nIRCTC me enter karke submit kiya ja raha hai..."
                await send_telegram_message(rec_msg, chat_id=chat_id)
                return

        # -------------------------------------------------------------
        # 9. Check for One-Shot Booking Message
        # (e.g. "Delhi to Varanasi 15 oct Deepak 28 M 3A")
        # -------------------------------------------------------------
        one_shot = extract_one_shot_booking_data(text)
        if one_shot:
            current_state = user_chat_states.get(chat_id, {})
            current_data = current_state.get("data", {})
            current_data.update(one_shot)

            if current_data.get("passengers"):
                for p in current_data["passengers"]:
                    auto_save_passenger_to_db(p)

            # Check for missing details step-by-step
            if not current_data.get("journey_date"):
                user_chat_states[chat_id] = {"step": "ASK_DATE", "data": current_data}
                route_ack = f"🚆 मार्ग तय हुआ: *{current_data['from_station']} ➔ {current_data['to_station']}*" if lang == "hi" else f"🚆 Route Set: *{current_data['from_station']} ➔ {current_data['to_station']}*"
                await send_telegram_message(route_ack, chat_id=chat_id)
                await self._ask_date(chat_id)
                return

            if not current_data.get("passengers"):
                user_chat_states[chat_id] = {"step": "ASK_PASSENGER", "data": current_data}
                r_line = f"🚆 मार्ग: *{current_data['from_station']} ➔ {current_data['to_station']}*\n📅 तारीख: *{current_data['journey_date']}*" if lang == "hi" else f"🚆 Route: *{current_data['from_station']} ➔ {current_data['to_station']}*\n📅 Date: *{current_data['journey_date']}*"
                await send_telegram_message(r_line, chat_id=chat_id)
                await self._ask_passenger(chat_id)
                return

            if not current_data.get("journey_class"):
                user_chat_states[chat_id] = {"step": "ASK_CLASS", "data": current_data}
                pax_name = current_data['passengers'][0]['name']
                r_line = f"🚆 मार्ग: *{current_data['from_station']} ➔ {current_data['to_station']}*\n📅 तारीख: *{current_data['journey_date']}*\n👤 यात्री: *{pax_name}*" if lang == "hi" else f"🚆 Route: *{current_data['from_station']} ➔ {current_data['to_station']}*\n📅 Date: *{current_data['journey_date']}*\n👤 Passenger: *{pax_name}*"
                await send_telegram_message(r_line, chat_id=chat_id)
                await self._ask_class(chat_id)
                return

            # All 4 items present -> confirm summary
            user_chat_states[chat_id] = {"step": "CONFIRM_SUMMARY", "data": current_data}
            pax = current_data["passengers"][0]
            if lang == "hi":
                os_msg = (
                    f"⚡ *त्वरित बुकिंग अनुरोध प्राप्त हुआ!*\n"
                    f"• मार्ग: *{current_data['from_station']} ➔ {current_data['to_station']}*\n"
                    f"• तारीख: *{current_data['journey_date']}*\n"
                    f"• श्रेणी: *{current_data['journey_class']}*\n"
                    f"• यात्री: *{pax['name']}* ({pax['age']}/{pax['gender']})"
                )
            elif lang == "en":
                os_msg = (
                    f"⚡ *One-Shot Booking Request Recognized!*\n"
                    f"• Route: *{current_data['from_station']} ➔ {current_data['to_station']}*\n"
                    f"• Date: *{current_data['journey_date']}*\n"
                    f"• Class: *{current_data['journey_class']}*\n"
                    f"• Traveler: *{pax['name']}* ({pax['age']}/{pax['gender']})"
                )
            else:
                os_msg = (
                    f"⚡ *One-Shot Booking Request Samjhi Gayi!*\n"
                    f"• Route: *{current_data['from_station']} ➔ {current_data['to_station']}*\n"
                    f"• Date: *{current_data['journey_date']}*\n"
                    f"• Class: *{current_data['journey_class']}*\n"
                    f"• Passenger: *{pax['name']}* ({pax['age']}/{pax['gender']})"
                )
            await send_telegram_message(os_msg, chat_id=chat_id)
            await self._show_summary_and_confirm(chat_id)
            return

        # -------------------------------------------------------------
        # 10. Check if user wants to initiate a booking
        # -------------------------------------------------------------
        is_book_intent = clean in ["book", "booking", "ticket", "book ticket", "train book", "nayi ticket", "ticket booking", "/book", "reservation", "tatkal", "seat", "बुक"] or clean.startswith("/book")
        if is_book_intent:
            user_chat_states[chat_id] = {"step": "ASK_ROUTE_MANUAL", "data": {}}
            await self._ask_route(chat_id)
            return

        # -------------------------------------------------------------
        # 11. Conversational Booking Wizard Step Handlers
        # (Strict single-process options during booking)
        # -------------------------------------------------------------
        state = user_chat_states.get(chat_id)
        if state and "step" in state:
            step = state["step"]

            # Step A: In Route Selection
            if step in ["ASK_ROUTE", "ASK_ROUTE_MANUAL"]:
                parts = re.split(r'\bto\b|\bse\b|\b-\b|\b➔\b|\b->\b', text, flags=re.IGNORECASE)
                if len(parts) >= 2:
                    from_code = resolve_station(parts[0])
                    to_code = resolve_station(parts[1])
                    if from_code and to_code:
                        state["data"]["from_station"] = from_code
                        state["data"]["to_station"] = to_code
                        state["step"] = "ASK_DATE"
                        user_chat_states[chat_id] = state
                        r_set = f"✅ मार्ग तय हुआ: *{from_code} ➔ {to_code}*" if lang == "hi" else f"✅ Route Set: *{from_code} ➔ {to_code}*"
                        await send_telegram_message(r_set, chat_id=chat_id)
                        await self._ask_date(chat_id)
                        return
                await self._ask_route(chat_id)
                return

            # Step B: In Date Selection
            if step in ["ASK_DATE", "ASK_DATE_MANUAL"]:
                parsed_d = parse_date_natural(text)
                if parsed_d:
                    state["data"]["journey_date"] = parsed_d
                    d_msg = f"✅ यात्रा की तारीख: *{parsed_d}*" if lang == "hi" else f"✅ Journey Date: *{parsed_d}*"
                    if state["data"].get("passengers"):
                        if state["data"].get("journey_class"):
                            state["step"] = "CONFIRM_SUMMARY"
                            user_chat_states[chat_id] = state
                            await send_telegram_message(d_msg, chat_id=chat_id)
                            await self._show_summary_and_confirm(chat_id)
                            return
                        else:
                            state["step"] = "ASK_CLASS"
                            user_chat_states[chat_id] = state
                            await send_telegram_message(d_msg, chat_id=chat_id)
                            await self._ask_class(chat_id)
                            return
                    else:
                        state["step"] = "ASK_PASSENGER_MANUAL"
                        user_chat_states[chat_id] = state
                        await send_telegram_message(d_msg, chat_id=chat_id)
                        await self._ask_passenger(chat_id)
                        return
                else:
                    if lang == "hi":
                        err_d = "⚠️ कृपया वैध तारीख लिखें (जैसे: `15 Oct`, `25/10/2026`, या `कल`) या नीचे दिए गए बटन पर टैप करें:"
                    elif lang == "en":
                        err_d = "⚠️ Please type a valid date (e.g. `15 Oct`, `25/10/2026`, or `Tomorrow`) or tap a button below:"
                    else:
                        err_d = "⚠️ Kripya valid date likhein (jaise: `15 Oct`, `25/10/2026`, ya `Kal`) ya neeche diye gaye button par tap karein:"
                    await send_telegram_message(err_d, chat_id=chat_id)
                    await self._ask_date(chat_id)
                    return

            # Step C: In Passenger Selection
            if step in ["ASK_PASSENGER", "ASK_PASSENGER_MANUAL"]:
                # 1. Did user enter a date instead of traveler name?
                potential_date = parse_date_natural(text)
                if potential_date:
                    state["data"]["journey_date"] = potential_date
                    state["step"] = "ASK_PASSENGER_MANUAL"
                    user_chat_states[chat_id] = state
                    if lang == "hi":
                        d_up = f"📅 *यात्रा की तारीख अपडेट की गई:* `{potential_date}`\n\nअब कृपया यात्री का नाम और उम्र लिखें (उदा. `Deepak 28 M`):"
                    elif lang == "en":
                        d_up = f"📅 *Journey Date updated:* `{potential_date}`\n\nNow please enter traveler name and age (e.g. `Deepak 28 M`):"
                    else:
                        d_up = f"📅 *Journey Date update ho gayi:* `{potential_date}`\n\nAb kripya passenger ka naam aur age likhein (jaise: `Deepak 28 M`):"
                    await send_telegram_message(d_up, chat_id=chat_id)
                    await self._ask_passenger(chat_id)
                    return

                # 2. Parse passenger details
                pax = parse_passenger_info(text)
                name_clean = pax.get("name", "").strip()
                lower_name = name_clean.lower()
                invalid_names = {
                    "tomorrow", "kal", "parso", "parson", "today", "aaj", "next week",
                    "cancel", "radd", "menu", "status", "pnr", "live", "train", "ticket",
                    "hi", "hii", "hello", "hey", "namaste", "yes", "no", "haan", "nahi"
                }

                is_valid = (
                    name_clean and
                    2 <= len(name_clean) <= 30 and
                    lower_name not in GREETING_WORDS and
                    not any(k in lower_name for k in invalid_names) and
                    not bool(re.search(r'\d{1,2}[/\-\.]\d{1,2}', lower_name)) and
                    any(c.isalpha() for c in name_clean)
                )

                if not is_valid:
                    if lang == "hi":
                        err_p = "⚠️ कृपया सही यात्री नाम और उम्र लिखें (उदा. `Deepak 28 M` या `Priya 25 F`):"
                    elif lang == "en":
                        err_p = "⚠️ Please type a valid traveler name & age (e.g. `Deepak 28 M` or `Priya 25 F`):"
                    else:
                        err_p = "⚠️ Kripya valid passenger name aur age likhein (jaise: `Deepak 28 M` ya `Priya 25 F`):"
                    await send_telegram_message(err_p, chat_id=chat_id)
                    await self._ask_passenger(chat_id)
                    return

                auto_save_passenger_to_db(pax)
                state["data"]["passengers"] = [pax]
                pax_ack = f"✅ यात्री जोड़ा गया: *{pax['name']}* ({pax['age']}/{pax['gender']})" if lang == "hi" else f"✅ Traveler Added: *{pax['name']}* ({pax['age']}/{pax['gender']})"
                if state["data"].get("journey_class"):
                    state["step"] = "CONFIRM_SUMMARY"
                    user_chat_states[chat_id] = state
                    await send_telegram_message(pax_ack, chat_id=chat_id)
                    await self._show_summary_and_confirm(chat_id)
                    return
                else:
                    state["step"] = "ASK_CLASS"
                    user_chat_states[chat_id] = state
                    await send_telegram_message(pax_ack, chat_id=chat_id)
                    await self._ask_class(chat_id)
                    return

            # Step D: In Class Selection
            if step in ["ASK_CLASS"]:
                cls = parse_class_natural(text)
                if cls:
                    state["data"]["journey_class"] = cls
                    state["step"] = "CONFIRM_SUMMARY"
                    user_chat_states[chat_id] = state
                    cls_ack = f"✅ श्रेणी चुनी गई: *{cls}*" if lang == "hi" else f"✅ Class Selected: *{cls}*"
                    await send_telegram_message(cls_ack, chat_id=chat_id)
                    await self._show_summary_and_confirm(chat_id)
                    return
                else:
                    await self._ask_class(chat_id)
                    return

            # Step E: In Summary Confirmation
            if step in ["CONFIRM_SUMMARY"]:
                if clean in ["yes", "haan", "ok", "confirm", "book", "हाँ"]:
                    await self._execute_telegram_booking(chat_id, state.get("data", {}))
                    user_chat_states.pop(chat_id, None)
                    return
                else:
                    await self._show_summary_and_confirm(chat_id)
                    return

        # -------------------------------------------------------------
        # 12. Smart Railway FAQs & Information Queries
        # -------------------------------------------------------------
        if "tatkal" in clean:
            if lang == "hi":
                t_info = (
                    "⚡ *IRCTC तत्काल बुकिंग समय (Tatkal Timings):*\n\n"
                    "• *AC Classes (1A, 2A, 3A, CC):* सुबह 10:00 AM से\n"
                    "• *Non-AC Classes (SL, 2S):* सुबह 11:00 AM से\n\n"
                    "तत्काल टिकट यात्रा से 1 दिन पहले खुलती है। क्या आप तत्काल टिकट बुक करना चाहते हैं?"
                )
                btn_txt = "🎫 तत्काल टिकट बुक करें"
            elif lang == "en":
                t_info = (
                    "⚡ *IRCTC Tatkal Booking Timings:*\n\n"
                    "• *AC Classes (1A, 2A, 3A, CC):* Opens at 10:00 AM\n"
                    "• *Non-AC Classes (SL, 2S):* Opens at 11:00 AM\n\n"
                    "Tatkal opens 1 day prior to journey date. Would you like to book now?"
                )
                btn_txt = "🎫 Book Tatkal Ticket"
            else:
                t_info = (
                    "⚡ *IRCTC Tatkal Booking Timings:*\n\n"
                    "• *AC Classes (1A, 2A, 3A, CC):* Subah 10:00 AM se shuru hoti hai\n"
                    "• *Non-AC Classes (SL, 2S):* Subah 11:00 AM se shuru hoti hai\n\n"
                    "Tatkal ticket travel date se 1 din pehle open hoti hai. Kya aap abhi book karna chahte hain?"
                )
                btn_txt = "🎫 Tatkal Ticket Book Karein"
            await send_telegram_message(t_info, chat_id=chat_id, reply_markup={"inline_keyboard": [[{"text": btn_txt, "callback_data": "cmd_book"}]]})
            return

        if any(k in clean for k in ["refund", "cancel rule", "radd niyam", "charges"]):
            if lang == "hi":
                r_info = (
                    "💰 *IRCTC रिफंड एवं रद्दीकरण नियम (Refund Rules):*\n\n"
                    "• चार्ट बनने से 4 घंटे पहले तक कन्फर्म टिकट रद्द करने पर क्लर्क शुल्क कटकर रिफंड मिलता है।\n"
                    "• RAC या वेटलिस्ट टिकट ट्रेन छूटने के 30 मिनट पहले तक रद्द की जा सकती है।\n"
                    "• रिफंड सीधे उसी खाते/UPI में 3-5 कार्य दिवसों में जमा होता है।"
                )
            elif lang == "en":
                r_info = (
                    "💰 *IRCTC Refund & Cancellation Guidelines:*\n\n"
                    "• Confirmed tickets can be cancelled up to 4 hours before chart preparation.\n"
                    "• RAC/Waitlisted tickets can be cancelled up to 30 mins before train departure.\n"
                    "• Refunds are credited directly to original payment method within 3-5 days."
                )
            else:
                r_info = (
                    "💰 *IRCTC Refund & Cancellation Rules:*\n\n"
                    "• Confirmed ticket chart banne se 4 ghante pehle cancel karne par standard deduction ke sath refund milta hai.\n"
                    "• RAC / Waitlist ticket train departure se 30 min pehle tak cancel ho sakti hai.\n"
                    "• Refund usi UPI/Account me 3-5 days me credit ho jata hai."
                )
            await send_telegram_message(
                r_info, 
                chat_id=chat_id, 
                reply_markup={"inline_keyboard": [[{"text": "🔍 PNR Status Check", "callback_data": "cmd_pnr"}, {"text": "🎫 Nayi Booking", "callback_data": "cmd_book"}]]}
            )
            return

        # -------------------------------------------------------------
        # 13. Default Fallback
        # -------------------------------------------------------------
        await self._send_welcome_menu(chat_id)

    async def _send_mode_menu(self, chat_id: str):
        lang = user_languages.get(chat_id, "hinglish")
        current_mode = "🛡️ Safe Mock Demo" if settings.DEMO_MODE else "🚀 Live Official IRCTC"
        if lang == "hi":
            text = (
                f"⚙️ *IRCTC ऑटोमेशन इंजन मोड*\n"
                f"═════════════════════════════════════\n"
                f"• वर्तमान मोड: *{current_mode}*\n\n"
                f"👉 *1. Live Official IRCTC Mode:* सीधे आधिकारिक IRCTC वेबसाइट (irctc.co.in) पर ब्राउज़र खोलकर तत्काल/सामान्य बुकिंग करता है। असली CAPTCHA और UPI QR सीधे आपके फ़ोन पर आते हैं।\n"
                f"👉 *2. Safe Demo Mode:* पूरी प्रक्रिया को सुरक्षित सिम्युलेटेड डेटा के साथ चलाता है (परीक्षण के लिए)।\n\n"
                f"कृपया अपना पसंदीदा मोड चुनें:"
            )
            btn_live = "🚀 असली IRCTC मोड चालू करें"
            btn_demo = "🛡️ सेफ डेमो मोड चालू करें"
            btn_menu = "🔙 मुख्य मेनू"
        elif lang == "en":
            text = (
                f"⚙️ *IRCTC Automation Engine Mode*\n"
                f"═════════════════════════════════════\n"
                f"• Current Mode: *{current_mode}*\n\n"
                f"👉 *1. Live Official IRCTC Mode:* Directly automates official IRCTC portal (irctc.co.in). Delivers live CAPTCHA & UPI QR to Telegram.\n"
                f"👉 *2. Safe Demo Mode:* Runs end-to-end booking in a safe simulated sandbox for testing.\n\n"
                f"Please choose your preferred execution mode:"
            )
            btn_live = "🚀 Switch to Live IRCTC"
            btn_demo = "🛡️ Switch to Demo Mode"
            btn_menu = "🔙 Main Menu"
        else:
            text = (
                f"⚙️ *Automation Engine Mode*\n"
                f"═════════════════════════════════════\n"
                f"• Abhi ka Mode: *{current_mode}*\n\n"
                f"👉 *1. Live Official IRCTC Mode:* Real IRCTC website (irctc.co.in) par browser khol kar booking karta hai. Real CAPTCHA aur payment QR Telegram par aate hain.\n"
                f"👉 *2. Safe Demo Mode:* Safe testing ke liye simulated booking run karta hai.\n\n"
                f"Kripya apna execution mode chunein:"
            )
            btn_live = "🚀 Switch to Live IRCTC"
            btn_demo = "🛡️ Switch to Demo Mode"
            btn_menu = "🔙 Main Menu"

        keyboard = {
            "inline_keyboard": [
                [{"text": btn_live, "callback_data": "setmode_live"}],
                [{"text": btn_demo, "callback_data": "setmode_demo"}],
                [{"text": btn_menu, "callback_data": "cmd_menu"}]
            ]
        }
        await send_telegram_message(text, chat_id=chat_id, reply_markup=keyboard)

    async def _send_credentials_info(self, chat_id: str):
        lang = user_languages.get(chat_id, "hinglish")
        u_display = settings.IRCTC_USERNAME or "Not Configured (सेट नहीं है)"
        p_display = "****** (Saved in .env)" if settings.IRCTC_PASSWORD else "Not Configured (सेट नहीं है)"

        if lang == "hi":
            info_msg = (
                "🔐 *IRCTC आधिकारिक खाता साख (Credentials):*\n"
                "═════════════════════════════════════\n"
                f"• *उपयोगकर्ता नाम (User ID):* `{u_display}`\n"
                f"• *पासवर्ड:* `{p_display}`\n\n"
                "👉 *नया ID / Password सुरक्षित रूप से सेव करने के लिए:*\n"
                "चैट में इस प्रकार लिखकर भेजें:\n"
                "`/credentials आपका_IRCTC_USER_ID आपका_PASSWORD`\n\n"
                "🛡️ यह आपकी लोकल `.env` फ़ाइल में सुरक्षित रहेगा और IRCTC लॉगिन के समय स्वतः भर जाएगा।"
            )
        elif lang == "en":
            info_msg = (
                "🔐 *Official IRCTC Credentials Profile:*\n"
                "═════════════════════════════════════\n"
                f"• *Username / ID:* `{u_display}`\n"
                f"• *Password:* `{p_display}`\n\n"
                "👉 *To set or update your credentials:*\n"
                "Send in chat as:\n"
                "`/credentials YOUR_USER_ID YOUR_PASSWORD`\n\n"
                "🛡️ This is stored securely in your local `.env` and auto-filled during IRCTC login."
            )
        else:
            info_msg = (
                "🔐 *IRCTC Account Credentials:*\n"
                "═════════════════════════════════════\n"
                f"• *User ID:* `{u_display}`\n"
                f"• *Password:* `{p_display}`\n\n"
                "👉 *ID / Password set karne ke liye:*\n"
                "Chat me aise likh kar bhejein:\n"
                "`/credentials YOUR_USER_ID YOUR_PASSWORD`\n\n"
                "🛡️ Ye local `.env` me safely save ho jayega aur login screen par auto-fill hoga."
            )

        menu_btn = {"inline_keyboard": [[{"text": "🔙 Main Menu", "callback_data": "cmd_menu"}]]}
        await send_telegram_message(info_msg, chat_id=chat_id, reply_markup=menu_btn)

    async def _send_welcome_menu(self, chat_id: str):
        lang = user_languages.get(chat_id, "hinglish")
        mode_label = "🚀 Live IRCTC" if not settings.DEMO_MODE else "🛡️ Demo Mode"

        if lang == "hi":
            welcome = (
                "🚆 *IRCTC (Indian Railway Catering and Tourism Corporation)*\n"
                "═════════════════════════════════════\n"
                "✨ *पर्सनल फास्ट-ट्रैक टिकट बुकिंग सहायक*\n\n"
                "आप अपने मोबाइल से बटन दबाकर या चैट में लिखकर तुरंत टिकट बुक कर सकते हैं।\n"
                "जब भी IRCTC में CAPTCHA आएगा, बॉट आपको उसकी फोटो भेजेगा और आप यहीं उत्तर लिख सकेंगे!\n\n"
                "⚡ *एक ही संदेश में त्वरित बुकिंग (One-Shot Booking):*\n"
                "आप एक ही मैसेज में पूरी यात्रा का विवरण लिखकर भेज सकते हैं, जैसे:\n"
                "`Delhi to Varanasi 15 oct Deepak 28 M 3A`\n"
                "या `NDLS se BSB kal Deepak 3A me book kardo`\n\n"
                "👉 *नीचे दिए गए बटनों पर टैप करें या चैट में लिखें:*"
            )
            buttons = [
                [{"text": "🎫 नई टिकट बुक करें", "callback_data": "cmd_book"}],
                [{"text": "🔍 PNR स्टेटस चेक", "callback_data": "cmd_pnr"}, {"text": "📍 लाइव ट्रेन स्थिति", "callback_data": "cmd_live_train"}],
                [{"text": "🔄 वर्तमान स्थिति", "callback_data": "cmd_status"}, {"text": f"⚙️ मोड: {mode_label}", "callback_data": "cmd_mode"}],
                [{"text": "👥 सहेजे गए यात्री", "callback_data": "cmd_passengers"}, {"text": "📍 मुख्य मार्ग (Routes)", "callback_data": "cmd_routes"}],
                [{"text": "🌐 भाषा बदलें (Language)", "callback_data": "cmd_lang"}, {"text": "❌ रद्द करें", "callback_data": "cmd_cancel"}]
            ]
        elif lang == "en":
            welcome = (
                "🚆 *IRCTC (Indian Railway Catering and Tourism Corporation)*\n"
                "═════════════════════════════════════\n"
                "✨ *Personal Fast-Track Ticket Booking Assistant*\n\n"
                "You can book train tickets effortlessly using interactive buttons or natural chat.\n"
                "When IRCTC asks for a CAPTCHA, the bot will send you the photo right here for a quick reply!\n\n"
                "⚡ *One-Shot Direct Booking:*\n"
                "You can send your entire booking request in a single message, e.g.:\n"
                "`Delhi to Varanasi 15 oct Deepak 28 M 3A`\n"
                "or `NDLS to BSB tomorrow Deepak 3A`\n\n"
                "👉 *Tap the buttons below or chat directly:*"
            )
            buttons = [
                [{"text": "🎫 Book New Ticket", "callback_data": "cmd_book"}],
                [{"text": "🔍 Check PNR Status", "callback_data": "cmd_pnr"}, {"text": "📍 Live Train Status", "callback_data": "cmd_live_train"}],
                [{"text": "🔄 Current Status", "callback_data": "cmd_status"}, {"text": f"⚙️ Mode: {mode_label}", "callback_data": "cmd_mode"}],
                [{"text": "👥 Saved Passengers", "callback_data": "cmd_passengers"}, {"text": "📍 Popular Routes", "callback_data": "cmd_routes"}],
                [{"text": "🌐 Change Language", "callback_data": "cmd_lang"}, {"text": "❌ Cancel Request", "callback_data": "cmd_cancel"}]
            ]
        else:  # Hinglish
            welcome = (
                "🚆 *IRCTC (Indian Railway Catering and Tourism Corporation)*\n"
                "═════════════════════════════════════\n"
                "✨ *Personal Fast-Track Ticket Booking Assistant*\n\n"
                "Aap apne phone se button click karke ya text chat me likh kar ticket book kar sakte hain.\n"
                "Jab bhi CAPTCHA aayega, bot aapko photo bhejega aur aap yahi text reply kar denge!\n\n"
                "⚡ *One-Shot Direct Booking:*\n"
                "Aap ek hi message me direct booking request bhej sakte hain, jaise:\n"
                "`Delhi to Varanasi 15 oct Deepak 28 M 3A`\n"
                "ya `NDLS se BSB kal Deepak 3A me book kardo`\n\n"
                "👉 *Neeche diye gaye buttons par tap karein ya chat me likhein:*"
            )
            buttons = [
                [{"text": "🎫 Nayi Ticket Book Karein", "callback_data": "cmd_book"}],
                [{"text": "🔍 PNR Status Check", "callback_data": "cmd_pnr"}, {"text": "📍 Live Train Status", "callback_data": "cmd_live_train"}],
                [{"text": "🔄 Current Status", "callback_data": "cmd_status"}, {"text": f"⚙️ Mode: {mode_label}", "callback_data": "cmd_mode"}],
                [{"text": "👥 Saved Passengers", "callback_data": "cmd_passengers"}, {"text": "📍 Saved Routes", "callback_data": "cmd_routes"}],
                [{"text": "🌐 Bhasha Badlein (Language)", "callback_data": "cmd_lang"}, {"text": "❌ Cancel Request", "callback_data": "cmd_cancel"}]
            ]
        await send_telegram_message(welcome, chat_id=chat_id, reply_markup={"inline_keyboard": buttons})

    async def _lookup_and_send_pnr(self, chat_id: str, pnr_input: str):
        lang = user_languages.get(chat_id, "hinglish")
        pnr_clean = re.sub(r'\D', '', pnr_input.strip())
        if len(pnr_clean) != 10:
            err_msg = "⚠️ PNR नंबर ठीक 10 अंकों का होना चाहिए। कृपया पुनः प्रयास करें।" if lang == "hi" else ("⚠️ PNR must be exactly 10 digits. Please try again." if lang == "en" else "⚠️ PNR number exact 10 digits ka hona chahiye. Kripya dobara try karein.")
            await send_telegram_message(err_msg, chat_id=chat_id)
            return

        loading = "🔄 PNR स्थिति जांची जा रही है..." if lang == "hi" else ("🔄 Fetching live PNR status..." if lang == "en" else "🔄 Live PNR status fetch ho raha hai...")
        await send_telegram_message(loading, chat_id=chat_id)

        data = await railway_service.get_pnr_status(pnr_clean)
        msg = railway_service.format_pnr_message(data, lang=lang)

        btn_refresh = "🔄 रिफ्रेश (Refresh)" if lang == "hi" else ("🔄 Refresh" if lang == "en" else "🔄 Refresh")
        btn_track = "📍 ट्रेन ट्रैक करें" if lang == "hi" else ("📍 Track Train Live" if lang == "en" else "📍 Train Track Karein")
        btn_book = "🎫 टिकट बुक करें" if lang == "hi" else ("🎫 Book Ticket" if lang == "en" else "🎫 Nayi Booking")
        btn_menu = "🔙 मुख्य मेनू" if lang == "hi" else ("🔙 Main Menu" if lang == "en" else "🔙 Main Menu")

        keyboard = {
            "inline_keyboard": [
                [
                    {"text": btn_refresh, "callback_data": f"pnr_refresh_{pnr_clean}"},
                    {"text": btn_track, "callback_data": f"live_train_{data.get('train_number', '12952')}"}
                ],
                [
                    {"text": btn_book, "callback_data": "cmd_book"},
                    {"text": btn_menu, "callback_data": "cmd_menu"}
                ]
            ]
        }
        await send_telegram_message(msg, chat_id=chat_id, reply_markup=keyboard)

    async def _lookup_and_send_live_train(self, chat_id: str, train_input: str):
        lang = user_languages.get(chat_id, "hinglish")
        train_clean = re.sub(r'\D', '', train_input.strip())
        if len(train_clean) < 4 or len(train_clean) > 5:
            err_msg = "⚠️ ट्रेन नंबर 5 अंकों का होना चाहिए (उदा. 12952, 22436)।" if lang == "hi" else ("⚠️ Train number must be 5 digits (e.g. 12952, 22436)." if lang == "en" else "⚠️ Train number 5 digits ka hona chahiye (e.g. 12952, 22436).")
            await send_telegram_message(err_msg, chat_id=chat_id)
            return

        loading = "🔄 लाइव ट्रेन स्थिति लोड हो रही है..." if lang == "hi" else ("🔄 Loading live train location..." if lang == "en" else "🔄 Live train location load ho rahi hai...")
        await send_telegram_message(loading, chat_id=chat_id)

        data = await railway_service.get_live_train_status(train_clean)
        msg = railway_service.format_live_train_message(data, lang=lang)

        btn_refresh = "🔄 रिफ्रेश (Refresh)" if lang == "hi" else ("🔄 Refresh" if lang == "en" else "🔄 Refresh")
        btn_pnr = "🔍 PNR स्टेटस" if lang == "hi" else ("🔍 PNR Status" if lang == "en" else "🔍 PNR Status")
        btn_menu = "🔙 मुख्य मेनू" if lang == "hi" else ("🔙 Main Menu" if lang == "en" else "🔙 Main Menu")

        keyboard = {
            "inline_keyboard": [
                [
                    {"text": btn_refresh, "callback_data": f"live_refresh_{train_clean}"},
                    {"text": btn_pnr, "callback_data": "cmd_pnr"}
                ],
                [
                    {"text": btn_menu, "callback_data": "cmd_menu"}
                ]
            ]
        }
        await send_telegram_message(msg, chat_id=chat_id, reply_markup=keyboard)

    async def _handle_cancel(self, chat_id: str):
        lang = user_languages.get(chat_id, "hinglish")
        user_chat_states.pop(chat_id, None)
        clear_all_waiting_sessions()
        btn_new = "🎫 नई टिकट बुक करें" if lang == "hi" else ("🎫 Book New Ticket" if lang == "en" else "🎫 Nayi Booking Shuru Karein")
        btn_menu = "🏠 मुख्य मेनू" if lang == "hi" else ("🏠 Main Menu" if lang == "en" else "🏠 Main Menu")
        keyboard = {"inline_keyboard": [[{"text": btn_new, "callback_data": "cmd_book"}, {"text": btn_menu, "callback_data": "cmd_menu"}]]}
        msg = "❌ सक्रिय बुकिंग सत्र और अनुरोध रद्द कर दिए गए हैं।" if lang == "hi" else ("❌ Active booking sessions and requests have been cancelled." if lang == "en" else "❌ Active booking session aur requests cancel kar diye gaye hain.")
        await send_telegram_message(msg, chat_id=chat_id, reply_markup=keyboard)

    async def _send_status(self, chat_id: str):
        lang = user_languages.get(chat_id, "hinglish")
        waiting_session = get_latest_waiting_session()
        btn_refresh = "🔄 स्थिति ताज़ा करें" if lang == "hi" else ("🔄 Refresh Status" if lang == "en" else "🔄 Refresh Status")
        btn_cancel = "❌ बुकिंग रद्द करें" if lang == "hi" else ("❌ Cancel Booking" if lang == "en" else "❌ Cancel Booking")
        btn_new = "🎫 नई टिकट बुक करें" if lang == "hi" else ("🎫 Book New Ticket" if lang == "en" else "🎫 Nayi Ticket Book Karein")

        if waiting_session:
            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": btn_refresh, "callback_data": "cmd_status"},
                        {"text": btn_cancel, "callback_data": "action_cancel"}
                    ]
                ]
            }
            title = "🔄 *सक्रिय बुकिंग:*" if lang == "hi" else ("🔄 *Active Booking:*" if lang == "en" else "🔄 *Active Booking:*")
            await send_telegram_message(
                f"{title} `{waiting_session.booking_ref}`\n"
                f"*Status:* `{waiting_session.status}`\n"
                f"*Stage:* `{waiting_session.stage}`\n"
                f"*Prompt:* {waiting_session.manual_prompt or 'Processing...'}",
                chat_id=chat_id,
                reply_markup=keyboard
            )
        else:
            db = SessionLocal()
            recent_b = db.query(Booking).order_by(Booking.id.desc()).first()
            db.close()

            if recent_b:
                btn_pdf_t = "📄 टिकट PDF (Download)" if lang == "hi" else ("📄 Ticket PDF" if lang == "en" else "📄 Ticket PDF")
                btn_pdf_i = "🧾 बिल / इनवॉइस PDF" if lang == "hi" else ("🧾 Invoice / Bill PDF" if lang == "en" else "🧾 Bill / Invoice PDF")
                keyboard = {
                    "inline_keyboard": [
                        [
                            {"text": btn_pdf_t, "callback_data": f"get_ticket_{recent_b.id}"},
                            {"text": btn_pdf_i, "callback_data": f"get_invoice_{recent_b.id}"}
                        ],
                        [
                            {"text": btn_new, "callback_data": "cmd_book"}
                        ]
                    ]
                }
                j_date_str = recent_b.journey_date.strftime("%d/%m/%Y") if recent_b.journey_date else "N/A"
                if lang == "hi":
                    stat_msg = (
                        f"📊 *नवीनतम बुकिंग स्थिति:*\n"
                        f"═════════════════════════════════════\n"
                        f"• संदर्भ संख्या (Ref): `{recent_b.booking_ref}`\n"
                        f"• स्थिति (Status): *{recent_b.status}*\n"
                        f"• PNR: `{recent_b.pnr or 'N/A'}`\n"
                        f"• मार्ग: *{recent_b.from_station} ➔ {recent_b.to_station}*\n"
                        f"• यात्रा तारीख: *{j_date_str}* | श्रेणी: *{recent_b.journey_class}*\n"
                        f"• कुल किराया: *Rs. {recent_b.fare or 0:,.2f} (₹{recent_b.fare or 0:,.2f})*\n\n"
                        f"📥 आप नीचे दिए गए बटनों से अपना टिकट या बिल PDF डाउनलोड कर सकते हैं:"
                    )
                elif lang == "en":
                    stat_msg = (
                        f"📊 *Latest Booking Status:*\n"
                        f"═════════════════════════════════════\n"
                        f"• Booking Ref: `{recent_b.booking_ref}`\n"
                        f"• Status: *{recent_b.status}*\n"
                        f"• PNR: `{recent_b.pnr or 'N/A'}`\n"
                        f"• Route: *{recent_b.from_station} ➔ {recent_b.to_station}*\n"
                        f"• Journey Date: *{j_date_str}* | Class: *{recent_b.journey_class}*\n"
                        f"• Fare: *Rs. {recent_b.fare or 0:,.2f} (₹{recent_b.fare or 0:,.2f})*\n\n"
                        f"📥 You can download your Ticket PDF or Invoice Bill PDF below:"
                    )
                else:
                    stat_msg = (
                        f"📊 *Latest Booking Status:*\n"
                        f"═════════════════════════════════════\n"
                        f"• Booking Ref: `{recent_b.booking_ref}`\n"
                        f"• Status: *{recent_b.status}*\n"
                        f"• PNR: `{recent_b.pnr or 'N/A'}`\n"
                        f"• Route: *{recent_b.from_station} ➔ {recent_b.to_station}*\n"
                        f"• Journey Date: *{j_date_str}* | Class: *{recent_b.journey_class}*\n"
                        f"• Fare: *Rs. {recent_b.fare or 0:,.2f} (₹{recent_b.fare or 0:,.2f})*\n\n"
                        f"📥 Aap neeche diye gaye buttons se Ticket PDF ya Bill PDF download kar sakte hain:"
                    )
                await send_telegram_message(stat_msg, chat_id=chat_id, reply_markup=keyboard)
            else:
                keyboard = {"inline_keyboard": [[{"text": btn_new, "callback_data": "cmd_book"}]]}
                no_active = "✅ *कोई सक्रिय बुकिंग प्रगति पर नहीं है।*" if lang == "hi" else ("✅ *No active booking in progress.*" if lang == "en" else "✅ *Koi active booking in-progress nahi hai.*")
                await send_telegram_message(no_active, chat_id=chat_id, reply_markup=keyboard)

    async def _send_booking_ticket_pdf(self, chat_id: str, booking_id: Optional[int] = None):
        lang = user_languages.get(chat_id, "hinglish")
        db = SessionLocal()
        try:
            if booking_id:
                booking = db.query(Booking).filter(Booking.id == booking_id).first()
            else:
                booking = db.query(Booking).order_by(Booking.id.desc()).first()

            if not booking:
                msg = "⚠️ कोई बुकिंग रिकॉर्ड नहीं मिला।" if lang == "hi" else ("⚠️ No booking record found." if lang == "en" else "⚠️ Koi booking record nahi mila.")
                await send_telegram_message(msg, chat_id=chat_id)
                return

            passengers = db.query(BookingPassenger).filter(BookingPassenger.booking_id == booking.id).all()
            b_dict = {
                "pnr": booking.pnr or "2451234567",
                "train_number": booking.train_number or "12952",
                "train_name": booking.train_name or "Rajdhani Express",
                "from_station": booking.from_station,
                "to_station": booking.to_station,
                "journey_date": booking.journey_date.strftime("%d/%m/%Y") if booking.journey_date else "",
                "journey_class": booking.journey_class,
                "quota": booking.quota or "GENERAL (GN)",
                "fare": booking.fare or 1450.0,
                "booking_ref": booking.booking_ref,
                "booking_time": booking.created_at.strftime("%d-%b-%Y %H:%M:%S") if booking.created_at else ""
            }
            pax_list = [
                {
                    "name": p.name,
                    "age": p.age,
                    "gender": p.gender,
                    "allocated_seat": p.allocated_seat or "B4-45 [MB]",
                    "status": p.status or "CNF"
                }
                for p in passengers
            ]
            pdf_bytes = pdf_service.generate_ticket_pdf(b_dict, pax_list, save_to_disk=True)
            pnr_val = booking.pnr or booking.booking_ref
            caption = "🎫 *IRCTC ई-टिकट (ERS) PDF संलग्न है। शुभ यात्रा!*" if lang == "hi" else ("🎫 *Official IRCTC Train Ticket (ERS) PDF is attached. Safe journey!*" if lang == "en" else "🎫 *IRCTC E-Ticket (ERS) PDF attach kar diya gaya hai. Happy Journey!*")
            await send_telegram_document(
                document_bytes=pdf_bytes,
                filename=f"IRCTC_Ticket_{pnr_val}.pdf",
                caption=caption,
                chat_id=chat_id
            )
        finally:
            db.close()

    async def _send_booking_invoice_pdf(self, chat_id: str, booking_id: Optional[int] = None):
        lang = user_languages.get(chat_id, "hinglish")
        db = SessionLocal()
        try:
            if booking_id:
                booking = db.query(Booking).filter(Booking.id == booking_id).first()
            else:
                booking = db.query(Booking).order_by(Booking.id.desc()).first()

            if not booking:
                msg = "⚠️ कोई बिल / इनवॉइस रिकॉर्ड नहीं मिला।" if lang == "hi" else ("⚠️ No invoice record found." if lang == "en" else "⚠️ Koi invoice record nahi mila.")
                await send_telegram_message(msg, chat_id=chat_id)
                return

            passengers = db.query(BookingPassenger).filter(BookingPassenger.booking_id == booking.id).all()
            b_dict = {
                "pnr": booking.pnr or "2451234567",
                "train_number": booking.train_number or "12952",
                "train_name": booking.train_name or "Rajdhani Express",
                "from_station": booking.from_station,
                "to_station": booking.to_station,
                "journey_date": booking.journey_date.strftime("%d/%m/%Y") if booking.journey_date else "",
                "journey_class": booking.journey_class,
                "quota": booking.quota or "GENERAL (GN)",
                "fare": booking.fare or 1450.0,
                "booking_ref": booking.booking_ref,
                "booking_time": booking.created_at.strftime("%d-%b-%Y %H:%M:%S") if booking.created_at else ""
            }
            pax_list = [
                {
                    "name": p.name,
                    "age": p.age,
                    "gender": p.gender,
                    "allocated_seat": p.allocated_seat or "B4-45 [MB]",
                    "status": p.status or "CNF"
                }
                for p in passengers
            ]
            pdf_bytes = pdf_service.generate_invoice_pdf(b_dict, pax_list, save_to_disk=True)
            caption = "🧾 *यात्रा बुकिंग का टैक्स इनवॉइस / बिल PDF संलग्न है।*" if lang == "hi" else ("🧾 *Travel Booking Tax Invoice / Bill PDF is attached.*" if lang == "en" else "🧾 *Aapki booking ka Tax Invoice / Bill PDF attach kar diya gaya hai.*")
            await send_telegram_document(
                document_bytes=pdf_bytes,
                filename=f"Invoice_Bill_{booking.booking_ref}.pdf",
                caption=caption,
                chat_id=chat_id
            )
        finally:
            db.close()

    async def _send_passengers(self, chat_id: str):
        lang = user_languages.get(chat_id, "hinglish")
        db = SessionLocal()
        pax_list = db.query(Passenger).all()
        db.close()

        btn_book = "🎫 इन यात्रियों के साथ बुक करें" if lang == "hi" else ("🎫 Book With Travelers" if lang == "en" else "🎫 In Travelers Ke Saath Book Karein")
        btn_menu = "🏠 मुख्य मेनू" if lang == "hi" else ("🏠 Main Menu" if lang == "en" else "🏠 Main Menu")
        btn_start = "🎫 नई बुकिंग शुरू करें" if lang == "hi" else ("🎫 Start New Booking" if lang == "en" else "🎫 Nayi Booking Shuru Karein")

        if not pax_list:
            keyboard = {
                "inline_keyboard": [
                    [{"text": btn_start, "callback_data": "cmd_book"}],
                    [{"text": btn_menu, "callback_data": "cmd_menu"}]
                ]
            }
            if lang == "hi":
                msg = (
                    "👥 *सहेजे गए यात्री:*\nअभी कोई सहेजा गया यात्री नहीं है।\n\n"
                    "💡 *नया यात्री कैसे जोड़ें?*\nचैट में सीधे नाम लिखें (जैसे: `Deepak 28 M`), वह स्वतः सहेज लिया जाएगा!"
                )
            elif lang == "en":
                msg = (
                    "👥 *Saved Travelers:*\nNo saved travelers found yet.\n\n"
                    "💡 *How to add?*\nDirectly send a message with details (e.g.: `Deepak 28 M`) and it will be auto-saved!"
                )
            else:
                msg = (
                    "👥 *Saved Passengers:*\nAbhi koi saved traveler nahi hai.\n\n"
                    "💡 *Kaise add karein?*\nAap chat me seedha naam likh kar bhej sakte hain (jaise: `Deepak 28 M`), wo automatically save ho jayega!"
                )
            await send_telegram_message(msg, chat_id=chat_id, reply_markup=keyboard)
        else:
            lines = [f"• *{p.name}* ({p.age}/{p.gender}) - Pref: {p.berth_preference}" for p in pax_list]
            keyboard = {
                "inline_keyboard": [
                    [{"text": btn_book, "callback_data": "cmd_book"}],
                    [{"text": btn_menu, "callback_data": "cmd_menu"}]
                ]
            }
            title = "👥 *सहेजे गए यात्री प्रोफाइल:*" if lang == "hi" else ("👥 *Saved Passenger Profiles:*" if lang == "en" else "👥 *Saved Passenger Profiles:*")
            await send_telegram_message(f"{title}\n" + "\n".join(lines), chat_id=chat_id, reply_markup=keyboard)

    async def _send_routes(self, chat_id: str):
        lang = user_languages.get(chat_id, "hinglish")
        db = SessionLocal()
        routes = db.query(SavedJourney).all()
        db.close()
        btn_menu = "🏠 मुख्य मेनू" if lang == "hi" else ("🏠 Main Menu" if lang == "en" else "🏠 Main Menu")
        if not routes:
            keyboard = {"inline_keyboard": [[{"text": btn_menu, "callback_data": "cmd_menu"}]]}
            await send_telegram_message("Koi saved route nahi hai.", chat_id=chat_id, reply_markup=keyboard)
        else:
            buttons = []
            for r in routes:
                buttons.append([{"text": f"🚀 {r.label} ({r.from_station} ➔ {r.to_station})", "callback_data": f"route_{r.from_station}_{r.to_station}"}])
            buttons.append([{"text": btn_menu, "callback_data": "cmd_menu"}])
            if lang == "hi":
                title = "📍 *भारत के मुख्य लोकप्रिय रेल मार्ग:*\nनीचे किसी भी मार्ग पर टैप करें या चैट में नया मार्ग लिखें:"
            elif lang == "en":
                title = "📍 *Top Popular Train Routes of India:*\nTap any route below or type a custom route in chat:"
            else:
                title = "📍 *Top Popular Routes of India:*\nNeeche kisi bhi route par tap karein ya chat me naya route likhein:"
            await send_telegram_message(title, chat_id=chat_id, reply_markup={"inline_keyboard": buttons})

    async def _ask_route(self, chat_id: str):
        lang = user_languages.get(chat_id, "hinglish")
        db = SessionLocal()
        saved = db.query(SavedJourney).limit(4).all()
        db.close()

        buttons = []
        for r in saved:
            buttons.append([{"text": f"📍 {r.label} ({r.from_station} ➔ {r.to_station})", "callback_data": f"route_{r.from_station}_{r.to_station}"}])
        cancel_txt = "❌ रद्द करें" if lang == "hi" else "❌ Cancel"
        buttons.append([{"text": cancel_txt, "callback_data": "cancel_book"}])

        keyboard = {"inline_keyboard": buttons}
        user_chat_states[chat_id] = {"step": "ASK_ROUTE_MANUAL", "data": {}}

        if lang == "hi":
            msg = (
                "🚆 *कहाँ से कहाँ यात्रा करनी है?*\n\n"
                "👉 *विकल्प 1 (बटन):* नीचे दिया गया मुख्य मार्ग चुनें।\n"
                "💬 *विकल्प 2 (चैट):* सीधे लिखें, जैसे:\n"
                "`Delhi to Varanasi` या `NDLS to BSB`"
            )
        elif lang == "en":
            msg = (
                "🚆 *Where would you like to travel?*\n\n"
                "👉 *Option 1 (Buttons):* Select a popular route below.\n"
                "💬 *Option 2 (Chat):* Type origin and destination, e.g.:\n"
                "`Delhi to Varanasi` or `NDLS to BSB`"
            )
        else:
            msg = (
                "🚆 *Kahan se kahan travel karna hai?*\n\n"
                "👉 *Option 1 (Button):* Neeche popular route select karein.\n"
                "💬 *Option 2 (Manual Chat):* Seedha likhein, jaise:\n"
                "`Delhi to Varanasi` ya `NDLS to BSB`"
            )
        await send_telegram_message(msg, chat_id=chat_id, reply_markup=keyboard)

    async def _ask_date(self, chat_id: str):
        lang = user_languages.get(chat_id, "hinglish")
        today = date.today()
        d1 = (today + timedelta(days=1)).strftime("%d/%m")
        d2 = (today + timedelta(days=2)).strftime("%d/%m")
        d7 = (today + timedelta(days=7)).strftime("%d/%m")

        if lang == "hi":
            t_d1, t_d2, t_d7, cancel_txt = f"कल ({d1})", f"परसों ({d2})", f"अगले हफ्ते ({d7})", "❌ रद्द करें"
            msg = (
                "📅 *यात्रा की तारीख क्या है?*\n\n"
                "👉 *विकल्प 1 (बटन):* त्वरित तारीख चुनें।\n"
                "💬 *विकल्प 2 (चैट):* तारीख लिखें जैसे: `15 Oct`, `25/10/2026`, या `कल`"
            )
        elif lang == "en":
            t_d1, t_d2, t_d7, cancel_txt = f"Tomorrow ({d1})", f"Day After ({d2})", f"Next Week ({d7})", "❌ Cancel"
            msg = (
                "📅 *What is your journey date?*\n\n"
                "👉 *Option 1 (Buttons):* Tap a quick date button.\n"
                "💬 *Option 2 (Chat):* Type date, e.g.: `15 Oct`, `25/10/2026`, or `Tomorrow`"
            )
        else:
            t_d1, t_d2, t_d7, cancel_txt = f"Kal ({d1})", f"Parso ({d2})", f"Next Week ({d7})", "❌ Cancel"
            msg = (
                "📅 *Journey Date kya hai?*\n\n"
                "👉 *Option 1 (Button):* Quick date button dabayein.\n"
                "💬 *Option 2 (Manual Chat):* Date likhein jaise: `15 Oct`, `25/10/2026`, ya `Kal`"
            )

        keyboard = {
            "inline_keyboard": [
                [
                    {"text": t_d1, "callback_data": "date_1"},
                    {"text": t_d2, "callback_data": "date_2"},
                    {"text": t_d7, "callback_data": "date_7"}
                ],
                [
                    {"text": cancel_txt, "callback_data": "cancel_book"}
                ]
            ]
        }
        if chat_id not in user_chat_states:
            user_chat_states[chat_id] = {"step": "ASK_DATE_MANUAL", "data": {}}
        else:
            user_chat_states[chat_id]["step"] = "ASK_DATE_MANUAL"
        await send_telegram_message(msg, chat_id=chat_id, reply_markup=keyboard)

    async def _ask_passenger(self, chat_id: str):
        lang = user_languages.get(chat_id, "hinglish")
        db = SessionLocal()
        saved_pax = db.query(Passenger).limit(6).all()
        db.close()

        buttons = []
        for p in saved_pax:
            clean_name = p.name[:24]
            buttons.append([{"text": f"👤 {clean_name} ({p.age}/{p.gender})", "callback_data": f"pax_id_{p.id}"}])
        cancel_txt = "❌ रद्द करें" if lang == "hi" else "❌ Cancel"
        buttons.append([{"text": cancel_txt, "callback_data": "cancel_book"}])

        keyboard = {"inline_keyboard": buttons}
        if chat_id not in user_chat_states:
            user_chat_states[chat_id] = {"step": "ASK_PASSENGER_MANUAL", "data": {}}
        else:
            user_chat_states[chat_id]["step"] = "ASK_PASSENGER_MANUAL"

        if lang == "hi":
            if saved_pax:
                msg = (
                    "👥 *यात्री विवरण (Traveler Details):*\n\n"
                    "👉 *विकल्प 1 (बटन):* नीचे सहेजे गए यात्री पर टैप करें।\n"
                    "💬 *विकल्प 2 (चैट):* नया यात्री विवरण लिखें जैसे:\n"
                    "`Deepak 28 M` (यह स्वतः सहेज लिया जाएगा)"
                )
            else:
                msg = (
                    "👥 *यात्री विवरण (Traveler Details):*\n\n"
                    "💬 चैट में यात्री का नाम और उम्र लिखें:\n"
                    "जैसे: `Deepak 28 M` या `Priya 25 F`\n"
                    "(यह स्वतः आपके खाते में सहेज लिया जाएगा!)"
                )
        elif lang == "en":
            if saved_pax:
                msg = (
                    "👥 *Who is traveling? (Traveler Details)*\n\n"
                    "👉 *Option 1 (Buttons):* Tap a saved traveler below.\n"
                    "💬 *Option 2 (Chat):* Type traveler name and age, e.g.:\n"
                    "`Deepak 28 M` (will be auto-saved)"
                )
            else:
                msg = (
                    "👥 *Who is traveling? (Traveler Details)*\n\n"
                    "💬 Type traveler details in chat:\n"
                    "e.g.: `Deepak 28 M` or `Priya 25 F`\n"
                    "(This traveler will be automatically saved!)"
                )
        else:
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
        lang = user_languages.get(chat_id, "hinglish")
        cancel_txt = "❌ रद्द करें" if lang == "hi" else "❌ Cancel"
        keyboard = {
            "inline_keyboard": [
                [{"text": "AC 3 Tier (3A)", "callback_data": "class_3A"}, {"text": "AC 2 Tier (2A)", "callback_data": "class_2A"}],
                [{"text": "Sleeper (SL)", "callback_data": "class_SL"}, {"text": "Chair Car (CC)", "callback_data": "class_CC"}],
                [{"text": cancel_txt, "callback_data": "cancel_book"}]
            ]
        }
        if lang == "hi":
            msg = (
                "💺 *यात्रा श्रेणी (Travel Class) चुनें:*\n\n"
                "👉 *विकल्प 1 (बटन):* नीचे श्रेणी बटन दबाएं।\n"
                "💬 *विकल्प 2 (चैट):* लिखें: `3A`, `2A`, `SL`, या `CC`"
            )
        elif lang == "en":
            msg = (
                "💺 *Select your preferred travel class:*\n\n"
                "👉 *Option 1 (Buttons):* Tap a class button below.\n"
                "💬 *Option 2 (Chat):* Type: `3A`, `2A`, `SL`, or `CC`"
            )
        else:
            msg = (
                "💺 *Preferred Class select karein:*\n\n"
                "👉 *Option 1 (Button):* Button par tap karein.\n"
                "💬 *Option 2 (Manual Chat):* Type karein: `3A`, `2A`, `SL`, ya `Sleeper`"
            )
        await send_telegram_message(msg, chat_id=chat_id, reply_markup=keyboard)

    async def _show_summary_and_confirm(self, chat_id: str):
        lang = user_languages.get(chat_id, "hinglish")
        data = user_chat_states.get(chat_id, {}).get("data", {})
        pax_list = data.get("passengers", [{}])
        pax_name = pax_list[0].get("name", "Traveler") if pax_list else "Traveler"
        pax_age = pax_list[0].get("age", 30) if pax_list else 30
        pax_gender = pax_list[0].get("gender", "M") if pax_list else "M"
        from_st = data.get('from_station', 'NDLS')
        to_st = data.get('to_station', 'BSB')
        j_date = data.get('journey_date', '')
        j_cls = data.get('journey_class', '3A')

        if lang == "hi":
            btn_confirm = "✅ पुष्टि करें और बुक करें"
            btn_cancel = "❌ रद्द करें"
            summary = (
                "📋 *IRCTC टिकट बुकिंग सारांश:*\n\n"
                f"• *मार्ग (Route):* `{from_st}` ➔ `{to_st}`\n"
                f"• *तारीख (Date):* {j_date}\n"
                f"• *श्रेणी (Class):* {j_cls} | कोटा: सामान्य (GN)\n"
                f"• *यात्री (Passenger):* {pax_name} ({pax_age}/{pax_gender})\n"
                f"• *किराया (Fare):* As per IRCTC Live (वेबसाइट से लाइव चेक होगा)\n\n"
                "क्या मैं IRCTC ऑटोमेशन बुकिंग शुरू करूँ?\n"
                "नीचे *'✅ पुष्टि करें और बुक करें'* बटन दबाएं:"
            )
        elif lang == "en":
            btn_confirm = "✅ Confirm & Book"
            btn_cancel = "❌ Cancel"
            summary = (
                "📋 *IRCTC Ticket Booking Summary:*\n\n"
                f"• *Route:* `{from_st}` ➔ `{to_st}`\n"
                f"• *Date:* {j_date}\n"
                f"• *Class:* {j_cls} | Quota: General (GN)\n"
                f"• *Passenger:* {pax_name} ({pax_age}/{pax_gender})\n"
                f"• *Fare:* As per IRCTC Live (Calculated dynamically on portal)\n\n"
                "Should I start automated booking in IRCTC?\n"
                "Tap *'✅ Confirm & Book'* below:"
            )
        else:
            btn_confirm = "✅ Confirm & Book"
            btn_cancel = "❌ Cancel"
            summary = (
                "📋 *Ticket Booking Summary:*\n\n"
                f"• *Route:* `{from_st}` ➔ `{to_st}`\n"
                f"• *Date:* {j_date}\n"
                f"• *Class:* {j_cls} | Quota: General (GN)\n"
                f"• *Passenger:* {pax_name} ({pax_age}/{pax_gender})\n"
                f"• *Fare:* As per IRCTC Live (IRCTC portal se live calculate hoga)\n\n"
                "Kya main browser me booking automation shuru karun?\n"
                "Neeche *'✅ Confirm & Book'* button dabayein:"
            )

        keyboard = {
            "inline_keyboard": [
                [
                    {"text": btn_confirm, "callback_data": "confirm_book"},
                    {"text": btn_cancel, "callback_data": "cancel_book"}
                ]
            ]
        }
        await send_telegram_message(summary, chat_id=chat_id, reply_markup=keyboard)

    async def _execute_telegram_booking(self, chat_id: str, data: Dict[str, Any]):
        lang = user_languages.get(chat_id, "hinglish")
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
            train_number=data.get("train_number") or "",
            train_name=data.get("train_name") or "Auto-Selected Train",
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

        b_id = int(booking.id)
        db.close()

        # Start automation task
        target_flow = run_mock_booking_flow if settings.DEMO_MODE else run_real_irctc_booking_flow
        async def runner():
            db_inner = SessionLocal()
            try:
                await target_flow(db_inner, b_id, session_state)
            finally:
                db_inner.close()

        asyncio.create_task(runner())

        if lang == "hi":
            exec_msg = (
                f"🚀 *IRCTC बुकिंग शुरू कर दी गई है!*\nसंदर्भ संख्या (Ref): `{ref}`\n"
                f"IRCTC ब्राउज़र ऑटोमेशन प्रारंभ हो गया है। CAPTCHA आते ही आपको फोटो भेजी जाएगी।"
            )
        elif lang == "en":
            exec_msg = (
                f"🚀 *IRCTC Booking Initiated!*\nRef: `{ref}`\n"
                f"Browser automation has started. A photo will be sent as soon as CAPTCHA appears."
            )
        else:
            exec_msg = (
                f"🚀 *IRCTC Booking Initiated!*\nRef: `{ref}`\n"
                f"Browser automation shuru ho gayi hai. CAPTCHA aate hi main photo bhejunga."
            )
        await send_telegram_message(exec_msg, chat_id=chat_id)

telegram_bot_service = TelegramBotService.get_instance()
