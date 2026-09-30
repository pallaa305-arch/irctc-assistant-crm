"""Telegram wizard whose state advances only after the IRCTC UI accepts a step."""
import asyncio
import logging
import re
import secrets
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from app.automation.live_irctc import LiveIRCTC, LivePageError, parse_irctc_date
from app.automation.flow_state import get_or_create_session
from app.config import settings
from app.database.connection import SessionLocal
from app.database.models import Booking, BookingPassenger
from app.notifications.telegram import send_telegram_message, send_telegram_photo

log = logging.getLogger(__name__)
TERMINAL = {"DONE", "CANCELLED", "EXPIRED"}


@dataclass
class Conversation:
    chat_id: str
    token: str = field(default_factory=lambda: secrets.token_hex(4))
    revision: int = 0
    step: str = "STARTING"
    data: dict = field(default_factory=lambda: {"passengers": [], "quota": "GN"})
    choices: list = field(default_factory=list)
    driver: object = None
    touched: float = field(default_factory=time.monotonic)
    booking_id: int = None
    monitor: object = None

    @property
    def ref(self):
        return f"TG-{self.token}"

    def callback(self, action, value=""):
        return f"live:{self.token}:{self.revision}:{action}:{value}"


def parse_passengers(text):
    result = []
    for row in re.split(r"[;\n]+", text.strip()):
        match = re.fullmatch(r"\s*([A-Za-z][A-Za-z .'-]{1,59}?)\s+(\d{1,3})\s+([MFTmft])(?:\s+(LB|MB|UB|SL|SU|NP))?\s*", row)
        if not match or not 1 <= int(match.group(2)) <= 120:
            raise LivePageError("Format: Rahul Kumar 28 M LB. Multiple passengers: separate with ;. Age 1–120; gender M/F/T.")
        result.append({"name": match.group(1).strip(), "age": int(match.group(2)),
                       "gender": match.group(3).upper(), "berth_preference": match.group(4) or "NP"})
    return result


