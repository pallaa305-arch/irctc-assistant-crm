"""Stepwise IRCTC UI adapter. Values come from the current browser page only.

No generated availability, guessed prices, alternate trains, or automatic CAPTCHA
solving. A changed/unsupported page is an error, never a successful booking.
"""
import asyncio
import re
from datetime import date, datetime, timezone
from urllib.parse import urlparse

from playwright.async_api import TimeoutError as BrowserTimeout

from app.automation.browser_manager import browser_manager
from app.config import settings

HOME = "https://www.irctc.co.in/nget/train-search"
FROM = "p-autocomplete[formcontrolname='origin'] input, #origin input"
TO = "p-autocomplete[formcontrolname='destination'] input, #destination input"
DATE = "p-calendar[formcontrolname='journeyDate'] input, #jDate input"
CARDS = "app-train-avl-enq"
CAPTCHA = "app-captcha img:visible, #captchaImg:visible, img.captcha-img:visible"
CAPTCHA_INPUT = "#nlpAnswer:visible, input[formcontrolname='captcha']:visible"
NAME = "input[placeholder='Passenger Name'], p-autocomplete[formcontrolname='passengerName'] input"
CLASSES = r"\b(1A|2A|3A|3E|SL|CC|EC|2S|FC|EA|EV)\b"


class LivePageError(RuntimeError):
    pass


def parse_irctc_date(value):
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d-%m-%y", "%Y-%m-%d", "%d %b %Y", "%a, %d %b %Y"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            pass
    raise LivePageError("IRCTC journey date could not be verified.")


def parse_train_cards(rows):
    """Normalize DOM snapshots without filling missing fields with made-up values."""
    result = []
    for row in rows:
        heading = row.get("heading", "")
        number = re.search(r"\b(\d{5})\b", heading)
        if not number:
            continue
        times = re.findall(r"\b(?:[01]\d|2[0-3]):[0-5]\d\b", row.get("text", ""))
        result.append({
            "train_number": number.group(1),
            "train_name": heading.strip(),
            "departure_time": times[0] if times else None,
            "arrival_time": times[1] if len(times) > 1 else None,
            "classes": list(dict.fromkeys(re.findall(CLASSES, row.get("text", "")))),
            "source": "irctc_browser",
        })
    return list({t["train_number"]: t for t in result}.values())


def parse_availability(text, journey_date, travel_class):
    # Availability must be attached to the exact date tile, not an adjacent date.
    found_date = None
    for raw in re.findall(r"\d{2}[/-]\d{2}[/-]\d{4}|\d{1,2} [A-Za-z]{3} \d{4}", text):
        try:
            if parse_irctc_date(raw) == journey_date:
                found_date = raw
                break
        except LivePageError:
            pass
    # IRCTC date tiles can omit the year; the search form already verified it.
    if not found_date and re.search(r"\b" + journey_date.strftime("%d %b") + r"\b", text, re.I):
        found_date = journey_date.isoformat()
    if not found_date:
        raise LivePageError("Availability for the selected date is not visible. Refresh in the browser.")
    match = re.search(r"(?:(?:GNWL|RLWL|PQWL|TQWL)\s*\d+\s*/\s*WL\s*\d+|NOT AVAILABLE|REGRET[^\n]*|TRAIN CANCELLED|DEPARTED|AVAILABLE\s*-?\s*\d+|CURR_AVBL\s*-?\s*\d+|(?:GNWL|RLWL|PQWL|TQWL|WL|RAC)\s*[-/]?\s*\d+)", text, re.I)
    if not match:
        raise LivePageError("IRCTC has not returned a readable seat status for this date/class.")
    return {"date": journey_date.isoformat(), "class_code": travel_class,
            "status": match.group(0).upper(), "source": "irctc_browser",
            "checked_at": datetime.now(timezone.utc).isoformat()}


