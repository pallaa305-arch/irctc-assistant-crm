import asyncio
import re
from datetime import datetime
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
    COVID/KAVACH disclaimers, or lingering PrimeNG dialog overlays.
    """
    for _ in range(3):
        dismissed = False
        try:
            # 1. Preferred Language Selection Dialog ("Please select your preferred language [हिंदी] [English]")
            lang_btns = page.locator("button:has-text('English'), a:has-text('English'), div.ui-dialog button:has-text('English')")
            if await lang_btns.count() > 0 and await lang_btns.first.is_visible():
                await lang_btns.first.click(timeout=1500, force=True)
                await asyncio.sleep(0.4)
                dismissed = True

            # 2. General alerts, disclaimers, OK / DISMISS / I Agree buttons
            general_selectors = [
                "button:has-text('OK')",
                "button:has-text('DISMISS')",
                "button:has-text('I Agree')",
                "button:has-text('SUBMIT')",
                "button.btn-primary:has-text('OK')",
                ".ui-dialog-titlebar-close",
                "a[role='button']:has-text('×')",
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
    Scrapes the official live IRCTC fare directly from the webpage.
    Extracts base fare, convenience fee, GST, or total amount displayed.
    """
    try:
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
            "div.fare"
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
                        if 50.0 <= num <= 50000.0:
                            return num
                    except ValueError:
                        continue
    except Exception:
        pass
    return None

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

        # Automatically dismiss language selection dialog and any alert disclaimers
        await dismiss_overlays(page)

        # Step 3: Check Login Status (Direct Login Support)
        is_already_logged_in = False
        try:
            logged_in_indicator = page.locator("a:has-text('LOGOUT'), span:has-text('Welcome'), span.user-name")
            if await logged_in_indicator.count() > 0:
                is_already_logged_in = True
                log_event(db, "INFO", "AUTOMATION", "Active IRCTC login session detected via persistent profile.", ref)
        except Exception:
            pass

        if not is_already_logged_in:
            login_btn = page.locator("a:has-text('LOGIN'), button:has-text('LOGIN')")
            if await login_btn.count() > 0 and await login_btn.first.is_visible():
                log_event(db, "INFO", "AUTOMATION", "Opening IRCTC login dialog...", ref)
                try:
                    await login_btn.first.click(timeout=3000, force=True)
                    await asyncio.sleep(1.5)
                except Exception:
                    pass

            # Match specifically the login modal (must contain username field or app-login)
            login_modal = page.locator("app-login, div.ui-dialog:has(input[formcontrolname='userid']), div.ui-dialog:has(#userId)").first
            modal_open = (await login_modal.count() > 0)

            if modal_open:
                # 3a. Auto-fill Username
                if settings.IRCTC_USERNAME:
                    try:
                        u_input = login_modal.locator("input[formcontrolname='userid'], #userId, input[placeholder*='User Name' i]").first
                        if await u_input.count() > 0:
                            await u_input.fill(settings.IRCTC_USERNAME, timeout=3000)
                    except Exception as e:
                        log_event(db, "WARNING", "AUTOMATION", f"Could not auto-fill username: {e}", ref)

                # 3b. Auto-fill Password
                if settings.IRCTC_PASSWORD:
                    try:
                        p_input = login_modal.locator("input[formcontrolname='password'], #pwd, input[placeholder*='Password' i]").first
                        if await p_input.count() > 0:
                            await p_input.fill(settings.IRCTC_PASSWORD, timeout=3000)
                    except Exception as e:
                        log_event(db, "WARNING", "AUTOMATION", f"Could not auto-fill password: {e}", ref)

                # 3c. Auto-tick OTP Checkbox
                try:
                    otp_checkbox = login_modal.locator("label:has-text('OTP'), p-checkbox[label*='OTP' i], label[for='otpLogin'], #otpLogin").first
                    if await otp_checkbox.count() > 0:
                        await otp_checkbox.click(timeout=2000, force=True)
                        log_event(db, "INFO", "AUTOMATION", "Auto-ticked 'Login with OTP / Remember' checkbox.", ref)
                except Exception as e:
                    log_event(db, "WARNING", "AUTOMATION", f"OTP checkbox note: {e}", ref)

                # 3d. Direct Login Attempt (Click SIGN IN immediately)
                try:
                    sign_in_btn = login_modal.locator("button:has-text('SIGN IN'), button[type='submit']").first
                    if await sign_in_btn.count() > 0:
                        await sign_in_btn.click(timeout=2000, force=True)
                        await asyncio.sleep(2)
                except Exception:
                    pass

                # Check if direct login succeeded without CAPTCHA
                for _ in range(4):
                    if await page.locator("a:has-text('LOGOUT'), span:has-text('Welcome')").count() > 0:
                        is_already_logged_in = True
                        log_event(db, "INFO", "AUTOMATION", "Direct IRCTC login succeeded without requiring CAPTCHA.", ref)
                        break
                    await asyncio.sleep(0.8)

                # 3e. Only pause if login did not succeed and CAPTCHA / OTP is actively waiting
                if not is_already_logged_in:
                    login_cap_img = login_modal.locator("app-captcha img, #captchaImg, img.captcha-img, img[alt*='captcha' i], .captcha-img").first
                    login_cap_input = login_modal.locator("#nlpAnswer, input[formcontrolname='captcha'], input[placeholder*='captcha' i], #otp, input[formcontrolname='otp']").first

                    if await login_modal.is_visible() and (await login_cap_input.count() > 0 or await login_cap_img.count() > 0):
                        try:
                            await login_cap_img.wait_for(state="visible", timeout=3000)
                        except Exception:
                            pass

                        screenshot_bytes = None
                        try:
                            if await login_cap_img.count() > 0 and await login_cap_img.is_visible():
                                screenshot_bytes = await login_cap_img.screenshot(timeout=3000)
                            else:
                                screenshot_bytes = await login_modal.screenshot(timeout=3000)
                        except Exception:
                            try:
                                screenshot_bytes = await page.screenshot()
                            except Exception:
                                pass

                        if screenshot_bytes:
                            try:
                                (DATA_DIR / "latest_captcha.png").write_bytes(screenshot_bytes)
                            except Exception:
                                pass

                        session_state.set_stage("WAITING_MANUAL")
                        login_prompt = "IRCTC Login: Credentials auto-filled. Please enter CAPTCHA/OTP or reply on Telegram."
                        session_state.pause_for_user(login_prompt, is_payment=False, input_type="CAPTCHA", screenshot_bytes=screenshot_bytes)
                        booking.status = "WAITING_MANUAL"
                        db.commit()
                        log_event(db, "WARNING", "AUTOMATION", login_prompt, ref)

                        # Bring browser window to front
                        try:
                            await page.bring_to_front()
                            focus_browser_window()
                        except Exception:
                            pass

                        if settings.TELEGRAM_ENABLED:
                            if screenshot_bytes:
                                try:
                                    await send_telegram_photo(
                                        photo_bytes=screenshot_bytes,
                                        caption=(
                                            f"🔐 *IRCTC Login CAPTCHA / OTP* (Ref: `{ref}`)\n\n"
                                            f"ID aur Password auto-fill ho gaye hain.\n"
                                            f"👉 Kripya ye photo dekh kar CAPTCHA text ya OTP reply karein (Hum browser me auto-fill kar denge):"
                                        )
                                    )
                                except Exception as e:
                                    log_event(db, "WARNING", "AUTOMATION", f"Could not send login CAPTCHA photo: {e}", ref)
                                    await send_telegram_message(format_action_required_telegram(booking, "IRCTC Login (Solve CAPTCHA/OTP)"))
                            else:
                                await send_telegram_message(format_action_required_telegram(booking, "IRCTC Login (Solve CAPTCHA/OTP)"))

                        # Wait for user reply from Telegram or Web Dashboard
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
                            log_event(db, "INFO", "AUTOMATION", "Booking cancelled during login.", ref)
                            return

                        # If user replied with CAPTCHA/OTP text, auto-fill and submit
                        if session_state.user_input_value:
                            try:
                                if await login_cap_input.count() > 0:
                                    await login_cap_input.fill(session_state.user_input_value.strip())
                                    log_event(db, "INFO", "AUTOMATION", "Auto-filled Login CAPTCHA/OTP received from user.", ref)
                                    sign_in_btn = login_modal.locator("button:has-text('SIGN IN'), button[type='submit']").first
                                    if await sign_in_btn.count() > 0:
                                        await sign_in_btn.click(timeout=3000, force=True)
                                        await asyncio.sleep(2)
                            except Exception as e:
                                log_event(db, "WARNING", "AUTOMATION", f"Could not auto-submit login: {e}", ref)

                        # Give login up to 4 seconds to settle
                        for _ in range(4):
                            if await page.locator("a:has-text('LOGOUT'), span:has-text('Welcome')").count() > 0:
                                is_already_logged_in = True
                                break
                            await asyncio.sleep(1)

        # Ensure no lingering dialogs or masks block the search form
        await dismiss_overlays(page)

        # Step 4: Search Trains
        session_state.set_stage("SEARCHING_TRAINS")
        log_event(db, "INFO", "AUTOMATION", f"Entering route: {booking.from_station} ➔ {booking.to_station}", ref)

        try:
            # Dismiss any dialog mask if present
            mask = page.locator(".custom-blur-mask, .ui-dialog-mask")
            if await mask.count() > 0 and await mask.first.is_visible():
                await dismiss_overlays(page)

            # Enter From station
            from_input = page.locator("p-autocomplete[formcontrolname='origin'] input, #origin input, input[aria-label*='From' i]").first
            if await from_input.count() > 0:
                await from_input.click(timeout=5000, force=True)
                await from_input.fill("")
                await from_input.fill(booking.from_station)
                await asyncio.sleep(1.2)
                await page.keyboard.press("ArrowDown")
                await page.keyboard.press("Enter")

            # Enter To station
            to_input = page.locator("p-autocomplete[formcontrolname='destination'] input, #destination input, input[aria-label*='To' i]").first
            if await to_input.count() > 0:
                await to_input.click(timeout=5000, force=True)
                await to_input.fill("")
                await to_input.fill(booking.to_station)
                await asyncio.sleep(1.2)
                await page.keyboard.press("ArrowDown")
                await page.keyboard.press("Enter")

            # Enter Date
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
            log_event(db, "WARNING", "AUTOMATION", f"Search form note: {str(e)}. Please confirm search in browser.", ref)

        # Step 5: Train & Class Selection
        session_state.set_stage("SELECTING_TRAIN")
        log_event(db, "INFO", "AUTOMATION", f"Selecting best train & class on IRCTC for {booking.from_station} ➔ {booking.to_station}...", ref)

        try:
            await page.wait_for_selector("app-train-list, div.train-heading, div.form-group", timeout=8000)
        except Exception:
            pass
        await asyncio.sleep(1.5)
        await dismiss_overlays(page)

        train_pref = (booking.train_number or "").strip()
        journey_cls = (booking.journey_class or "3A").strip().upper()

        # Step 5a: Target a train card
        target_train_card = None
        if train_pref and train_pref != "12002":
            card = page.locator(f"app-train-list:has-text('{train_pref}'), div.form-group:has-text('{train_pref}')").first
            if await card.count() > 0:
                target_train_card = card

        # If no specific train matched, find the first train card with the requested class
        if not target_train_card:
            all_cards = page.locator("app-train-list, div.form-group:has(.train-heading)")
            card_count = await all_cards.count()
            for i in range(min(card_count, 12)):
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
                        log_event(db, "INFO", "AUTOMATION", f"Auto-selected train: {booking.train_number} - {booking.train_name}", ref)
                    except Exception:
                        pass
                    break

        # Fallback to first train card on page
        if not target_train_card:
            first_c = page.locator("app-train-list, div.form-group:has(.train-heading)").first
            if await first_c.count() > 0:
                target_train_card = first_c

        # Step 5b: Click the requested class tab on the chosen train
        if target_train_card:
            try:
                cls_btn = target_train_card.locator(f"div:has-text('{journey_cls}'), span:has-text('{journey_cls}'), .pre-avl:has-text('{journey_cls}')").first
                if await cls_btn.count() > 0:
                    await cls_btn.click(timeout=3000, force=True)
                    await asyncio.sleep(2)
            except Exception as e:
                log_event(db, "WARNING", "AUTOMATION", f"Class click note: {e}", ref)

        # Step 5c: Extract live fare if visible
        live_fare = await extract_live_fare_from_page(page)
        if live_fare:
            booking.fare = live_fare
            db.commit()
            log_event(db, "INFO", "AUTOMATION", f"Official IRCTC Fare: ₹{live_fare:,.2f}", ref)

        # Step 5d: Click 'Book Now' automatically
        try:
            book_now = page.locator("button:has-text('Book Now'), button.btn-primary:has-text('Book Now')").first
            if await book_now.count() > 0 and await book_now.is_visible():
                await book_now.click(timeout=3000, force=True)
                await asyncio.sleep(2.5)
                await dismiss_overlays(page)
        except Exception as e:
            log_event(db, "WARNING", "AUTOMATION", f"Book now click note: {e}", ref)

        # Step 5e: If passenger input is not visible yet, pause with screenshot and action buttons
        if not await page.locator(NAVIGATION_SELECTORS["PASSENGER_NAME"]).count() > 0:
            train_bytes = None
            try:
                train_bytes = await page.screenshot()
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

            # Bring browser window to front
            try:
                await page.bring_to_front()
                focus_browser_window()
            except Exception:
                pass

            if settings.TELEGRAM_ENABLED:
                t_keyboard = {
                    "inline_keyboard": [
                        [
                            {"text": "✅ Maine 'Book Now' Click Kar Diya (Continue)", "callback_data": "action_continue"},
                            {"text": "❌ Cancel", "callback_data": "action_cancel"}
                        ]
                    ]
                }
                caption = (
                    f"🚆 *IRCTC Train & Class Selection* (Ref: `{ref}`)\n\n"
                    f"Route: `{booking.from_station}` ➔ `{booking.to_station}` ({booking.journey_class})\n"
                    f"Kripya browser me apni manpasand train par *'Book Now'* click karein aur phir neeche button dabayein:"
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

        # Step 6: Passenger Form Filling
        session_state.set_stage("FILLING_PASSENGERS")
        passengers = db.query(BookingPassenger).filter(BookingPassenger.booking_id == booking.id).all()
        log_event(db, "INFO", "AUTOMATION", f"Entering details for {len(passengers)} passenger(s)...", ref)

        try:
            for idx, p in enumerate(passengers):
                if idx > 0:
                    add_btn = page.locator(NAVIGATION_SELECTORS["ADD_PASSENGER_BTN"]).first
                    if await add_btn.count() > 0:
                        await add_btn.click(timeout=3000, force=True)
                        await asyncio.sleep(0.5)

                name_inputs = page.locator(NAVIGATION_SELECTORS["PASSENGER_NAME"])
                if await name_inputs.count() > idx:
                    await name_inputs.nth(idx).fill(p.name)

                age_inputs = page.locator(NAVIGATION_SELECTORS["PASSENGER_AGE"])
                if await age_inputs.count() > idx:
                    await age_inputs.nth(idx).fill(str(p.age))
        except Exception as e:
            log_event(db, "WARNING", "AUTOMATION", f"Auto-fill note: {str(e)}", ref)

        # Contact mobile
        if booking.contact_mobile:
            try:
                mob_input = page.locator(NAVIGATION_SELECTORS["CONTACT_MOBILE"]).first
                if await mob_input.count() > 0:
                    await mob_input.fill(booking.contact_mobile)
            except Exception:
                pass

        # Extract live fare from Passenger details summary
        live_fare = await extract_live_fare_from_page(page)
        if live_fare:
            booking.fare = live_fare
            db.commit()
            log_event(db, "INFO", "AUTOMATION", f"Extracted IRCTC Passenger Fare: ₹{live_fare:,.2f}", ref)

        # Click Continue to Review / Payment
        try:
            cont_btn = page.locator("button:has-text('Continue'), button[type='submit']:has-text('Continue')").first
            if await cont_btn.count() > 0:
                await cont_btn.click(timeout=3000, force=True)
                await asyncio.sleep(2)
        except Exception:
            pass

        # Step 7: Security challenge check (CAPTCHA / OTP before payment)
        await asyncio.sleep(2)

        # Extract live total fare including convenience fee and taxes from Review page
        live_fare = await extract_live_fare_from_page(page)
        if live_fare:
            booking.fare = live_fare
            db.commit()
            log_event(db, "INFO", "AUTOMATION", f"Confirmed Official IRCTC Total Fare (including taxes & fees): ₹{live_fare:,.2f}", ref)

        captcha_img_loc = page.locator("img.captcha-img, app-captcha img, #captchaImg, img[alt*='captcha' i]").first
        captcha_input = page.locator("input[placeholder*='captcha' i], #nlpAnswer, #captcha").first
        is_payment_page = (await page.locator("app-payment, div:has-text('Payment Option'), div:has-text('Payment Method'), #bank-type").count() > 0)

        has_captcha = False
        if not is_payment_page:
            try:
                await captcha_img_loc.wait_for(state="visible", timeout=3000)
            except Exception:
                pass
            has_captcha = (await captcha_img_loc.count() > 0) or (await captcha_input.count() > 0)

        if has_captcha:
            captcha_bytes = None
            try:
                if await captcha_img_loc.count() > 0 and await captcha_img_loc.is_visible():
                    captcha_bytes = await captcha_img_loc.screenshot(timeout=3000)
                else:
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

            # Bring browser window to front
            try:
                await page.bring_to_front()
                focus_browser_window()
            except Exception:
                pass

            if settings.TELEGRAM_ENABLED:
                try:
                    if captcha_bytes:
                        await send_telegram_photo(
                            photo_bytes=captcha_bytes,
                            caption=(
                                f"📸 *IRCTC Review CAPTCHA* (Ref: `{ref}`)\n\n"
                                f"Kripya ye photo dekh kar CAPTCHA text reply karein. Hum automatically ise browser me fill kar denge!"
                            )
                        )
                    else:
                        await send_telegram_message(format_action_required_telegram(booking, "IRCTC Review CAPTCHA"))
                except Exception as e:
                    log_event(db, "WARNING", "AUTOMATION", f"Could not capture CAPTCHA screenshot for Telegram: {e}", ref)

            # Wait for user input from Telegram text reply or Web dashboard
            done, pending = await asyncio.wait(
                [
                    asyncio.create_task(session_state.continue_event.wait()),
                    asyncio.create_task(session_state.input_event.wait())
                ],
                return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()

            if session_state.cancel_event.is_set():
                booking.status = "CANCELLED"
                db.commit()
                return

            # If user supplied CAPTCHA via Telegram, type it into the form
            if session_state.user_input_value:
                try:
                    if await captcha_input.count() > 0:
                        await captcha_input.fill(session_state.user_input_value.strip())
                        log_event(db, "INFO", "AUTOMATION", "Auto-filled CAPTCHA received from Telegram.", ref)
                        submit_btn = page.locator("button:has-text('Continue'), button[type='submit']").first
                        if await submit_btn.count() > 0:
                            await submit_btn.click(timeout=3000, force=True)
                            await asyncio.sleep(2)
                except Exception as e:
                    log_event(db, "WARNING", "AUTOMATION", f"Could not auto-fill CAPTCHA into page: {e}", ref)
        else:
            log_event(db, "INFO", "AUTOMATION", "Review CAPTCHA bypassed or not required by login session. Proceeding directly to Payment Gateway.", ref)
            try:
                cont_btn = page.locator("button:has-text('Continue'), button[type='submit']:has-text('Continue')").first
                if await cont_btn.count() > 0:
                    await cont_btn.click(timeout=3000, force=True)
                    await asyncio.sleep(2)
            except Exception:
                pass

        # Step 8: Payment Gateway Handoff (MANDATORY HUMAN-IN-THE-LOOP)
        session_state.set_stage("PAYMENT_PENDING")

        # Attempt to auto-select UPI / BHIM QR option if visible
        try:
            upi_selectors = [
                "div:has-text('BHIM / UPI / USSD')",
                "span:has-text('BHIM / UPI')",
                "div:has-text('BHIM / UPI')",
                "span:has-text('iPay')",
                "div:has-text('IRCTC iPay')",
                "input[value*='UPI' i]",
                "p-radiobutton[name='paymentProvider']"
            ]
            for sel in upi_selectors:
                loc = page.locator(sel).first
                if await loc.count() > 0 and await loc.is_visible():
                    await loc.click(timeout=2000, force=True)
                    await asyncio.sleep(1)
                    break

            pay_btn = page.locator("button:has-text('Pay & Book'), button:has-text('Continue'), button.btn-primary:has-text('Pay')").first
            if await pay_btn.count() > 0 and await pay_btn.is_visible():
                await pay_btn.click(timeout=3000, force=True)
                await asyncio.sleep(3)
        except Exception:
            pass

        # Extract final payable amount from payment page
        final_fare = await extract_live_fare_from_page(page)
        if final_fare:
            booking.fare = final_fare
            db.commit()
            log_event(db, "INFO", "AUTOMATION", f"Final IRCTC Payable Amount: ₹{final_fare:,.2f}", ref)

        fare_display = f"₹{booking.fare:,.2f} (Rs. {booking.fare:,.2f})" if booking.fare else "As per IRCTC Portal"

        pay_prompt = f"PAYMENT REQUIRED: Official IRCTC Total Amount: {fare_display}. Please scan UPI QR code or complete payment."
        session_state.pause_for_user(pay_prompt, is_payment=True, input_type="PAYMENT")
        booking.status = "PAYMENT_PENDING"
        db.commit()
        log_event(db, "WARNING", "AUTOMATION", pay_prompt, ref)

        # Bring browser window to front
        try:
            await page.bring_to_front()
            focus_browser_window()
        except Exception:
            pass

        qr_bytes = None
        try:
            qr_locators = [
                "app-bhim-upi-qr img",
                "#qr-image",
                "#qrCode",
                "img.qr-code",
                "div.qr-image img",
                "img[src*='data:image']",
                "img[alt*='qr' i]"
            ]
            qr_elem = None
            for q_sel in qr_locators:
                loc = page.locator(q_sel).first
                if await loc.count() > 0 and await loc.is_visible():
                    qr_elem = loc
                    break

            qr_bytes = await qr_elem.screenshot(timeout=3000) if qr_elem else await page.screenshot()
            if qr_bytes:
                session_state.latest_screenshot_bytes = qr_bytes
                (DATA_DIR / "latest_captcha.png").write_bytes(qr_bytes)
        except Exception:
            pass

        if settings.TELEGRAM_ENABLED:
            try:
                qr_keyboard = {
                    "inline_keyboard": [
                        [
                            {"text": "✅ Payment Ho Gayi (Continue)", "callback_data": "action_continue"},
                            {"text": "❌ Cancel", "callback_data": "action_cancel"}
                        ]
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
                log_event(db, "WARNING", "AUTOMATION", f"Could not capture payment screenshot: {e}", ref)

        await session_state.continue_event.wait()
        if session_state.cancel_event.is_set():
            booking.status = "CANCELLED"
            db.commit()
            return

        # Step 9: Confirmation Detection & Data Extraction
        session_state.set_stage("CONFIRMATION_DETECTED")
        log_event(db, "INFO", "AUTOMATION", "Detecting confirmation details from official IRCTC page...", ref)
        await asyncio.sleep(2)

        # Scan for PNR in the current DOM
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
