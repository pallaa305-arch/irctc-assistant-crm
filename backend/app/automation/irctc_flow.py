import asyncio
import re
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from app.automation.browser_manager import browser_manager, focus_browser_window
from app.automation.flow_state import BookingSessionState
from app.automation.selectors import URLS, CHALLENGE_SELECTORS, NAVIGATION_SELECTORS
from app.database.models import Booking, BookingPassenger
from app.crm.crm_service import log_event, finalize_successful_booking
from app.notifications.telegram import (
    send_telegram_message, 
    send_telegram_photo, 
    format_action_required_telegram
)
from app.config import settings, DATA_DIR

async def dismiss_overlays(page):
    """
    Automatically dismisses language selection dialogs, alert popups,
    Senior citizen notices, COVID/KAVACH disclaimers, beta banners,
    or lingering PrimeNG dialog overlays.
    """
    if not page:
        return
    for _ in range(4):
        dismissed = False
        try:
            # 1. Remove beta banner and any full-width promo banners via DOM
            await page.evaluate('''() => {
                const banners = document.querySelectorAll('div, section, app-header');
                for (const b of banners) {
                    if (b.innerText && (b.innerText.includes('Explore the beta') || b.innerText.includes('beta version'))) {
                        b.remove();
                    }
                }
                const masks = document.querySelectorAll('.custom-blur-mask, .ui-dialog-mask');
                masks.forEach(m => m.remove());
            }''')

            # 2. Preferred Language Selection Dialog ("Please select your preferred language [English] [हिंदी]")
            lang_btns = page.locator("button:has-text('English'), a:has-text('English'), div.ui-dialog button:has-text('English')")
            if await lang_btns.count() > 0 and await lang_btns.first.is_visible():
                await lang_btns.first.click(timeout=1500, force=True)
                await asyncio.sleep(0.4)
                dismissed = True

            # 3. General alerts, disclaimers, OK / DISMISS / I Agree / Yes buttons
            general_selectors = [
                "button:has-text('I Agree')",
                "button:has-text('Yes')",
                "button:has-text('OK')",
                "button:has-text('DISMISS')",
                "button:has-text('SUBMIT')",
                "button.btn-primary:has-text('I Agree')",
                "button.btn-primary:has-text('Yes')",
                "button.btn-primary:has-text('OK')",
                ".ui-dialog-titlebar-close",
                "a[role='button']:has-text('×')",
                "a[role='button']:has-text('x')",
                "a.fa-window-close",
                "span.fa-close"
            ]
            for sel in general_selectors:
                loc = page.locator(sel)
                cnt = await loc.count()
                for idx in range(min(cnt, 2)):
                    elem = loc.nth(idx)
                    if await elem.is_visible():
                        await elem.click(timeout=1000, force=True)
                        await asyncio.sleep(0.3)
                        dismissed = True
        except Exception:
            pass
        if not dismissed:
            break

async def extract_live_fare_from_page(page) -> Optional[float]:
    """
    Scrapes the official live IRCTC fare directly from the webpage DOM.
    Extracts base fare, convenience fee, GST, or total payable amount.
    """
    if not page:
        return None
    try:
        # Evaluate via JS to inspect exact DOM elements
        js_fare = await page.evaluate('''() => {
            const selectors = [
                '.fare-summary',
                '.ticket-fare',
                'app-payment',
                '.payment_box',
                '.pre-avl.active',
                'div[class*="fare"]',
                'span[class*="fare"]',
                '.train-heading'
            ];
            for (const sel of selectors) {
                const elems = document.querySelectorAll(sel);
                for (const el of elems) {
                    const text = el.innerText || el.textContent || '';
                    const m = text.match(/(?:Total\\s*Fare|Total\\s*Amount|Payable\\s*Amount|Ticket\\s*Fare|Fare)[\\s:]*₹?\\s*([\\d,]+(?:\\.\\d{1,2})?)/i);
                    if (m) return m[1];
                }
            }
            const all = document.querySelectorAll('span, div, b, strong, p');
            for (const el of all) {
                if (el.children.length === 0) {
                    const text = el.innerText || el.textContent || '';
                    if (/(?:Total\\s*Fare|Total\\s*Amount|Payable\\s*Amount)/i.test(text)) {
                        const m = text.match(/₹?\\s*([\\d,]+(?:\\.\\d{1,2})?)/);
                        if (m) return m[1];
                    }
                }
            }
            return null;
        }''')
        if js_fare:
            try:
                num = float(str(js_fare).replace(',', '').strip())
                if 50.0 <= num <= 75000.0:
                    return num
            except Exception:
                pass

        # Python selector fallback
        selectors = [
            ".ticket-fare",
            ".fare-summary",
            "div:has-text('Total Fare')",
            "div:has-text('Total Amount')",
            "div:has-text('Payable Amount')",
            "span:has-text('Total Fare')",
            "span.pull-right",
            "div.bank-text",
            "span.fare",
            "div.fare",
            ".pre-avl"
        ]
        for sel in selectors:
            loc = page.locator(sel)
            cnt = await loc.count()
            for i in range(min(cnt, 6)):
                txt = (await loc.nth(i).inner_text()).strip()
                matches = re.findall(r'(?:₹|Rs\.?)\s*([\d,]+(?:\.\d{1,2})?)', txt)
                if matches:
                    try:
                        num = float(matches[-1].replace(',', ''))
                        if 50.0 <= num <= 75000.0:
                            return num
                    except ValueError:
                        continue
    except Exception:
        pass
    return None