def parse_confirmation(text):
    # A phone number, transaction ID or generic success banner is not a PNR.
    pnr = re.search(r"\bPNR(?:\s*(?:No\.?|Number))?\s*[:#-]?\s*(\d{10})\b", text, re.I)
    if not pnr:
        return None
    txn = re.search(r"Transaction\s*(?:ID|No\.?)\s*[:#-]?\s*(\d+)\b", text, re.I)
    return {"pnr": pnr.group(1), "transaction_id": txn.group(1) if txn else None}


def parse_availability_response(payload, journey_date, train_number, travel_class):
    """Read the response to the page's own class enquiry, never a separate API call."""
    if not isinstance(payload, dict) or payload.get("errorMessage"):
        raise LivePageError(str(payload.get("errorMessage") or "IRCTC availability response is invalid.") if isinstance(payload, dict) else "Invalid IRCTC availability response.")
    if str(payload.get("trainNo", payload.get("trainNumber", train_number))) != train_number:
        raise LivePageError("IRCTC returned availability for another train.")
    if payload.get("enqClass", travel_class) != travel_class:
        raise LivePageError("IRCTC returned availability for another class.")
    for row in payload.get("avlDayList", []):
        try:
            day = parse_irctc_date(row.get("availablityDate", row.get("availabilityDate", "")))
        except LivePageError:
            continue
        if day == journey_date:
            status = str(row.get("availablityStatus", row.get("availabilityStatus", ""))).strip()
            if not status:
                break
            raw_fare = payload.get("totalFare")
            try:
                fare = float(str(raw_fare).replace(',', '')) if raw_fare is not None else None
            except ValueError:
                fare = None
            return {"train_number": train_number, "class_code": travel_class, "date": day.isoformat(),
                    "status": status, "fare": fare, "source": "irctc_browser_response",
                    "checked_at": datetime.now(timezone.utc).isoformat()}
    raise LivePageError("IRCTC has not returned availability for the requested date.")


