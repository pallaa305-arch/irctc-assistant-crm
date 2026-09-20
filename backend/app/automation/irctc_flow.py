import asyncio
import re
from datetime import datetime
from sqlalchemy.orm import Session
from app.automation.browser_manager import browser_manager
from app.automation.flow_state import BookingSessionState
from app.automation.selectors import URLS, CHALLENGE_SELECTORS, NAVIGATION_SELECTORS
from app.database.models import Booking, BookingPassenger
from app.crm.crm_service import log_event, finalize_successful_booking
from app.notifications.telegram import send_telegram_message, format_action_required_telegram
from app.config import settings

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

        # Check for initial disclaimers / alerts and dismiss if present
        try:
            ok_btn = page.locator("button:has-text('OK'), button:has-text('DISMISS')")
            if await ok_btn.count() > 0:
                await ok_btn.first.click()
        except Exception:
            pass

        # Step 3: Check if user needs to log in
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
            if await login_btn.count() > 0:
                log_event(db, "INFO", "AUTOMATION", "Opening IRCTC login dialog...", ref)
                try:
                    await login_btn.first.click()
                    await asyncio.sleep(1.5)
                except Exception:
                    pass

                # Auto-fill credentials from settings/.env if configured
                credentials_auto_filled = False
                if settings.IRCTC_USERNAME:
                    try:
                        u_input = page.locator("input[placeholder*='User Name' i], #userId, input[formcontrolname='userid'], input[name='userId']").first
                        if await u_input.count() > 0:
                            await u_input.fill(settings.IRCTC_USERNAME)
                            credentials_auto_filled = True
                    except Exception as e:
                        log_event(db, "WARNING", "AUTOMATION", f"Could not auto-fill username: {e}", ref)

                if settings.IRCTC_PASSWORD:
                    try:
                        p_input = page.locator("input[placeholder*='Password' i], #pwd, input[formcontrolname='password'], input[name='pwd']").first
                        if await p_input.count() > 0:
                            await p_input.fill(settings.IRCTC_PASSWORD)
                    except Exception as e:
                        log_event(db, "WARNING", "AUTOMATION", f"Could not auto-fill password: {e}", ref)

                # Auto-tick the Login checkbox (Booking with OTP / Remember / Auto login)
                try:
                    otp_checkbox = page.locator("input[type='checkbox'], #otpLogin, p-checkbox, label:has-text('OTP'), label:has-text('Booking with OTP')").first
                    if await otp_checkbox.count() > 0:
                        is_checked = False
                        try:
                            is_checked = await otp_checkbox.is_checked()
                        except Exception:
                            pass
                        if not is_checked:
                            await otp_checkbox.click()
                            log_event(db, "INFO", "AUTOMATION", "Auto-ticked 'Login with OTP / Remember' checkbox on IRCTC.", ref)
                except Exception as e:
                    log_event(db, "WARNING", "AUTOMATION", f"Checkbox auto-tick note: {e}", ref)

                if credentials_auto_filled:
                    log_event(db, "INFO", "AUTOMATION", f"Saved credentials for '{settings.IRCTC_USERNAME}' auto-filled with checkbox active.", ref)

                session_state.set_stage("WAITING_MANUAL")
                login_prompt = "IRCTC Login: Credentials auto-filled with OTP checkbox ticked. Please confirm/solve login in browser if needed."
                session_state.pause_for_user(login_prompt, is_payment=False)
                booking.status = "WAITING_MANUAL"
                db.commit()
                log_event(db, "WARNING", "AUTOMATION", login_prompt, ref)

                if settings.TELEGRAM_ENABLED:
                    await send_telegram_message(format_action_required_telegram(booking, "IRCTC Login Check"))

                await session_state.continue_event.wait()
                if session_state.cancel_event.is_set():
                    booking.status = "CANCELLED"
                    db.commit()
                    log_event(db, "INFO", "AUTOMATION", "Booking cancelled during login.", ref)
                    return

        # Step 4: Search Trains
        session_state.set_stage("SEARCHING_TRAINS")
        log_event(db, "INFO", "AUTOMATION", f"Entering route: {booking.from_station} ➔ {booking.to_station}", ref)

        try:
            # Enter From station
            from_input = page.locator(NAVIGATION_SELECTORS["FROM_STATION"]).first
            if await from_input.count() > 0:
                await from_input.click()
                await from_input.fill(booking.from_station)
                await asyncio.sleep(1)
                # Select first matching dropdown item
                await page.keyboard.press("ArrowDown")
                await page.keyboard.press("Enter")

            # Enter To station
            to_input = page.locator(NAVIGATION_SELECTORS["TO_STATION"]).first
            if await to_input.count() > 0:
                await to_input.click()
                await to_input.fill(booking.to_station)
                await asyncio.sleep(1)
                await page.keyboard.press("ArrowDown")
                await page.keyboard.press("Enter")

            # Enter Date
            date_str = booking.journey_date.strftime("%d/%m/%Y")
            date_input = page.locator(NAVIGATION_SELECTORS["JOURNEY_DATE"]).first
            if await date_input.count() > 0:
                await date_input.click()
                await page.keyboard.press("Control+A")
                await page.keyboard.press("Backspace")
                await date_input.fill(date_str)
                await page.keyboard.press("Enter")

            # Click Search
            search_btn = page.locator(NAVIGATION_SELECTORS["SEARCH_BUTTON"]).first
            if await search_btn.count() > 0:
                await search_btn.click()
                await asyncio.sleep(3)
        except Exception as e:
            log_event(db, "WARNING", "AUTOMATION", f"Search form note: {str(e)}. Please confirm search in browser.", ref)

        # Step 5: Train & Class Selection
        session_state.set_stage("SELECTING_TRAIN")
        select_prompt = f"Train Selection: Please verify or click 'Book Now' for train {booking.train_number or ''} ({booking.journey_class}) in the browser."
        session_state.pause_for_user(select_prompt, is_payment=False)
        booking.status = "WAITING_MANUAL"
        db.commit()
        log_event(db, "INFO", "AUTOMATION", select_prompt, ref)

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
                        await add_btn.click()
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

        # Step 7: Security challenge check (CAPTCHA / OTP before payment)
        await asyncio.sleep(2)
        captcha_img_loc = page.locator("img.captcha-img, app-captcha img, #captchaImg, img[alt*='captcha' i]").first
        captcha_input = page.locator("input[placeholder*='captcha' i], #nlpAnswer, #captcha").first
        is_payment_page = (await page.locator("app-payment, div:has-text('Payment Option'), div:has-text('Payment Method'), #bank-type").count() > 0)

        has_captcha = False
        if not is_payment_page:
            has_captcha = (await captcha_img_loc.count() > 0) or (await captcha_input.count() > 0)

        if has_captcha:
            session_state.set_stage("WAITING_MANUAL")
            review_prompt = "Review & CAPTCHA: Please review details and enter the visual CAPTCHA in the browser window, or reply with text in Telegram."
            session_state.pause_for_user(review_prompt, is_payment=False, input_type="CAPTCHA")
            booking.status = "WAITING_MANUAL"
            db.commit()
            log_event(db, "WARNING", "AUTOMATION", review_prompt, ref)

            from app.notifications.telegram import send_telegram_photo

            if settings.TELEGRAM_ENABLED:
                try:
                    captcha_bytes = None
                    if await captcha_img_loc.count() > 0:
                        captcha_bytes = await captcha_img_loc.screenshot()
                    else:
                        captcha_bytes = await page.screenshot()

                    if captcha_bytes:
                        await send_telegram_photo(
                            photo_bytes=captcha_bytes,
                            caption=(
                                f"📸 *IRCTC CAPTCHA Check* (Ref: `{ref}`)\n\n"
                                f"Kripya ye photo dekh kar CAPTCHA text ka reply karein. Hum automatically ise browser me fill kar denge!"
                            )
                        )
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
                        await captcha_input.fill(session_state.user_input_value)
                        log_event(db, "INFO", "AUTOMATION", f"Auto-filled CAPTCHA received from Telegram.", ref)
                        submit_btn = page.locator("button:has-text('Continue'), button[type='submit']").first
                        if await submit_btn.count() > 0:
                            await submit_btn.click()
                except Exception as e:
                    log_event(db, "WARNING", "AUTOMATION", f"Could not auto-fill CAPTCHA into page: {e}", ref)
        else:
            log_event(db, "INFO", "AUTOMATION", "Review CAPTCHA bypassed or not required by login session. Proceeding directly to Payment Gateway.", ref)
            try:
                cont_btn = page.locator("button:has-text('Continue'), button[type='submit']:has-text('Continue')").first
                if await cont_btn.count() > 0:
                    await cont_btn.click()
                    await asyncio.sleep(2)
            except Exception:
                pass

        # Step 8: Payment Gateway Handoff (MANDATORY HUMAN-IN-THE-LOOP)
        session_state.set_stage("PAYMENT_PENDING")
        pay_prompt = "PAYMENT REQUIRED: Please scan UPI QR code or pay via NetBanking/Cards. After successful payment, click 'Payment Done'."
        session_state.pause_for_user(pay_prompt, is_payment=True, input_type="PAYMENT")
        booking.status = "PAYMENT_PENDING"
        db.commit()
        log_event(db, "WARNING", "AUTOMATION", pay_prompt, ref)

        # Attempt to auto-select UPI / BHIM QR option if visible
        try:
            upi_selector = page.locator("div:has-text('BHIM / UPI'), span:has-text('BHIM / UPI'), span:has-text('iPay'), input[value*='UPI' i]").first
            if await upi_selector.count() > 0:
                await upi_selector.click()
                await asyncio.sleep(1)
        except Exception:
            pass

        if settings.TELEGRAM_ENABLED:
            try:
                # Capture QR element or full screen
                qr_elem = page.locator("app-bhim-upi-qr img, #qr-code, img[alt*='qr' i], div.qr-image").first
                qr_bytes = await qr_elem.screenshot() if await qr_elem.count() > 0 else await page.screenshot()
                qr_keyboard = {
                    "inline_keyboard": [
                        [
                            {"text": "✅ Payment Ho Gayi (Continue)", "callback_data": "action_continue"},
                            {"text": "❌ Cancel", "callback_data": "action_cancel"}
                        ]
                    ]
                }
                await send_telegram_photo(
                    photo_bytes=qr_bytes,
                    caption=(
                        f"💳 *IRCTC Payment Step* (Ref: `{ref}`)\n\n"
                        f"Kripya payment complete karein aur phir neeche *'✅ Payment Ho Gayi'* button par tap karein."
                    ),
                    reply_markup=qr_keyboard
                )
            except Exception as e:
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