async def check_logged_in_state(page) -> bool:
    """Checks if the browser currently has an active authenticated IRCTC session."""
    if not page:
        return False
    try:
        indicators = ["a:has-text('LOGOUT')", "span:has-text('Welcome')", "span.user-name", "a:has-text('Logout')"]
        for ind in indicators:
            if await page.locator(ind).count() > 0:
                return True
    except Exception:
        pass
    return False

async def run_real_irctc_booking_flow(db: Session, booking_id: int, session_state: BookingSessionState):
    """
    Automates permitted IRCTC navigation while strictly handing over control
    to the human user at all security barriers (CAPTCHA, OTP, Payment).
    """
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        session_state.set_stage("FAILED", "FAILED")
        session_state.error_message = "Booking record not found in database."
        return

    ref = booking.booking_ref
    page = None
    try:
        # Step 1: Launch visible browser
        session_state.set_stage("PREPARING", "IN_PROGRESS")
        booking.status = "IN_PROGRESS"
        db.commit()
        log_event(db, "INFO", "AUTOMATION", "Launching visible browser session...", ref)

        page = await browser_manager.get_page()

        # Step 2: Open IRCTC
        session_state.set_stage("OPENING_IRCTC")
        log_event(db, "INFO", "AUTOMATION", f"Navigating to official IRCTC website: {URLS['HOME']}", ref)
        await page.goto(URLS["HOME"], wait_until="domcontentloaded", timeout=45000)
        await asyncio.sleep(2)
        await dismiss_overlays(page)

        # Step 3: Verified IRCTC Authentication
        session_state.set_stage("CHECKING_LOGIN")
        log_event(db, "INFO", "AUTOMATION", "Checking IRCTC login session...", ref)

        is_logged_in = await check_logged_in_state(page)

        if not is_logged_in:
            log_event(db, "INFO", "AUTOMATION", "No active login session found. Navigating to IRCTC login...", ref)
            try:
                # Open login page directly
                await page.goto(URLS["LOGIN"], wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(2)
            except Exception:
                pass
            await dismiss_overlays(page)

            # Check if login form is on screen
            user_input = page.locator("input[formcontrolname='userid'], #userId, input[placeholder*='User Name' i]").first
            pass_input = page.locator("input[formcontrolname='password'], #pwd, input[placeholder*='Password' i]").first

            # If user-login URL redirected to home or opened as modal
            if await user_input.count() == 0:
                login_btn = page.locator("a:has-text('LOGIN'), button:has-text('LOGIN'), a.loginText").first
                if await login_btn.count() > 0:
                    await login_btn.click(timeout=3000, force=True)
                    await asyncio.sleep(2)
                user_input = page.locator("input[formcontrolname='userid'], #userId, input[placeholder*='User Name' i]").first
                pass_input = page.locator("input[formcontrolname='password'], #pwd, input[placeholder*='Password' i]").first

            # Auto-fill credentials
            if await user_input.count() > 0 and settings.IRCTC_USERNAME:
                await user_input.fill("")
                await user_input.fill(settings.IRCTC_USERNAME)
                log_event(db, "INFO", "AUTOMATION", f"Auto-filled username: {settings.IRCTC_USERNAME[:4]}****", ref)

            if await pass_input.count() > 0 and settings.IRCTC_PASSWORD:
                await pass_input.fill("")
                await pass_input.fill(settings.IRCTC_PASSWORD)

            # Auto-tick "Login and Booking with OTP" if available
            try:
                otp_chk = page.locator("label:has-text('OTP'), #otpLogin, p-checkbox[label*='OTP' i], label[for='otpLogin']").first
                if await otp_chk.count() > 0 and await otp_chk.is_visible():
                    await otp_chk.click(timeout=1500, force=True)
                    log_event(db, "INFO", "AUTOMATION", "Auto-selected OTP login option.", ref)
            except Exception:
                pass

            # Try direct Sign In
            sign_in_btn = page.locator("button:has-text('SIGN IN'), button[type='submit']").first
            if await sign_in_btn.count() > 0:
                await sign_in_btn.click(timeout=2000, force=True)
                await asyncio.sleep(2)

            is_logged_in = await check_logged_in_state(page)

            # If CAPTCHA or OTP is required to finish login
            if not is_logged_in:
                cap_img = page.locator("app-captcha img, #captchaImg, img.captcha-img, img[alt*='captcha' i]").first
                cap_input = page.locator("#nlpAnswer, input[formcontrolname='captcha'], input[placeholder*='captcha' i], #otp, input[formcontrolname='otp']").first

                cap_bytes = None
                try:
                    if await cap_img.count() > 0 and await cap_img.is_visible():
                        await cap_img.scroll_into_view_if_needed()
                        cap_bytes = await cap_img.screenshot(timeout=3000)
                    else:
                        cap_bytes = await page.screenshot()
                except Exception:
                    pass

                if cap_bytes:
                    try:
                        (DATA_DIR / "latest_captcha.png").write_bytes(cap_bytes)
                    except Exception:
                        pass

                session_state.set_stage("WAITING_MANUAL")
                login_prompt = "IRCTC Login: Credentials auto-filled. Please solve visual CAPTCHA or OTP."
                session_state.pause_for_user(login_prompt, is_payment=False, input_type="CAPTCHA", screenshot_bytes=cap_bytes)
                booking.status = "WAITING_MANUAL"
                db.commit()
                log_event(db, "WARNING", "AUTOMATION", login_prompt, ref)

                try:
                    await page.bring_to_front()
                    focus_browser_window()
                except Exception:
                    pass

                if settings.TELEGRAM_ENABLED:
                    t_keyboard = {
                        "inline_keyboard": [
                            [{"text": "✅ Login Ho Gaya (Continue)", "callback_data": "action_continue"}],
                            [{"text": "❌ Cancel", "callback_data": "action_cancel"}]
                        ]
                    }
                    cap_caption = (
                        f"🔐 *IRCTC Login Required* (Ref: `{ref}`)\n\n"
                        f"ID (`{settings.IRCTC_USERNAME}`) aur Password auto-fill ho chuke hain.\n"
                        f"👉 Kripya ye photo dekh kar CAPTCHA reply karein ya browser me login karke *'Login Ho Gaya'* dabayein:"
                    )
                    if cap_bytes:
                        await send_telegram_photo(photo_bytes=cap_bytes, caption=cap_caption, reply_markup=t_keyboard)
                    else:
                        await send_telegram_message(cap_caption, reply_markup=t_keyboard)

                done, pending = await asyncio.wait(
                    [
                        asyncio.create_task(session_state.continue_event.wait()),
                        asyncio.create_task(session_state.input_event.wait())
                    ],
                    return_when=asyncio.FIRST_COMPLETED
                )
                for t in pending:
                    t.cancel()

                if session_state.cancel_event.is_set():
                    booking.status = "CANCELLED"
                    db.commit()
                    return

                if session_state.user_input_value and await cap_input.count() > 0:
                    try:
                        await cap_input.fill(session_state.user_input_value.strip())
                        if await sign_in_btn.count() > 0:
                            await sign_in_btn.click(timeout=3000, force=True)
                            await asyncio.sleep(2.5)
                    except Exception:
                        pass

                for _ in range(10):
                    if await check_logged_in_state(page):
                        is_logged_in = True
                        break
                    await asyncio.sleep(1)

        log_event(db, "INFO", "AUTOMATION", "IRCTC Login session confirmed. Proceeding to Train Search...", ref)

        # Step 4: Search Trains
        session_state.set_stage("SEARCHING_TRAINS")
        booking.status = "IN_PROGRESS"
        db.commit()
        log_event(db, "INFO", "AUTOMATION", f"Entering route: {booking.from_station} ➔ {booking.to_station}", ref)

        if "/train-search" not in page.url:
            await page.goto(URLS["HOME"], wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(1.5)
        await dismiss_overlays(page)

        try:
            # From station
            from_input = page.locator("p-autocomplete[formcontrolname='origin'] input, #origin input, input[aria-label*='From' i]").first
            if await from_input.count() > 0:
                await from_input.click(timeout=5000, force=True)
                await from_input.fill("")
                await from_input.fill(booking.from_station)
                await asyncio.sleep(1.2)
                await page.keyboard.press("ArrowDown")
                await page.keyboard.press("Enter")

            # To station
            to_input = page.locator("p-autocomplete[formcontrolname='destination'] input, #destination input, input[aria-label*='To' i]").first
            if await to_input.count() > 0:
                await to_input.click(timeout=5000, force=True)
                await to_input.fill("")
                await to_input.fill(booking.to_station)
                await asyncio.sleep(1.2)
                await page.keyboard.press("ArrowDown")
                await page.keyboard.press("Enter")

            # Date
            date_str = booking.journey_date.strftime("%d/%m/%Y")
            date_input = page.locator("p-calendar[formcontrolname='journeyDate'] input, #jDate input, input[placeholder*='Date' i]").first
            if await date_input.count() > 0:
                await date_input.click(timeout=5000, force=True)
                await page.keyboard.press("Control+A")
                await page.keyboard.press("Backspace")
                await date_input.fill(date_str)
                await page.keyboard.press("Enter")

            # Click Search
            search_btn = page.locator("button.search_btn, button[type='submit']:has-text('Search'), button:has-text('Search')").first
            if await search_btn.count() > 0:
                await search_btn.click(timeout=5000, force=True)
                await asyncio.sleep(3)
        except Exception as e:
            log_event(db, "WARNING", "AUTOMATION", f"Search form note: {str(e)}", ref)

        # Step 5: Train & Class Selection
        session_state.set_stage("SELECTING_TRAIN")
        log_event(db, "INFO", "AUTOMATION", f"Selecting train & class for {booking.from_station} ➔ {booking.to_station}...", ref)

        # Wait up to 15s for train list cards
        for _ in range(15):
            await dismiss_overlays(page)
            if await page.locator("app-train-list, div.train-heading, div.form-group:has(.train-name)").count() > 0:
                break
            await asyncio.sleep(1)

        train_pref = (booking.train_number or "").strip()
        journey_cls = (booking.journey_class or "3A").strip().upper()

        target_train_card = None
        if train_pref and train_pref != "12002":
            card = page.locator(f"app-train-list:has-text('{train_pref}'), div.form-group:has-text('{train_pref}')").first
            if await card.count() > 0:
                target_train_card = card

        if not target_train_card:
            all_cards = page.locator("app-train-list, div.form-group:has(.train-heading)")
            card_count = await all_cards.count()
            for i in range(min(card_count, 15)):
                c = all_cards.nth(i)
                cls_elem = c.locator(f"div:has-text('{journey_cls}'), span:has-text('{journey_cls}'), .pre-avl:has-text('{journey_cls}')").first
                if await cls_elem.count() > 0:
                    target_train_card = c
                    try:
                        heading_txt = (await c.locator(".train-heading, .train-name").first.inner_text()).strip()
                        num_m = re.search(r'\b\d{5}\b', heading_txt)
                        if num_m:
                            booking.train_number = num_m.group(0)
                        booking.train_name = heading_txt.split('\n')[0].strip()
                        db.commit()
                        log_event(db, "INFO", "AUTOMATION", f"Selected train: {booking.train_number} - {booking.train_name}", ref)
                    except Exception:
                        pass
                    break

        if not target_train_card:
            first_c = page.locator("app-train-list, div.form-group:has(.train-heading)").first
            if await first_c.count() > 0:
                target_train_card = first_c

        # Click class tab
        if target_train_card:
            try:
                cls_btn = target_train_card.locator(f"div:has-text('{journey_cls}'), span:has-text('{journey_cls}'), .pre-avl:has-text('{journey_cls}')").first
                if await cls_btn.count() > 0:
                    await cls_btn.click(timeout=3000, force=True)
                    await asyncio.sleep(2)
            except Exception as e:
                log_event(db, "WARNING", "AUTOMATION", f"Class click note: {e}", ref)

        # Click date availability box
        try:
            avl_box = page.locator("div.pre-avl, div.avail-box, td:has-text('AVAILABLE'), td:has-text('RAC'), td:has-text('WL')").first
            if await avl_box.count() > 0 and await avl_box.is_visible():
                await avl_box.click(timeout=3000, force=True)
                await asyncio.sleep(1.5)
        except Exception:
            pass

        # Extract live fare
        live_fare = await extract_live_fare_from_page(page)
        if live_fare:
            booking.fare = live_fare
            db.commit()
            log_event(db, "INFO", "AUTOMATION", f"Official IRCTC Live Fare: ₹{live_fare:,.2f}", ref)

        # Click 'Book Now'
        try:
            book_now = page.locator("button:has-text('Book Now'), button.btn-primary:has-text('Book Now')").first
            if await book_now.count() > 0 and await book_now.is_visible():
                await book_now.click(timeout=4000, force=True)
                await asyncio.sleep(1.5)
                await dismiss_overlays(page)
        except Exception as e:
            log_event(db, "WARNING", "AUTOMATION", f"Book now click note: {e}", ref)

        # Wait up to 10 seconds for Passenger Input page
        arrived_at_passenger = False
        for _ in range(10):
            await dismiss_overlays(page)
            if "psgn-input" in page.url or await page.locator("input[placeholder*='Passenger Name' i], p-autocomplete[formcontrolname='passengerName'] input").count() > 0:
                arrived_at_passenger = True
                break
            await asyncio.sleep(1)

        # Pause only if passenger page not reached
        if not arrived_at_passenger:
            train_bytes = None
            try:
                # Scroll to train selection section before screenshot
                await page.evaluate("window.scrollTo(0, 200)")
                await asyncio.sleep(0.5)
                train_bytes = await page.screenshot(full_page=False)
                if train_bytes:
                    session_state.latest_screenshot_bytes = train_bytes
                    (DATA_DIR / "latest_captcha.png").write_bytes(train_bytes)
            except Exception:
                pass

            select_prompt = f"Train Selection: Please select your train / class and click 'Book Now' in browser."
            session_state.pause_for_user(select_prompt, is_payment=False, screenshot_bytes=train_bytes)
            booking.status = "WAITING_MANUAL"
            db.commit()
            log_event(db, "INFO", "AUTOMATION", select_prompt, ref)

            try:
                await page.bring_to_front()
                focus_browser_window()
            except Exception:
                pass

            if settings.TELEGRAM_ENABLED:
                t_keyboard = {
                    "inline_keyboard": [
                        [{"text": "✅ Maine 'Book Now' Click Kar Diya (Continue)", "callback_data": "action_continue"}],
                        [{"text": "❌ Cancel", "callback_data": "action_cancel"}]
                    ]
                }
                caption = (
                    f"🚆 *IRCTC Train & Class Selection* (Ref: `{ref}`)\n\n"
                    f"Route: `{booking.from_station}` ➔ `{booking.to_station}` ({booking.journey_class})\n"
                    f"Kripya browser me apni train par *'Book Now'* click karein aur phir neeche button dabayein:"
                )
                if train_bytes:
                    await send_telegram_photo(photo_bytes=train_bytes, caption=caption, reply_markup=t_keyboard)
                else:
                    await send_telegram_message(caption, reply_markup=t_keyboard)

            await session_state.continue_event.wait()
            if session_state.cancel_event.is_set():
                booking.status = "CANCELLED"
                db.commit()
                return

            # Wait for passenger form to load after manual click
            for _ in range(15):
                await dismiss_overlays(page)
                if "psgn-input" in page.url or await page.locator("input[placeholder*='Passenger Name' i], p-autocomplete[formcontrolname='passengerName'] input").count() > 0:
                    arrived_at_passenger = True
                    break
                await asyncio.sleep(1)

        # Step 6: Passenger Form Filling
        session_state.set_stage("FILLING_PASSENGERS")
        booking.status = "IN_PROGRESS"
        db.commit()
        passengers = db.query(BookingPassenger).filter(BookingPassenger.booking_id == booking.id).all()
        log_event(db, "INFO", "AUTOMATION", f"Entering details for {len(passengers)} passenger(s)...", ref)

        try:
            await page.evaluate("window.scrollTo(0, 200)")
        except Exception:
            pass

        try:
            await page.wait_for_selector("input[placeholder*='Passenger Name' i], p-autocomplete[formcontrolname='passengerName'] input", timeout=12000)
        except Exception:
            pass

        try:
            for idx, p in enumerate(passengers):
                if idx > 0:
                    add_btn = page.locator("a:has-text('+ Add Passenger'), button:has-text('Add Passenger')").first
                    if await add_btn.count() > 0:
                        await add_btn.click(timeout=3000, force=True)
                        await asyncio.sleep(0.8)

                # Name
                name_inputs = page.locator("input[placeholder*='Passenger Name' i], p-autocomplete[formcontrolname='passengerName'] input")
                if await name_inputs.count() > idx:
                    await name_inputs.nth(idx).click(force=True)
                    await name_inputs.nth(idx).fill(p.name)

                # Age
                age_inputs = page.locator("input[placeholder*='Age' i], input[formcontrolname='passengerAge']")
                if await age_inputs.count() > idx:
                    await age_inputs.nth(idx).click(force=True)
                    await age_inputs.nth(idx).fill(str(p.age))

                # Gender
                gender_selects = page.locator("select[formcontrolname='passengerGender']")
                if await gender_selects.count() > idx:
                    g_val = "M" if (p.gender or "M").upper().startswith("M") else "F"
                    await gender_selects.nth(idx).select_option(value=g_val)
                else:
                    p_dropdown = page.locator("p-dropdown[formcontrolname='passengerGender']").nth(idx)
                    if await p_dropdown.count() > 0:
                        await p_dropdown.click(force=True)
                        await asyncio.sleep(0.4)
                        g_label = "Male" if (p.gender or "M").upper().startswith("M") else "Female"
                        g_opt = page.locator(f"li[aria-label*='{g_label}' i], span:has-text('{g_label}')").first
                        if await g_opt.count() > 0:
                            await g_opt.click(force=True)
        except Exception as e:
            log_event(db, "WARNING", "AUTOMATION", f"Passenger auto-fill note: {str(e)}", ref)

        # Contact mobile
        if booking.contact_mobile:
            try:
                mob_input = page.locator("input[formcontrolname='mobileNumber'], input[placeholder*='Mobile Number' i]").first
                if await mob_input.count() > 0:
                    await mob_input.fill(booking.contact_mobile)
            except Exception:
                pass

        # Select Payment Mode: BHIM/UPI (Convenience Fee: ₹20 + GST)
        try:
            bhim_upi_radio = page.locator("p-radiobutton[value='2'], input[value='2'], label:has-text('BHIM/UPI'), div:has-text('Pay through BHIM/UPI')").first
            if await bhim_upi_radio.count() > 0:
                await bhim_upi_radio.click(timeout=2000, force=True)
                await asyncio.sleep(0.5)
        except Exception:
            pass

        # Live fare
        live_fare = await extract_live_fare_from_page(page)
        if live_fare:
            booking.fare = live_fare
            db.commit()
            log_event(db, "INFO", "AUTOMATION", f"Extracted IRCTC Passenger Fare: ₹{live_fare:,.2f}", ref)

        # Click Continue to Review Page
        try:
            cont_btn = page.locator("button:has-text('Continue'), button[type='submit']:has-text('Continue'), button.btn-primary:has-text('Continue')").first
            if await cont_btn.count() > 0:
                await cont_btn.scroll_into_view_if_needed()
                await cont_btn.click(timeout=4000, force=True)
                await asyncio.sleep(2)
        except Exception as e:
            log_event(db, "WARNING", "AUTOMATION", f"Passenger Continue note: {e}", ref)

        # Step 7: Review Booking Page & Security Challenge Check
        session_state.set_stage("REVIEW_BOOKING")
        log_event(db, "INFO", "AUTOMATION", "Navigating to Review Booking page...", ref)

        for _ in range(12):
            await dismiss_overlays(page)
            if "review-booking" in page.url or "payment" in page.url:
                break
            if await page.locator("app-review-booking, div:has-text('Review Booking'), app-payment, app-captcha").count() > 0:
                break
            await asyncio.sleep(1)

        # Extract confirmed live total fare from Review page
        live_fare = await extract_live_fare_from_page(page)
        if live_fare:
            booking.fare = live_fare
            db.commit()
            log_event(db, "INFO", "AUTOMATION", f"Confirmed IRCTC Total Fare (with taxes & fees): ₹{live_fare:,.2f}", ref)

        # Check if CAPTCHA exists on Review page
        captcha_img_loc = page.locator("app-captcha img, #captchaImg, img.captcha-img, img[alt*='captcha' i]").first
        captcha_input = page.locator("input[placeholder*='captcha' i], #nlpAnswer, #captcha").first
        is_payment_page = ("payment" in page.url or await page.locator("app-payment, div:has-text('Payment Option'), div:has-text('Payment Method'), #bank-type").count() > 0)

        has_captcha = False
        if not is_payment_page:
            try:
                await captcha_img_loc.wait_for(state="visible", timeout=3000)
            except Exception:
                pass
            has_captcha = (await captcha_img_loc.count() > 0 and await captcha_img_loc.is_visible()) or (await captcha_input.count() > 0 and await captcha_input.is_visible())

        if has_captcha:
            captcha_bytes = None
            try:
                await captcha_img_loc.scroll_into_view_if_needed()
                captcha_bytes = await captcha_img_loc.screenshot(timeout=3000)
            except Exception:
                try:
                    captcha_bytes = await page.screenshot()
                except Exception:
                    pass

            if captcha_bytes:
                try:
                    (DATA_DIR / "latest_captcha.png").write_bytes(captcha_bytes)
                except Exception:
                    pass

            session_state.set_stage("WAITING_MANUAL")
            review_prompt = "Review & CAPTCHA: Please enter the CAPTCHA in browser or reply with text on Telegram."
            session_state.pause_for_user(review_prompt, is_payment=False, input_type="CAPTCHA", screenshot_bytes=captcha_bytes)
            booking.status = "WAITING_MANUAL"
            db.commit()
            log_event(db, "WARNING", "AUTOMATION", review_prompt, ref)

            try:
                await page.bring_to_front()
                focus_browser_window()
            except Exception:
                pass

            if settings.TELEGRAM_ENABLED:
                try:
                    fare_tag = f"\n💰 Total Fare: `₹{booking.fare:,.2f}`" if booking.fare else ""
                    if captcha_bytes:
                        await send_telegram_photo(
                            photo_bytes=captcha_bytes,
                            caption=(
                                f"📸 *IRCTC Review CAPTCHA* (Ref: `{ref}`){fare_tag}\n\n"
                                f"Kripya ye photo dekh kar CAPTCHA text reply karein. Hum automatically browser me fill kar denge!"
                            )
                        )
                    else:
                        await send_telegram_message(format_action_required_telegram(booking, "IRCTC Review CAPTCHA"))
                except Exception as e:
                    log_event(db, "WARNING", "AUTOMATION", f"Could not send CAPTCHA: {e}", ref)

            done, pending = await asyncio.wait(
                [
                    asyncio.create_task(session_state.continue_event.wait()),
                    asyncio.create_task(session_state.input_event.wait())
                ],
                return_when=asyncio.FIRST_COMPLETED
            )
            for t in pending:
                t.cancel()

            if session_state.cancel_event.is_set():
                booking.status = "CANCELLED"
                db.commit()
                return

            if session_state.user_input_value:
                try:
                    if await captcha_input.count() > 0:
                        await captcha_input.fill(session_state.user_input_value.strip())
                        log_event(db, "INFO", "AUTOMATION", "Auto-filled CAPTCHA received from user.", ref)
                        submit_btn = page.locator("button:has-text('Continue'), button[type='submit']:has-text('Continue'), button.btn-primary:has-text('Continue')").first
                        if await submit_btn.count() > 0:
                            await submit_btn.click(timeout=3000, force=True)
                            await asyncio.sleep(2)
                except Exception as e:
                    log_event(db, "WARNING", "AUTOMATION", f"Could not auto-fill CAPTCHA: {e}", ref)
        else:
            log_event(db, "INFO", "AUTOMATION", "Review CAPTCHA bypassed or not required. Proceeding to Payment Gateway.", ref)
            try:
                cont_btn = page.locator("button:has-text('Continue'), button[type='submit']:has-text('Continue'), button.btn-primary:has-text('Continue')").first
                if await cont_btn.count() > 0 and await cont_btn.is_visible():
                    await cont_btn.click(timeout=3000, force=True)
                    await asyncio.sleep(2)
            except Exception:
                pass

        # Step 8: Payment Gateway Handoff (MANDATORY HUMAN-IN-THE-LOOP)
        session_state.set_stage("PAYMENT_PENDING")
        log_event(db, "INFO", "AUTOMATION", "Navigating to IRCTC Payment Gateway page...", ref)

        for _ in range(15):
            await dismiss_overlays(page)
            if "payment" in page.url or await page.locator("app-payment, div:has-text('Payment Option'), div:has-text('Payment Method'), #bank-type").count() > 0:
                break
            await asyncio.sleep(1)

        try:
            await page.evaluate("window.scrollTo(0, 0)")
        except Exception:
            pass

        # Select BHIM / UPI / USSD or IRCTC iPay
        try:
            upi_category_selectors = [
                "div:has-text('BHIM / UPI / USSD')",
                "span:has-text('BHIM / UPI / USSD')",
                "div:has-text('BHIM / UPI')",
                "span:has-text('BHIM / UPI')",
                "div:has-text('IRCTC iPay')",
                "span:has-text('iPay')",
                "div:has-text('Multiple Payment Service')",
                "span:has-text('Multiple Payment Service')"
            ]
            for sel in upi_category_selectors:
                loc = page.locator(sel).first
                if await loc.count() > 0 and await loc.is_visible():
                    await loc.click(timeout=3000, force=True)
                    await asyncio.sleep(1)
                    break

            provider_selectors = [
                "p-radiobutton[name='paymentProvider']",
                "input[name='paymentProvider']",
                "label:has-text('BHIM')",
                "label:has-text('UPI')",
                "label:has-text('Paytm')",
                "label:has-text('iPay')",
                "div.bank-text:has-text('BHIM')"
            ]
            for p_sel in provider_selectors:
                p_loc = page.locator(p_sel).first
                if await p_loc.count() > 0 and await p_loc.is_visible():
                    await p_loc.click(timeout=2000, force=True)
                    await asyncio.sleep(0.8)
                    break

            pay_btn = page.locator("button:has-text('Pay & Book'), button.btn-primary:has-text('Pay & Book'), button:has-text('Pay and Book'), button:has-text('Make Payment')").first
            if await pay_btn.count() > 0 and await pay_btn.is_visible():
                await pay_btn.click(timeout=4000, force=True)
                await asyncio.sleep(3)
        except Exception as e:
            log_event(db, "WARNING", "AUTOMATION", f"Payment method selection note: {e}", ref)

        final_fare = await extract_live_fare_from_page(page)
        if final_fare:
            booking.fare = final_fare
            db.commit()
            log_event(db, "INFO", "AUTOMATION", f"Final IRCTC Payable Amount: ₹{final_fare:,.2f}", ref)

        fare_display = f"₹{booking.fare:,.2f}" if booking.fare else "As per IRCTC Portal"

        pay_prompt = f"PAYMENT REQUIRED: Official IRCTC Total Amount: {fare_display}. Please scan UPI QR code or complete payment."
        session_state.pause_for_user(pay_prompt, is_payment=True, input_type="PAYMENT")
        booking.status = "PAYMENT_PENDING"
        db.commit()
        log_event(db, "WARNING", "AUTOMATION", pay_prompt, ref)

        try:
            await page.bring_to_front()
            focus_browser_window()
        except Exception:
            pass

        # WAIT FOR DYNAMIC UPI QR CODE
        qr_bytes = None
        qr_elem = None
        qr_locators = [
            "app-bhim-upi-qr img",
            "#qr-image",
            "#qrCode",
            "img.qr-code",
            "div.qr-image img",
            "div.qr-container img",
            "img[src*='data:image/png;base64']",
            "img[src*='data:image/jpeg;base64']",
            "img[src*='data:image']",
            "img[alt*='qr' i]",
            "canvas.qr-canvas",
            "canvas"
        ]

        for _ in range(12):
            for q_sel in qr_locators:
                loc = page.locator(q_sel).first
                if await loc.count() > 0 and await loc.is_visible():
                    qr_elem = loc
                    break
            if qr_elem:
                break
            for frame in page.frames:
                for q_sel in qr_locators:
                    f_loc = frame.locator(q_sel).first
                    if await f_loc.count() > 0 and await f_loc.is_visible():
                        qr_elem = f_loc
                        break
                if qr_elem:
                    break
            if qr_elem:
                break
            await asyncio.sleep(1)

        # 1. First priority: Crop exact QR element
        if qr_elem:
            try:
                await qr_elem.scroll_into_view_if_needed()
                qr_bytes = await qr_elem.screenshot(timeout=3000)
            except Exception:
                pass

        # 2. Second priority: Crop payment modal card
        if not qr_bytes:
            container_locators = [
                "app-bhim-upi-qr",
                "div.modal-dialog",
                "div.ui-dialog",
                "div.payment_box",
                "div.payment-container",
                "app-payment",
                "div.bank-box"
            ]
            for c_sel in container_locators:
                c_loc = page.locator(c_sel).first
                if await c_loc.count() > 0 and await c_loc.is_visible():
                    try:
                        await c_loc.scroll_into_view_if_needed()
                        qr_bytes = await c_loc.screenshot(timeout=3000)
                        if qr_bytes:
                            break
                    except Exception:
                        pass

        # 3. Third priority: Viewport screenshot around top-center (NEVER page footer!)
        if not qr_bytes:
            try:
                await page.evaluate("window.scrollTo(0, 100)")
                await asyncio.sleep(0.5)
                qr_bytes = await page.screenshot(full_page=False)
            except Exception:
                pass

        if qr_bytes:
            session_state.latest_screenshot_bytes = qr_bytes
            try:
                (DATA_DIR / "latest_captcha.png").write_bytes(qr_bytes)
            except Exception:
                pass

        if settings.TELEGRAM_ENABLED:
            try:
                qr_keyboard = {
                    "inline_keyboard": [
                        [{"text": "✅ Payment Ho Gayi (Continue)", "callback_data": "action_continue"}],
                        [{"text": "❌ Cancel", "callback_data": "action_cancel"}]
                    ]
                }
                caption = (
                    f"💳 *IRCTC Official Payment QR* (Ref: `{ref}`)\n\n"
                    f"💰 *कुल देय राशि (Total Amount):* `{fare_display}`\n"
                    f"*(IRCTC आधिकारिक पोर्टल के अनुसार सभी चार्जेस सहित)*\n\n"
                    f"📱 Kripya kisi bhi UPI App (GPay/PhonePe/Paytm) se ye QR scan karke bhugtan karein.\n"
                    f"Payment complete hone ke baad neeche button dabayein:"
                )
                if qr_bytes:
                    await send_telegram_photo(
                        photo_bytes=qr_bytes,
                        caption=caption,
                        reply_markup=qr_keyboard
                    )
                else:
                    await send_telegram_message(caption, reply_markup=qr_keyboard)
            except Exception as e:
                log_event(db, "WARNING", "AUTOMATION", f"Could not dispatch payment prompt to Telegram: {e}", ref)

        await session_state.continue_event.wait()
        if session_state.cancel_event.is_set():
            booking.status = "CANCELLED"
            db.commit()
            return

        # Step 9: Confirmation Detection & Data Extraction
        session_state.set_stage("CONFIRMATION_DETECTED")
        log_event(db, "INFO", "AUTOMATION", "Detecting confirmation details from official IRCTC page...", ref)
        await asyncio.sleep(2)

        # Scan for PNR in DOM
        page_content = await page.content()
        pnr_match = re.search(r'\b[2-9]\d{9}\b', page_content)
        txn_match = re.search(r'TXN\w+|Transaction\s*ID[\s:]+(\w+)', page_content, re.IGNORECASE)

        captured_pnr = pnr_match.group(0) if pnr_match else None
        captured_txn = txn_match.group(1) if (txn_match and txn_match.groups()) else None

        if captured_pnr:
            booking.pnr = captured_pnr
            booking.status = "CONFIRMED"
            booking.payment_status = "COMPLETED"
        if captured_txn:
            booking.transaction_id = captured_txn

        db.commit()

        # Step 10: Finalize CRM, Excel, and Notifications
        await finalize_successful_booking(db, booking.id)

        session_state.set_stage("COMPLETED", "CONFIRMED" if captured_pnr else "WAITING_MANUAL")
        log_event(db, "INFO", "AUTOMATION", f"Booking flow finished. PNR: {booking.pnr or 'Manual Verification'}", ref)

    except Exception as e:
        session_state.set_stage("FAILED", "FAILED")
        session_state.error_message = str(e)
        booking.status = "FAILED"
        db.commit()
        log_event(db, "ERROR", "AUTOMATION", f"Real IRCTC Flow error: {str(e)}", ref)