class LiveIRCTC:
    def __init__(self, owner):
        self.owner = owner
        self.page = None
        self.trains = []
        self.journey_date = None
        self.train_number = None
        self.travel_class = None
        self.quote = None
        self.station_labels = {}
        self.payment_pages = []
        self.passengers = []
        self.quota = "GN"
        self._page_listener = self.payment_pages.append

    async def check_page(self):
        if not self.page or self.page.is_closed() or browser_manager.owner != self.owner:
            raise LivePageError("Browser session expired. Start New Booking again.")
        host = urlparse(self.page.url).hostname or ""
        if host != "www.irctc.co.in":
            raise LivePageError("The booking page is no longer on IRCTC. Check the browser before continuing.")

    async def logged_in(self):
        return await self.page.get_by_text(re.compile(r"^LOGOUT$", re.I)).count() > 0

    async def open(self):
        browser_manager.claim(self.owner)
        self.page = await browser_manager.get_page(owner=self.owner, foreground=False)
        await self.page.goto(HOME, wait_until="domcontentloaded", timeout=45000)
        await self.check_page()
        english = self.page.locator("button:visible").filter(has_text=re.compile(r"^English$"))
        if await english.count():
            await english.first.click()
            if await english.first.is_visible():
                await english.first.press("Enter")
        ok = self.page.get_by_role("button", name="OK", exact=True)
        if await ok.count() and await ok.first.is_visible():
            await ok.first.click()
        await self.page.locator(FROM).first.wait_for(timeout=20000)
        if await self.logged_in():
            return True
        if not settings.IRCTC_USERNAME or not settings.IRCTC_PASSWORD:
            raise LivePageError("Set IRCTC_USERNAME and IRCTC_PASSWORD in the local .env before booking.")
        await self.page.locator("a.loginText:visible, a:has-text('LOGIN'):visible, a:has(i.fa-user):visible").first.click()
        await self.page.locator("input[formcontrolname='userid'], #userId").first.fill(settings.IRCTC_USERNAME)
        await self.page.locator("input[formcontrolname='password'], #pwd").first.fill(settings.IRCTC_PASSWORD)
        return False

    async def challenge_image(self):
        cap = self.page.locator(CAPTCHA).first
        if await cap.count():
            return await cap.screenshot()
        return None

    async def login(self, captcha=None):
        await self.check_page()
        if await self.logged_in():
            return True
        if captcha:
            await self.page.locator(CAPTCHA_INPUT).first.fill(captcha)
            await self.page.get_by_role("button", name=re.compile(r"^SIGN IN$", re.I)).first.click()
        try:
            await self.page.get_by_text(re.compile(r"^LOGOUT$", re.I)).first.wait_for(timeout=10000)
        except BrowserTimeout:
            return False
        return True

    async def stations(self, field, query):
        await self.check_page()
        if field not in ("from", "to") or len(query.strip()) < 2:
            raise LivePageError("Enter at least two letters of the station name or code.")
        inp = self.page.locator(FROM if field == "from" else TO).first
        await inp.fill("")
        await inp.press_sequentially(query.strip(), delay=80)
        options = self.station_options(field)
        await options.first.wait_for(timeout=10000)
        # PrimeNG autocompletes debounce keystrokes; let the final query settle.
        await asyncio.sleep(0.7)
        labels = [await options.nth(i).inner_text() for i in range(await options.count())]
        return [re.sub(r"\s+", " ", s).strip() for s in labels if re.search(r"\s-\s*[A-Z0-9]{2,5}\b", s)][:12]

    def station_options(self, field):
        scope = "#origin" if field == "from" else "#destination"
        return self.page.locator(scope).locator("li[role='option']:visible")

    async def select_station(self, field, label):
        options = self.station_options(field)
        wanted = re.search(r"\s-\s*([A-Z0-9]{2,5})\b", label)
        if not wanted:
            raise LivePageError("Choose an actual station from IRCTC suggestions.")
        await options.filter(has_text=re.compile(r"\s-\s*" + wanted.group(1) + r"\b")).first.click()
        await self.page.locator(FROM if field == "from" else TO).first.press("Tab")
        value = await self.page.locator(FROM if field == "from" else TO).first.input_value()
        # IRCTC labels are typically 'NEW DELHI - NDLS (NEW DELHI)'.
        code = re.search(r"\s-\s*([A-Z0-9]{2,5})\b", value)
        if not code:
            code = re.search(r"\(([A-Z0-9]{2,5})\)\s*$", value)
        if not code or code.group(1) != wanted.group(1):
            raise LivePageError("Selected station code could not be verified from the IRCTC field.")
        self.station_labels[field] = value
        return code.group(1)

    async def set_date(self, value):
        self.journey_date = parse_irctc_date(value)
        if self.journey_date < date.today():
            raise LivePageError("Journey date cannot be in the past.")
        text = self.journey_date.strftime("%d/%m/%Y")
        inp = self.page.locator(DATE).first
        await inp.click()
        await inp.press("ControlOrMeta+A")
        await inp.press_sequentially(text, delay=40)
        await inp.press("Tab")
        if parse_irctc_date(await inp.input_value()) != self.journey_date:
            raise LivePageError("IRCTC did not accept the selected date.")

    async def set_quota(self, quota):
        labels = {"GN": "GENERAL", "TQ": "TATKAL", "PT": "PREMIUM TATKAL", "LD": "LADIES", "SS": "LOWER BERTH/SR.CITIZEN"}
        if quota not in labels:
            raise LivePageError("Unsupported quota.")
        dropdown = self.page.locator("p-dropdown[formcontrolname='journeyQuota'], #journeyQuota").first
        await dropdown.click()
        await self.page.get_by_role("option", name=labels[quota], exact=True).click()
        if labels[quota] not in (await dropdown.inner_text()).upper():
            raise LivePageError("IRCTC quota selection could not be verified.")
        self.quota = quota

    async def search(self):
        await self.check_page()
        for field, selector in (("from", FROM), ("to", TO)):
            if await self.page.locator(selector).first.input_value() != self.station_labels.get(field):
                raise LivePageError("Station field changed in the browser. Start a fresh search.")
        if parse_irctc_date(await self.page.locator(DATE).first.input_value()) != self.journey_date:
            raise LivePageError("Browser date differs from your selected date.")
        await self.page.get_by_role("button", name=re.compile(r"^Search(?: Trains)?$", re.I)).first.click()
        try:
            await self.page.locator(CARDS).first.wait_for(timeout=30000)
        except BrowserTimeout as exc:
            notices = await self.page.locator(".ui-toast-message, .ui-growl-message, .ui-dialog-content, .p-toast-message").all_text_contents()
            notice = " ".join(notices).strip()[:700]
            if notice:
                raise LivePageError("IRCTC: " + notice) from exc
            raise LivePageError("IRCTC did not show trains. Check route/date, session or the website message; no substitute data was used.") from exc
        rows = await self.page.locator(CARDS).evaluate_all("""cards => cards.map(c => ({
            heading: (c.querySelector('.train-heading, .train-name') || {}).innerText || '',
            text: c.innerText
        }))""")
        self.trains = parse_train_cards(rows)
        if not self.trains:
            raise LivePageError("Train results could not be read from IRCTC.")
        return self.trains

    def card(self, train_number):
        if train_number not in [t["train_number"] for t in self.trains]:
            raise LivePageError("This train is not in the current IRCTC search results.")
        return self.page.locator(CARDS).filter(has_text=re.compile(r"\b" + re.escape(train_number) + r"\b")).first

    async def availability(self, train_number, travel_class):
        await self.check_page()
        train = next((t for t in self.trains if t["train_number"] == train_number), None)
        if not train or travel_class not in train["classes"]:
            raise LivePageError("Choose a class shown for this train on IRCTC.")
        card = self.card(train_number)
        tab = card.locator("div.pre-avl").filter(has_text=re.compile(r"\(" + travel_class + r"\)"))
        def matches(response):
            path = urlparse(response.url).path
            codes = [re.search(r"\s-\s*([A-Z0-9]{2,5})\b", label).group(1) for label in self.station_labels.values()]
            return bool(urlparse(response.url).hostname == "www.irctc.co.in"
                    and "avlfareenq" in path.lower()
                    and re.search(r"/" + re.escape(train_number) + r"/", path)
                    and re.search(r"/" + re.escape(travel_class) + r"/", path)
                    and all(re.search(r"/" + re.escape(code) + r"/", path) for code in codes)
                    and re.search(r"/" + self.quota + r"/", path))
        # Register before clicking; a previous class's visible tiles are not a new quote.
        try:
            async with self.page.expect_response(matches, timeout=20000) as enquiry:
                await tab.first.click()
                refresh = card.get_by_text("Refresh", exact=True)
                if await refresh.count() and await refresh.first.is_visible():
                    await refresh.first.click()
            response = await enquiry.value
            quote = parse_availability_response(await response.json(), self.journey_date, train_number, travel_class)
        except BrowserTimeout as exc:
            raise LivePageError("Fresh IRCTC availability response not received. Try Refresh; no old class/date quote was reused.") from exc
        self.train_number, self.travel_class, self.quote = train_number, travel_class, quote
        return quote

    async def select_date_tile(self):
        card = self.card(self.train_number)
        quote = self.quote
        last_error = None
        for _ in range(20):
            tiles = card.locator("div.pre-avl, td.pre-avl")
            for i in range(await tiles.count()):
                tile = tiles.nth(i)
                try:
                    tile_quote = parse_availability(await tile.inner_text(), self.journey_date, self.travel_class)
                except LivePageError as exc:
                    last_error = exc
                    continue
                if re.sub(r"\s", "", tile_quote["status"]) != re.sub(r"\s", "", quote["status"].upper()):
                    continue
                await tile.click()
                return
            await asyncio.sleep(0.5)
        raise last_error or LivePageError("IRCTC availability did not load.")

    async def book_selected(self):
        if not self.quote or re.search(r"NOT AVAILABLE|REGRET|CANCELLED|DEPARTED", self.quote["status"]):
            raise LivePageError("This selection is not bookable on IRCTC.")
        await self.select_date_tile()
        await self.card(self.train_number).get_by_role("button", name=re.compile(r"^Book Now$", re.I)).click()
        try:
            await self.page.locator(NAME).first.wait_for(timeout=20000)
        except BrowserTimeout:
            return False  # IRCTC may require Aadhaar OTP / a booking notice.
        return True

    async def passenger_ready(self):
        await self.check_page()
        return await self.page.locator(NAME).first.is_visible()

    async def select_value(self, control, value, index=0):
        native = self.page.locator(f"select[formcontrolname='{control}']")
        if await native.count() > index:
            await native.nth(index).select_option(value=value)
            return
        dropdowns = self.page.locator(f"p-dropdown[formcontrolname='{control}']")
        if await dropdowns.count() > index:
            labels = {"passengerGender": {"M": "Male", "F": "Female", "T": "Transgender"},
                      "passengerBerthChoice": {"NP": "No Preference", "LB": "Lower", "MB": "Middle", "UB": "Upper", "SL": "Side Lower", "SU": "Side Upper"}}
            label = labels.get(control, {}).get(value)
            if label:
                await dropdowns.nth(index).click()
                await self.page.get_by_role("option", name=label, exact=True).click()
                if label.casefold() not in (await dropdowns.nth(index).inner_text()).casefold():
                    raise LivePageError("IRCTC dropdown did not accept your selection.")
                return
        raise LivePageError(f"IRCTC form control {control} changed. Complete it in the browser.")

    async def fill_passengers(self, passengers):
        await self.check_page()
        for i, pax in enumerate(passengers):
            if await self.page.locator(NAME).count() <= i:
                await self.page.get_by_text(re.compile(r"^\+?\s*Add Passenger$", re.I)).first.click()
            name = self.page.locator(NAME).nth(i)
            age = self.page.locator("input[placeholder='Age'], input[formcontrolname='passengerAge']").nth(i)
            await name.fill(pax["name"])
            await name.press("Tab")
            await age.fill(str(pax["age"]))
            await age.press("Tab")
            await self.select_value("passengerGender", pax["gender"], i)
            if await self.page.locator("select[formcontrolname='passengerBerthChoice'], p-dropdown[formcontrolname='passengerBerthChoice']").count() > i:
                await self.select_value("passengerBerthChoice", pax.get("berth_preference", "NP"), i)
            if await name.input_value() != pax["name"] or await age.input_value() != str(pax["age"]):
                raise LivePageError("Passenger details were not accepted by IRCTC.")
        self.passengers = list(passengers)

    def verify_journey(self, text):
        for value in (self.train_number, self.travel_class):
            if not re.search(r"\b" + re.escape(value) + r"\b", text):
                raise LivePageError("Page train/class differs from your selection.")
        for label in self.station_labels.values():
            station_name = label.split(" - ")[0].strip()
            code = re.search(r"\s-\s*([A-Z0-9]{2,5})\b", label)
            if station_name.upper() not in text.upper() and (not code or not re.search(r"\b" + code.group(1) + r"\b", text)):
                raise LivePageError("Page route could not be matched to your selected stations.")
        variants = [self.journey_date.strftime(fmt) for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d %b %Y", "%d-%b-%Y", "%d %b, %Y")]
        if not any(v.lower() in text.lower() for v in variants):
            raise LivePageError("Page journey date could not be verified.")
        for pax in self.passengers:
            if pax["name"].casefold() not in text.casefold():
                raise LivePageError("Page passenger list differs from the entered passengers.")

    async def fill_contact(self, mobile):
        inp = self.page.locator("input[formcontrolname='mobileNumber'], input#mobileNumber").first
        await inp.fill(mobile)
        await inp.press("Tab")
        if await inp.input_value() != mobile:
            raise LivePageError("Contact number was not accepted by IRCTC.")

    async def review(self):
        await self.page.get_by_role("button", name=re.compile(r"^Continue$", re.I)).first.click()
        try:
            await self.page.locator("app-review-booking").wait_for(timeout=20000)
        except BrowserTimeout:
            return None
        return await self.read_review()

    async def read_review(self):
        await self.check_page()
        root = self.page.locator("app-review-booking")
        text = await root.inner_text()
        self.verify_journey(text)
        total = re.search(r"(?:Total\s*(?:Fare|Amount)|Fare\s*Amount)\s*[:\s]*(?:₹|Rs\.?|INR)?\s*([\d,]+(?:\.\d{1,2})?)", text, re.I)
        if not total:
            raise LivePageError("Exact total fare could not be read from the IRCTC review page.")
        return {"total_fare": float(total.group(1).replace(',', '')), "text": text, "screenshot": await root.screenshot()}

    async def proceed_payment(self, captcha=None):
        if captcha:
            await self.page.locator(CAPTCHA_INPUT).first.fill(captcha)
        await self.page.get_by_role("button", name=re.compile(r"^Continue$", re.I)).first.click()
        await self.page.locator("app-payment").wait_for(timeout=20000)
        # Let the website open its actual gateway. No generated UPI IDs or amounts.
        root = self.page.locator("app-payment")
        self.page.context.on("page", self._page_listener)
        ipay = root.locator(".bank-text").filter(has_text=re.compile(r"IRCTC iPay", re.I)).first
        if not await ipay.count():
            # Unsupported gateway layout: preserve the genuine payment screen for manual selection.
            return await root.screenshot()
        await ipay.click()
        await root.get_by_role("button", name=re.compile(r"Pay\s*(?:&|and)\s*Book|Make Payment", re.I)).first.click()
        gateway = self.page
        for _ in range(20):
            pages = [self.page] + [p for p in self.payment_pages if not p.is_closed()]
            for page in pages:
                if await page.locator("#upiAccordionBtn, #qr-click").count():
                    gateway = page
                    break
            else:
                await asyncio.sleep(0.5)
                continue
            break
        accordion = gateway.locator("#upiAccordionBtn")
        if await accordion.count() and await accordion.get_attribute("aria-expanded") != "true":
            await accordion.click()
        qr_radio = gateway.locator("#qr-click")
        if await qr_radio.count():
            await qr_radio.check()
            pay = gateway.get_by_role("button", name=re.compile(r"^Pay Now$", re.I))
            if await pay.count():
                await pay.first.click()
            show = gateway.get_by_text(re.compile(r"^Show QR(?: Code)?$", re.I))
            if await show.count():
                await show.first.click()
        return await gateway.screenshot()

    async def payment_snapshot(self):
        # Gateway-specific screens vary. User can choose a provider in the browser.
        pages = [self.page] + [p for p in self.payment_pages if not p.is_closed()]
        for page in reversed(pages):
            qr = page.locator("img[alt*='QR' i]:visible, img.qr-code:visible, canvas.qr-code:visible, #qrCode img:visible, #qrcode canvas:visible")
            if await qr.count():
                return await qr.first.screenshot()
        return None

    async def confirmation(self):
        if not self.page or self.page.is_closed() or browser_manager.owner != self.owner:
            raise LivePageError("Browser session lost while checking confirmation.")
        if urlparse(self.page.url).hostname != "www.irctc.co.in":
            return None  # The same tab can still be at the payment gateway.
        if not re.search(r"ticketconfirm|confirmation|bookingconfirmed", self.page.url, re.I):
            return None
        text = await self.page.locator("body").inner_text()
        result = parse_confirmation(text)
        if result:
            self.verify_journey(text)
            result["screenshot"] = await self.page.screenshot(full_page=True)
        return result

    def release(self):
        if self.page:
            self.page.context.remove_listener("page", self._page_listener)
        browser_manager.release(self.owner)