class LiveBookingWizard:
    def __init__(self, driver_factory=LiveIRCTC):
        self.sessions = {}
        self.locks = {}
        self.driver_factory = driver_factory
        self.reaper = None
        self.operations = {}

    def authorized(self, chat_id):
        # This application uses one personal IRCTC account and one browser profile.
        return bool(settings.TELEGRAM_CHAT_ID) and str(chat_id) == str(settings.TELEGRAM_CHAT_ID)

    def start_maintenance(self):
        if self.reaper is None or self.reaper.done():
            self.reaper = asyncio.create_task(self._expire_loop())

    def stop(self):
        if self.reaper:
            self.reaper.cancel()
        for task in self.operations.values():
            task.cancel()
        for s in self.sessions.values():
            if s.monitor:
                s.monitor.cancel()
            if s.step not in TERMINAL:
                self.finish(s, "EXPIRED")

    async def _expire_loop(self):
        while True:
            await asyncio.sleep(30)
            for chat_id, s in list(self.sessions.items()):
                if s.step not in TERMINAL and s.step != "PAYMENT" and time.monotonic() - s.touched > 900:
                    async with self.locks.setdefault(chat_id, asyncio.Lock()):
                        if time.monotonic() - s.touched > 900:
                            self.finish(s, "EXPIRED")
                            await self.say(s, "Session 15 minutes inactive tha, isliye expire hua. New Booking se dobara shuru karein.")

    async def say(self, s, text, buttons=None):
        keyboard = [[{"text": label, "callback_data": s.callback(action, value)}] for label, action, value in (buttons or [])]
        if s.step not in TERMINAL:
            keyboard.append([{"text": "Cancel booking flow", "callback_data": s.callback("cancel")}])
        await send_telegram_message(text, chat_id=s.chat_id, reply_markup={"inline_keyboard": keyboard})

    def stage(self, s, step):
        s.step = step
        s.revision += 1
        s.touched = time.monotonic()
        flow = get_or_create_session(s.ref)
        flow.captured_data["telegram_chat_id"] = s.chat_id
        flow.captured_data["live_wizard"] = True
        flow.set_stage(step, "PAYMENT_PENDING" if step == "PAYMENT" else "IN_PROGRESS")

    def finish(self, s, step):
        self.stage(s, step)
        flow = get_or_create_session(s.ref)
        status = {"DONE": "CONFIRMED", "CANCELLED": "CANCELLED", "EXPIRED": "FAILED"}[step]
        if s.booking_id:
            with SessionLocal() as db:
                b = db.get(Booking, s.booking_id)
                if b and b.status != "CONFIRMED":
                    # A stopped payment monitor cannot prove that payment failed.
                    b.status = "PAYMENT_PENDING" if b.payment_status == "PENDING" and s.data.get("payment_started") else status
                    db.commit()
                    status = b.status
        flow.set_stage(step, status)
        s.driver.release()

    async def start(self, chat_id):
        if settings.DEMO_MODE:
            await send_telegram_message("Demo mode active hai. Live IRCTC session ke liye menu mein Live mode select karein, phir New Booking dabayein.", chat_id=chat_id)
            return
        old = self.sessions.get(chat_id)
        if old and old.step not in TERMINAL:
            await self.say(old, f"Booking {old.ref} already active ({old.step}). Continue it or cancel first.")
            return
        s = Conversation(chat_id)
        s.driver = self.driver_factory(s.ref)
        self.sessions[chat_id] = s
        self.stage(s, "STARTING")
        await self.say(s, "1/10: IRCTC browser session khol raha hoon aur saved login details fill kar raha hoon…")
        try:
            ready = await s.driver.open()
            if ready:
                self.stage(s, "FROM")
                await self.say(s, "2/10: IRCTC login ready. FROM station ka naam/code bhejein (e.g. New Delhi).")
            else:
                self.stage(s, "LOGIN")
                await self.challenge(s, "Login details fill ho gayi hain. CAPTCHA ka text reply karein, ya browser mein login karke Verify Login dabayein.", "login")
        except Exception:
            self.finish(s, "EXPIRED")
            raise

    async def challenge(self, s, message, action):
        image = await s.driver.challenge_image()
        if image:
            await send_telegram_photo(image, message, chat_id=s.chat_id)
        await self.say(s, message, [("Verify Login" if action == "login" else "Confirm & Continue", action, "")])

    async def handle(self, chat_id, *, text=None, callback=None):
        chat_id = str(chat_id)
        clean = (text or "").strip().lower()
        new = callback == "cmd_book" or clean in {"/book", "book", "booking", "ticket", "book ticket", "train book", "nayi ticket", "ticket booking", "reservation", "tatkal", "बुक"}
        s = self.sessions.get(chat_id)
        active = s and s.step not in TERMINAL
        if not (new or active or (callback or "").startswith("live:")):
            return False
        if not self.authorized(chat_id):
            return True
        # Cancellation can interrupt a slow page load/enquiry before acquiring the
        # chat lock. Validate the current session token/revision first.
        cancel_requested = clean in {"cancel", "/cancel", "stop", "abort", "band karo"} or callback in {"cmd_cancel", "cancel_book", "action_cancel"}
        if s and callback == s.callback("cancel"):
            cancel_requested = True
        running = self.operations.get(chat_id)
        if cancel_requested and running and running is not asyncio.current_task() and not running.done():
            running.cancel()
            await asyncio.gather(running, return_exceptions=True)
        async with self.locks.setdefault(chat_id, asyncio.Lock()):
            current_task = asyncio.current_task()
            self.operations[chat_id] = current_task
            try:
                if new:
                    await self.start(chat_id)
                    return True
                s = self.sessions.get(chat_id)
                if not s or s.step in TERMINAL:
                    await send_telegram_message("This booking session ended. Tap New Booking.", chat_id=chat_id)
                    return True
                action, value = "", ""
                if callback:
                    if callback in {"cmd_cancel", "cancel_book", "action_cancel"}:
                        action = "cancel"
                    elif callback == "cmd_status":
                        action = "status"
                    elif callback.startswith("live:"):
                        parts = callback.split(":", 4)
                        if len(parts) != 5 or parts[1] != s.token or parts[2] != str(s.revision):
                            await self.say(s, "Ye purana button hai. Latest message ke buttons use karein.")
                            return True
                        action, value = parts[3:]
                    else:
                        await self.say(s, f"Live booking active hai: {s.step}. Latest booking prompt follow karein.")
                        return True
                if clean in {"cancel", "/cancel", "stop", "abort", "band karo"}:
                    action = "cancel"
                if action == "cancel":
                    if s.monitor:
                        s.monitor.cancel()
                    paid = s.data.get("payment_started")
                    self.finish(s, "CANCELLED")
                    await self.say(s, "Booking flow stopped." + (" Payment may still complete: check IRCTC Booked Ticket History before retrying. This does not cancel an issued ticket." if paid else ""))
                    return True
                if action == "status" or clean in {"/status", "status", "/start", "/menu", "hi", "hello"}:
                    await self.say(s, f"{s.ref}: {s.step}. Latest prompt ka reply dein; /cancel se stop kar sakte hain.")
                    return True
                s.touched = time.monotonic()
                await self.advance(s, text or "", action, value)
            except (LivePageError, ValueError) as exc:
                s = self.sessions.get(chat_id)
                if s:
                    await self.say(s, str(exc))
            except Exception as exc:
                # Do not include browser call logs; these can contain passwords or CAPTCHA input.
                log.warning("Live booking step failed (%s)", type(exc).__name__)
                s = self.sessions.get(chat_id)
                if s and s.step not in TERMINAL:
                    self.stage(s, "ERROR")
                    await self.say(s, "IRCTC page expected step par nahi aaya. Browser check karein; /cancel karke fresh booking start karein. Payment kiya ho to pehle IRCTC history check karein.")
                else:
                    await send_telegram_message("IRCTC browser open/login step fail hua. Connection aur browser check karke New Booking retry karein.", chat_id=chat_id)
            finally:
                if self.operations.get(chat_id) is current_task:
                    self.operations.pop(chat_id, None)
        return True

    async def advance(self, s, text, action, value):
        d = s.data
        if s.step == "LOGIN":
            if await s.driver.login(None if action == "login" else text):
                self.stage(s, "FROM")
                await self.say(s, "2/10: Login verified. FROM station ka naam/code bhejein.")
            else:
                self.stage(s, "LOGIN")
                await self.challenge(s, "Login verify nahi hua. Current CAPTCHA enter karein ya browser mein login complete karein.", "login")
        elif s.step in {"FROM", "TO", "FROM_CHOICE", "TO_CHOICE"}:
            field = "from" if s.step.startswith("FROM") else "to"
            if action == "station" and s.step.endswith("CHOICE"):
                label = s.choices[int(value)]
                code = await s.driver.select_station(field, label)
                if field == "to" and code == d.get("from_station"):
                    raise LivePageError("From aur To stations alag hone chahiye.")
                d[f"{field}_station"] = code
                self.stage(s, "TO" if field == "from" else "DATE")
                await self.say(s, f"Website par {label} selected.\n" + ("3/10: TO station ka naam/code bhejein." if field == "from" else "4/10: Journey date DD/MM/YYYY mein bhejein (ya aaj/kal/parso)."))
            else:
                s.choices = await s.driver.stations(field, text)
                self.stage(s, field.upper() + "_CHOICE")
                await self.say(s, "IRCTC ke station suggestions mein se choose karein:", [(v, "station", str(i)) for i, v in enumerate(s.choices)])
        elif s.step == "DATE":
            offset = {"aaj": 0, "today": 0, "kal": 1, "tomorrow": 1, "parso": 2}.get(text.strip().lower())
            dt = date.today() + timedelta(days=offset) if offset is not None else parse_irctc_date(text)
            await s.driver.set_date(dt.strftime("%d/%m/%Y"))
            d["journey_date"] = dt
            self.stage(s, "QUOTA")
            await self.say(s, f"Website date: {dt:%d/%m/%Y}. Quota choose karein:", [(label, "quota", code) for code, label in [("GN", "General"), ("TQ", "Tatkal"), ("PT", "Premium Tatkal"), ("LD", "Ladies"), ("SS", "Lower Berth / Senior Citizen")]])
        elif s.step == "QUOTA" and action == "quota":
            await s.driver.set_quota(value)
            d["quota"] = value
            self.stage(s, "COMPARE_CLASS")
            await self.say(s, "Train list mein kaunsi class ke seats aur fare compare karne hain?", [(c, "compare", c) for c in ("3A", "2A", "SL", "1A", "3E", "CC", "EC", "2S")])
        elif s.step == "COMPARE_CLASS" and action == "compare":
            if value not in {"3A", "2A", "SL", "1A", "3E", "CC", "EC", "2S"}:
                raise LivePageError("Choose a class from the current buttons.")
            d["compare_class"] = value
            await self.say(s, "5/10: IRCTC se selected date ki trains load ho rahi hain…")
            d["trains"] = await s.driver.search()
            self.stage(s, "TRAIN")
            await self.show_trains(s)
        elif s.step == "TRAIN":
            if action == "page":
                await self.show_trains(s, int(value))
                return
            number = value if action == "train" else text.strip()
            train = next((t for t in d["trains"] if t["train_number"] == number), None)
            if not train:
                raise LivePageError("Current list ka train button ya 5-digit train number choose karein.")
            d["train"] = train
            self.stage(s, "CLASS")
            await self.say(s, f"6/10: {train['train_name']}\nClass choose karein; IRCTC se exact date ki availability/fare check hogi.", [(c, "class", c) for c in train["classes"]])
        elif s.step in {"CLASS", "QUOTE"} and action in {"class", "refresh"}:
            cls = value if action == "class" else d["quote"]["class_code"]
            d["quote"] = await s.driver.availability(d["train"]["train_number"], cls)
            self.stage(s, "QUOTE")
            q = d["quote"]
            fare = f"₹{q['fare']:,.2f}" if q["fare"] is not None else "IRCTC par abhi visible nahi; review par exact total aayega"
            await self.say(s, f"IRCTC • {d['journey_date']:%d/%m/%Y} • {cls}\n{q['status']}\nFare: {fare}\nChecked: {q['checked_at']}\nSeats/fare booking tak badal sakte hain.", [("Choose this train/class", "select", ""), ("Refresh availability", "refresh", ""), ("Other class", "classes", ""), ("Other train", "trains", "")])
        elif s.step == "QUOTE" and action == "classes":
            self.stage(s, "CLASS")
            await self.say(s, "Class choose karein:", [(c, "class", c) for c in d["train"]["classes"]])
        elif s.step == "QUOTE" and action == "trains":
            self.stage(s, "TRAIN")
            await self.show_trains(s)
        elif s.step == "QUOTE" and action == "select":
            self.stage(s, "TRAIN_CHECKPOINT")
            if await s.driver.book_selected():
                await self.ask_passengers(s)
            else:
                await self.say(s, "IRCTC ko browser mein action chahiye (e.g. Aadhaar OTP / notice). Browser mein complete karein, phir Verify Passenger Page dabayein.", [("Verify Passenger Page", "passenger_ready", "")])
        elif s.step == "TRAIN_CHECKPOINT" and action == "passenger_ready":
            if await s.driver.passenger_ready():
                await self.ask_passengers(s)
            else:
                await self.say(s, "Passenger page abhi open nahi hai. IRCTC browser ka message/OTP complete karein.", [("Verify Passenger Page", "passenger_ready", "")])
        elif s.step == "PASSENGERS":
            if action == "paxdone":
                if not d["passengers"]:
                    raise LivePageError("Pehle passenger details bhejein.")
                self.stage(s, "CONTACT")
                await self.say(s, "8/10: Booking contact ka 10-digit mobile number bhejein.")
            else:
                passengers = d["passengers"] + parse_passengers(text)
                if len(passengers) > (4 if d["quota"] in {"TQ", "PT"} else 6):
                    raise LivePageError("Is quota ke liye passenger limit exceed ho gayi.")
                await s.driver.fill_passengers(passengers)
                d["passengers"] = passengers
                self.stage(s, "PASSENGERS")
                await self.say(s, f"{len(passengers)} passenger(s) website par filled. Aur bhejein ya Done dabayein.", [("Done adding passengers", "paxdone", "")])
        elif s.step == "CONTACT":
            mobile = text.strip()
            if not re.fullmatch(r"[6-9]\d{9}", mobile):
                raise LivePageError("Valid 10-digit mobile number bhejein.")
            await s.driver.fill_contact(mobile)
            d["mobile"] = mobile
            # Move before navigation: retrying contact cannot accidentally submit review.
            self.stage(s, "REVIEW_LOADING")
            review = await s.driver.review()
            if review:
                await self.show_review(s, review)
            else:
                await self.say(s, "IRCTC review page open nahi hua. Browser mein validation/notice complete karein, phir Verify Review dabayein.", [("Verify Review", "review_ready", "")])
        elif s.step == "REVIEW_LOADING" and action == "review_ready":
            await self.show_review(s, await s.driver.read_review())
        elif s.step == "REVIEW" and action == "confirm":
            self.create_record(s)
            self.stage(s, "REVIEW_CAPTCHA")
            if await s.driver.challenge_image():
                await self.challenge(s, "Review CAPTCHA ka text reply karein.", "payment")
            else:
                await self.begin_payment(s)
        elif s.step == "REVIEW_CAPTCHA":
            if action == "payment" and await s.driver.challenge_image():
                raise LivePageError("CAPTCHA text reply karein, phir payment page khulega.")
            await self.begin_payment(s, text or None)
        elif s.step == "PAYMENT":
            await self.say(s, "Payment apne UPI app/browser mein complete karein. PNR website se verify hone par confirmation aayega. PIN/OTP Telegram par mat bhejein.")
        else:
            await self.say(s, f"Current step: {s.step}. Latest prompt follow karein ya /cancel karein.")

    async def ask_passengers(self, s):
        self.stage(s, "PASSENGERS")
        await self.say(s, "7/10: Passenger form browser mein open hai. Name Age Gender aur optional berth bhejein:\nRahul Kumar 28 M LB\nMultiple passengers ko ; se separate karein. Har message website par fill hoga. Sab add karne ke baad Done dabayein.", [("Done adding passengers", "paxdone", "")])

    async def show_review(self, s, review):
        d = s.data
        d["total_fare"] = review["total_fare"]
        self.stage(s, "REVIEW")
        await send_telegram_photo(review["screenshot"], "IRCTC review: route, date, train, class, passengers aur total verify karein.", chat_id=s.chat_id)
        await self.say(s, f"9/10: {d['from_station']} → {d['to_station']} | {d['journey_date']:%d/%m/%Y}\n{d['train']['train_number']} • {d['quote']['class_code']} • {d['quota']}\nPassengers: {', '.join(p['name'] for p in d['passengers'])}\nIRCTC total: ₹{d['total_fare']:,.2f}\nConfirm karne par payment step khulega.", [("Confirm details & proceed", "confirm", "")])

    async def show_trains(self, s, page=0):
        trains = s.data["trains"]
        if page < 0 or page * 5 >= len(trains):
            raise LivePageError("Invalid results page.")
        self.stage(s, "TRAIN")
        chunk = trains[page * 5:page * 5 + 5]
        lines = []
        cls = s.data.get("compare_class")
        if cls:
            await self.say(s, f"IRCTC se is page ki {cls} availability/fare check kar raha hoon. Har train ki enquiry ek-ek karke hogi…")
        for t in chunk:
            details = ""
            if cls and cls in t["classes"]:
                try:
                    quote = await s.driver.availability(t["train_number"], cls)
                    price = f"₹{quote['fare']:,.2f}" if quote["fare"] is not None else "fare not shown by IRCTC"
                    details = f"\n{cls}: {quote['status']} • {price}"
                except LivePageError as exc:
                    details = f"\n{cls}: Live enquiry unavailable ({str(exc)[:120]})"
            elif cls:
                details = f"\n{cls}: class not shown for this train"
            lines.append(f"{t['train_name']}\n{t['departure_time'] or 'Time not visible'} → {t['arrival_time'] or 'Time not visible'} | {', '.join(t['classes'])}{details}")
        buttons = [(t["train_number"], "train", t["train_number"]) for t in chunk]
        if page:
            buttons.append(("Previous", "page", str(page - 1)))
        if (page + 1) * 5 < len(trains):
            buttons.append(("Next", "page", str(page + 1)))
        await self.say(s, f"IRCTC se {len(trains)} trains • Page {page + 1}\n\n" + "\n\n".join(lines) + "\n\nChoose train. Final fare IRCTC review par verify hoga.", buttons)

    def create_record(self, s):
        if s.booking_id:
            return
        d = s.data
        with SessionLocal() as db:
            names = {p["name"].strip().lower() for p in d["passengers"]}
            existing = db.query(Booking).filter(Booking.from_station == d["from_station"], Booking.to_station == d["to_station"], Booking.journey_date == d["journey_date"], Booking.status.in_(["INITIATED", "IN_PROGRESS", "WAITING_MANUAL", "PAYMENT_PENDING", "CONFIRMED"])).all()
            if any(names.intersection(p.name.strip().lower() for p in b.passengers) for b in existing):
                raise LivePageError("Same passenger/route/date ki active booking exists. Booking history check karein.")
            b = Booking(booking_ref=s.ref, from_station=d["from_station"], to_station=d["to_station"], boarding_station=d["from_station"], journey_date=d["journey_date"], train_number=d["train"]["train_number"], train_name=d["train"]["train_name"], departure_time=d["train"].get("departure_time"), arrival_time=d["train"].get("arrival_time"), journey_class=d["quote"]["class_code"], quota=d["quota"], fare=d["total_fare"], passenger_count=len(d["passengers"]), contact_mobile=d["mobile"], status="WAITING_MANUAL", payment_status="PENDING")
            db.add(b)
            db.flush()
            for pax in d["passengers"]:
                db.add(BookingPassenger(booking_id=b.id, status="PENDING", **pax))
            db.commit()
            s.booking_id = b.id

    async def begin_payment(self, s, captcha=None):
        self.stage(s, "PAYMENT_LOADING")
        # Mark before navigation: errors after gateway submission have an unknown outcome.
        s.data["payment_started"] = True
        with SessionLocal() as db:
            db.get(Booking, s.booking_id).status = "PAYMENT_PENDING"
            db.commit()
        picture = await s.driver.proceed_payment(captcha)
        self.stage(s, "PAYMENT")
        await send_telegram_photo(picture, "10/10: IRCTC payment page. Payment apne app/browser mein complete karein.", chat_id=s.chat_id)
        await self.say(s, "Official payment QR visible hote hi yahan bhejunga. Gateway ko manual selection chahiye ho to browser mein choose karein. Website par PNR milne ke baad hi booking confirmed hogi.")
        s.monitor = asyncio.create_task(self.monitor(s))

    async def monitor(self, s):
        qr_sent = False
        deadline = time.monotonic() + 600
        try:
            while time.monotonic() < deadline:
                await asyncio.sleep(2)
                async with self.locks.setdefault(s.chat_id, asyncio.Lock()):
                    if s.step != "PAYMENT":
                        return
                    confirmed = await s.driver.confirmation()
                    if confirmed:
                        with SessionLocal() as db:
                            b = db.get(Booking, s.booking_id)
                            b.pnr, b.transaction_id = confirmed["pnr"], confirmed["transaction_id"]
                            b.status, b.payment_status = "CONFIRMED", "COMPLETED"
                            db.commit()
                            from app.crm.crm_service import finalize_successful_booking
                            await finalize_successful_booking(db, b.id)
                        self.finish(s, "DONE")
                        await send_telegram_photo(confirmed["screenshot"], f"IRCTC confirmed PNR: {confirmed['pnr']}", chat_id=s.chat_id)
                        await self.say(s, f"Booking confirmed. PNR: {confirmed['pnr']}. Booking history/Excel updated.")
                        return
                    if not qr_sent:
                        qr = await s.driver.payment_snapshot()
                        if qr:
                            await send_telegram_photo(qr, "IRCTC gateway ka actual QR. Amount aur merchant apne payment app mein verify karein.", chat_id=s.chat_id)
                            qr_sent = True
            self.finish(s, "EXPIRED")
            await self.say(s, "PNR verification timed out. Payment status uncertain hai: IRCTC Booked Ticket History check karein before making another payment. Record PAYMENT_PENDING rakha hai.")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("Payment verification interrupted (%s)", type(exc).__name__)
            self.finish(s, "EXPIRED")
            await self.say(s, "Confirmation verify nahi hui. Payment status pending hai; IRCTC history check karein before retrying.")


live_booking = LiveBookingWizard()
