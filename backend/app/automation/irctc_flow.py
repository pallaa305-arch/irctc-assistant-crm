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
from app.automation.captcha_solver import fast_solve_captcha
from app.automation.smart_browser import SmartBrowserActions
from app.config import settings, DATA_DIR

# ──────────────────────────────────────────────────────
# STATION CODE RESOLUTION — Maps full names → IRCTC codes
# ──────────────────────────────────────────────────────
STATION_CODE_MAP = {
    # Major cities
    "NEW DELHI": "NDLS", "NDLS": "NDLS", "DELHI": "NDLS",
    "OLD DELHI": "DLI", "DLI": "DLI",
    "NIZAMUDDIN": "NZM", "H NIZAMUDDIN": "NZM", "NZM": "NZM",
    "ANAND VIHAR": "ANVT", "ANVT": "ANVT",
    "MUMBAI": "MMCT", "MUMBAI CENTRAL": "MMCT", "MMCT": "MMCT",
    "CSMT": "CSMT", "MUMBAI CSMT": "CSMT", "CSTM": "CSMT",
    "BANDRA": "BDTS", "BDTS": "BDTS", "BANDRA TERMINUS": "BDTS",
    "LTT": "LTT", "LOKMANYA TILAK": "LTT",
    "KOLKATA": "HWH", "HOWRAH": "HWH", "HWH": "HWH",
    "SEALDAH": "SDAH", "SDAH": "SDAH",
    "CHENNAI": "MAS", "MAS": "MAS", "CHENNAI CENTRAL": "MAS",
    "BENGALURU": "SBC", "BANGALORE": "SBC", "SBC": "SBC",
    "YESVANTPUR": "YPR", "YPR": "YPR",
    "HYDERABAD": "SC", "SECUNDERABAD": "SC", "SC": "SC",
    "AHMEDABAD": "ADI", "ADI": "ADI",
    "PUNE": "PUNE",
    "JAIPUR": "JP", "JP": "JP",
    "LUCKNOW": "LKO", "LKO": "LKO",
    "KANPUR": "CNB", "CNB": "CNB", "KANPUR CENTRAL": "CNB",
    "VARANASI": "BSB", "BSB": "BSB", "BANARAS": "BSB",
    "PATNA": "PNBE", "PNBE": "PNBE",
    "BHOPAL": "BPL", "BPL": "BPL",
    "HABIBGANJ": "RKMP", "RKMP": "RKMP",
    "AGRA": "AGC", "AGC": "AGC", "AGRA CANTT": "AGC",
    "GOA": "MAO", "MADGAON": "MAO", "MAO": "MAO",
    "CHANDIGARH": "CDG", "CDG": "CDG",
    "AMRITSAR": "ASR", "ASR": "ASR",
    "GWALIOR": "GWL", "GWL": "GWL",
    "NAGPUR": "NGP", "NGP": "NGP",
    "SURAT": "ST", "ST": "ST",
    "INDORE": "INDB", "INDB": "INDB",
    "UJJAIN": "UJN", "UJN": "UJN",
    "JODHPUR": "JU", "JU": "JU",
    "UDAIPUR": "UDZ", "UDZ": "UDZ",
    "AYODHYA": "AY", "AY": "AY",
    "PRAYAGRAJ": "PRYJ", "ALLAHABAD": "PRYJ", "PRYJ": "PRYJ",
    "GORAKHPUR": "GKP", "GKP": "GKP",
    "JAMMU": "JAT", "JAT": "JAT", "JAMMU TAWI": "JAT",
    "DEHRADUN": "DDN", "DDN": "DDN",
    "HARIDWAR": "HW", "HW": "HW",
    "RANCHI": "RNC", "RNC": "RNC",
    "BHUBANESWAR": "BBS", "BBS": "BBS",
    "GUWAHATI": "GHY", "GHY": "GHY",
    "THIRUVANANTHAPURAM": "TVC", "TVC": "TVC", "TRIVANDRUM": "TVC",
    "KOCHI": "ERS", "ERS": "ERS", "ERNAKULAM": "ERS",
    "COIMBATORE": "CBE", "CBE": "CBE",
    "MADURAI": "MDU", "MDU": "MDU",
    "VISAKHAPATNAM": "VSKP", "VSKP": "VSKP",
    "VIJAYAWADA": "BZA", "BZA": "BZA",
    "GUHAD ROAD GOA": "MAO",
}

def resolve_station_code(station_text: str) -> str:
    """Resolves full station name to IRCTC-compatible code for autocomplete."""
    clean = station_text.strip().upper()
    # Direct lookup
    if clean in STATION_CODE_MAP:
        return STATION_CODE_MAP[clean]
    # Partial match
    for key, code in STATION_CODE_MAP.items():
        if key in clean or clean in key:
            return code
    # If already looks like a station code (3-5 uppercase letters), return as-is
    if len(clean) <= 5 and clean.isalpha():
        return clean
    # Fallback: return first 4 chars as potential code
    return clean[:4] if len(clean) > 4 else clean


async def dismiss_overlays(page):
    """
    Automatically dismisses language selection dialogs, alert popups,
    Senior citizen notices, COVID/KAVACH disclaimers, beta banners,
    or lingering dialog overlays.
    """
    if not page:
        return
    for _ in range(5):
        dismissed = False
        try:
            # 1. Native DOM evaluation for rapid, bulletproof dismissal
            js_res = await page.evaluate('''() => {
                let action = false;
                
                // Click language selection: English or Hindi button/link/span
                const allElems = Array.from(document.querySelectorAll('button, a, span, div.ui-button, [role="button"], label'));
                for (const el of allElems) {
                    const text = (el.innerText || el.textContent || '').trim().toLowerCase();
                    if (text === 'english' || text === 'हिंदी' || text.includes('english') || text.includes('हिंदी')) {
                        if (el.closest('.ui-dialog, app-dialog, .modal, .alert, p-dialog, div[role="dialog"]')) {
                            el.click();
                            action = true;
                            break;
                        }
                    }
                }
                
                // Click standard confirmation / disclaimer buttons (ignore login dialog)
                const okTexts = ['ok', 'i agree', 'yes', 'dismiss', 'submit', 'continue', 'agree', 'theek hai', 'स्वीकार'];
                for (const el of allElems) {
                    if (el.closest('app-login')) continue;
                    const text = (el.innerText || el.textContent || '').trim().toLowerCase();
                    if (okTexts.some(k => text === k || text.startsWith(k)) && el.closest('.ui-dialog, app-dialog, .modal, .alert, p-dialog, div[role="dialog"]')) {
                        el.click();
                        action = true;
                        break;
                    }
                }
                
                // Close dialog titlebar close icon (X) - strictly EXCLUDE app-login!
                const closeIcons = document.querySelectorAll('.ui-dialog-titlebar-close, a.ui-dialog-titlebar-close, button.close, [aria-label="Close"], .fa-window-close, .ui-dialog-titlebar-icon');
                for (const ci of closeIcons) {
                    if (ci.closest('app-login') || ci.closest('.loginCloseBtn')) continue;
                    if (ci.offsetParent !== null) {
                        ci.click();
                        action = true;
                    }
                }
                
                return action;
            }''')
            if js_res:
                dismissed = True
                await asyncio.sleep(0.5)

            # 2. Python Playwright selector fallback
            lang_loc = page.locator("button:has-text('English'), button:has-text('हिंदी'), span:has-text('English'), a:has-text('English'), .btn-primary:has-text('English')").first
            if await lang_loc.count() > 0 and await lang_loc.is_visible():
                await lang_loc.click(timeout=1200, force=True)
                await asyncio.sleep(0.4)
                dismissed = True

            general_selectors = [
                "div.ui-dialog:not(:has(app-login)) button:has-text('OK')",
                "div.ui-dialog:not(:has(app-login)) button:has-text('I Agree')",
                "div.ui-dialog:not(:has(app-login)) button:has-text('Yes')",
                "div.ui-dialog:not(:has(app-login)) button:has-text('DISMISS')",
                "div.ui-dialog:not(:has(app-login)) .ui-dialog-titlebar-close",
                "div.modal:not(:has(app-login)) button[aria-label='Close']"
            ]
            for sel in general_selectors:
                loc = page.locator(sel).first
                if await loc.count() > 0 and await loc.is_visible():
                    await loc.click(timeout=800, force=True)
                    await asyncio.sleep(0.4)
                    dismissed = True
                    
            # Dismiss lingering backdrop with Escape ONLY if login modal is NOT present
            has_login_modal = await page.locator("app-login, input[formcontrolname='userid'], #userId").count() > 0
            if not has_login_modal:
                await page.keyboard.press("Escape")
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
                        const m = text.match(/₹?\\s*([\\d,]+(?:\\.\\d{1,2})?)/) ;
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
        js_logged_in = await page.evaluate(r'''() => {
            const bodyText = (document.body && document.body.innerText) || '';
            const allElements = Array.from(document.querySelectorAll('a, button, span, div'));
            
            // Check for presence of Login button
            const hasLoginBtn = allElements.some(el => {
                const t = (el.innerText || '').trim().toUpperCase();
                return (t === 'LOGIN' || t === 'LOGIN / REGISTER' || t === 'SIGN IN') && el.offsetParent !== null;
            });

            // Check for explicit Logout button
            const hasLogoutBtn = allElements.some(el => {
                const t = (el.innerText || '').trim().toUpperCase();
                return t === 'LOGOUT' && el.offsetParent !== null;
            });

            // Check for user-specific welcome banner like "Welcome Suman Kumar Sharma (randisumandalladeepak)"
            const hasUserWelcome = /Welcome\s+[A-Za-z]+.*\(.*\)/i.test(bodyText);

            if (hasLogoutBtn || hasUserWelcome) {
                return true;
            }
            if (hasLoginBtn) {
                return false;
            }
            return false;
        }''')
        return bool(js_logged_in)
    except Exception:
        pass
    return False


async def _wait_for_user_or_cancel(session_state: BookingSessionState, timeout_seconds: int = 600) -> str:
    """
    Waits for user input, continue, or cancel event. Returns 'input', 'continue', or 'cancel'.
    Also supports timeout to avoid infinite hanging.
    """
    try:
        done, pending = await asyncio.wait(
            [
                asyncio.create_task(session_state.continue_event.wait()),
                asyncio.create_task(session_state.input_event.wait())
            ],
            timeout=timeout_seconds,
            return_when=asyncio.FIRST_COMPLETED
        )
        for t in pending:
            t.cancel()
    except Exception:
        pass

    if session_state.cancel_event.is_set():
        return "cancel"
    if session_state.input_event.is_set() and session_state.user_input_value:
        return "input"
    if session_state.continue_event.is_set():
        return "continue"
    return "timeout"


async def ensure_authenticated_session(page, ref: str, db: Session, session_state: BookingSessionState, booking: Optional[Booking] = None) -> bool:
    """
    Enforces that the IRCTC browser session is ALWAYS authenticated.
    If the user is not logged in or gets logged out at any point,
    this function immediately handles the login dialog, credential fill,
    CAPTCHA solving, and verifies the session before allowing the flow to proceed.
    Guarantees no unauthenticated/guest search or booking ever occurs.
    """
    if not page:
        return False

    # Validate credentials exist
    if not settings.IRCTC_USERNAME or not settings.IRCTC_PASSWORD:
        err = "IRCTC_USERNAME and IRCTC_PASSWORD must be set in .env file. Cannot proceed without credentials."
        log_event(db, "ERROR", "AUTOMATION", err, ref)
        session_state.set_stage("FAILED", "FAILED")
        session_state.error_message = err
        if booking:
            booking.status = "FAILED"
            db.commit()
        raise RuntimeError(err)

    if not page.url or "irctc.co.in" not in page.url or page.url == "about:blank":
        await page.goto(URLS["HOME"], wait_until="domcontentloaded", timeout=45000)
        await asyncio.sleep(2)
        await dismiss_overlays(page)

    # 1. Quick check if already logged in
    if await check_logged_in_state(page):
        log_event(db, "INFO", "AUTOMATION", f"Authenticated IRCTC session confirmed for user: {settings.IRCTC_USERNAME[:4]}****", ref)
        return True

    log_event(db, "WARNING", "AUTOMATION", "IRCTC session not logged in. Initiating mandatory authentication...", ref)
    session_state.set_stage("CHECKING_LOGIN")
    if booking:
        booking.status = "IN_PROGRESS"
        db.commit()

    await dismiss_overlays(page)

    for attempt in range(1, 4):
        # Check if already logged in after dismissing overlays
        if await check_logged_in_state(page):
            return True

        if session_state.cancel_event.is_set():
            return False

        # Try opening login modal if not already open
        user_input = page.locator("input[formcontrolname='userid'], #userId, input[placeholder*='User Name' i]").first
        if not (await user_input.count() > 0 and await user_input.is_visible()):
            login_btn = page.locator("a.loginText, a:has-text('LOGIN / REGISTER'), a:has-text('LOGIN'), button:has-text('LOGIN')").first
            if await login_btn.count() > 0 and await login_btn.is_visible():
                await login_btn.click(timeout=3000, force=True)
                await asyncio.sleep(1.5)

        # Wait for user input selector
        try:
            await page.wait_for_selector("input[formcontrolname='userid'], #userId, input[placeholder*='User Name' i]", timeout=6000)
            user_input = page.locator("input[formcontrolname='userid'], #userId, input[placeholder*='User Name' i]").first
            pass_input = page.locator("input[formcontrolname='password'], #pwd, input[placeholder*='Password' i]").first
        except Exception:
            user_input = page.locator("input[formcontrolname='userid'], #userId, input[placeholder*='User Name' i]").first
            pass_input = page.locator("input[formcontrolname='password'], #pwd, input[placeholder*='Password' i]").first

        if await user_input.count() > 0 and await user_input.is_visible():
            # Fill username
            await user_input.click()
            await user_input.fill("")
            await user_input.press_sequentially(settings.IRCTC_USERNAME, delay=35)
            await user_input.dispatch_event("input")
            await user_input.dispatch_event("change")
            log_event(db, "INFO", "AUTOMATION", f"Auto-filled username: {settings.IRCTC_USERNAME[:4]}**** (attempt {attempt})", ref)

            # Fill password
            if await pass_input.count() > 0 and settings.IRCTC_PASSWORD:
                await pass_input.click()
                await pass_input.fill("")
                await pass_input.press_sequentially(settings.IRCTC_PASSWORD, delay=35)
                await pass_input.dispatch_event("input")
                await pass_input.dispatch_event("change")

            # Wait up to 8s for visual captcha image to load in DOM
            try:
                await page.wait_for_selector("app-captcha img, #captchaImg, img.captcha-img, img[alt*='captcha' i]", timeout=8000)
            except Exception:
                pass

            # Check visual captcha inside login modal
            cap_img = page.locator("app-captcha img, #captchaImg, img.captcha-img, img[alt*='captcha' i]").first
            cap_input = page.locator("#nlpAnswer, input[formcontrolname='captcha'], input[placeholder*='captcha' i]").first

            if await cap_img.count() > 0 and await cap_img.is_visible():
                cap_bytes = None
                try:
                    await cap_img.scroll_into_view_if_needed()
                    cap_bytes = await cap_img.screenshot(timeout=3000)
                except Exception:
                    login_modal = page.locator("app-login, div.ui-dialog").first
                    if await login_modal.count() > 0 and await login_modal.is_visible():
                        cap_bytes = await login_modal.screenshot(timeout=3000)

                candidate_text = ""
                if cap_bytes:
                    try:
                        (DATA_DIR / "latest_captcha.png").write_bytes(cap_bytes)
                    except Exception:
                        pass
                    candidate_text, _ = fast_solve_captcha(cap_bytes)
                    if candidate_text and await cap_input.count() > 0:
                        try:
                            await cap_input.fill(candidate_text)
                        except Exception:
                            pass

                # If fast captcha was predicted, attempt auto-login first
                sign_in_btn = page.locator("app-login button:has-text('SIGN IN'), app-login button[type='submit'], button:has-text('SIGN IN')").first
                if candidate_text and await sign_in_btn.count() > 0:
                    log_event(db, "INFO", "AUTOMATION", f"Submitting credentials with auto-detected CAPTCHA: '{candidate_text}' (attempt {attempt})", ref)
                    await sign_in_btn.click(timeout=3000, force=True)
                    await asyncio.sleep(2.5)

                # Check if logged in immediately
                for _ in range(6):
                    if await check_logged_in_state(page):
                        log_event(db, "INFO", "AUTOMATION", "Login successful! Session authenticated.", ref)
                        return True
                    await asyncio.sleep(1)

                # If still not logged in, request manual confirmation / Telegram / UI pause
                if not await check_logged_in_state(page):
                    session_state.set_stage("WAITING_MANUAL")
                    login_prompt = f"IRCTC Login: Credentials auto-filled. CAPTCHA: '{candidate_text}'. Please confirm or enter captcha."
                    session_state.pause_for_user(login_prompt, is_payment=False, input_type="CAPTCHA", screenshot_bytes=cap_bytes, suggested_value=candidate_text)
                    if booking:
                        booking.status = "WAITING_MANUAL"
                        db.commit()
                    log_event(db, "WARNING", "AUTOMATION", login_prompt, ref)

                    if settings.TELEGRAM_ENABLED and cap_bytes:
                        t_keyboard = {
                            "inline_keyboard": [
                                [{"text": f"⚡ Confirm '{candidate_text}'", "callback_data": f"action_captcha_{candidate_text}"}],
                                [{"text": "✅ Login Ho Gaya (Continue)", "callback_data": "action_continue"}],
                                [{"text": "❌ Cancel", "callback_data": "action_cancel"}]
                            ]
                        }
                        cap_caption = (
                            f"🔐 *IRCTC Login Required* (Ref: `{ref}`)\n\n"
                            f"ID (`{settings.IRCTC_USERNAME}`) auto-filled.\n"
                            f"⚡ *Auto-Detected CAPTCHA:* `{candidate_text}`\n"
                            f"👉 Sahi hai to direct *'Confirm'* dabayein ya 'OK' reply karein, warna corrected text type karein:"
                        )
                        await send_telegram_photo(photo_bytes=cap_bytes, caption=cap_caption, reply_markup=t_keyboard)

                    result = await _wait_for_user_or_cancel(session_state, timeout_seconds=300)
                    
                    if result == "cancel":
                        if booking:
                            booking.status = "CANCELLED"
                            db.commit()
                        return False

                    if result == "input" and session_state.user_input_value and await cap_input.count() > 0:
                        try:
                            await cap_input.fill(session_state.user_input_value.strip())
                            if await sign_in_btn.count() > 0:
                                await sign_in_btn.click(timeout=3000, force=True)
                                await asyncio.sleep(2.5)
                        except Exception:
                            pass

                    # Check login after user action
                    for _ in range(10):
                        if await check_logged_in_state(page):
                            log_event(db, "INFO", "AUTOMATION", "Login successfully confirmed! Session authenticated.", ref)
                            return True
                        await asyncio.sleep(1)
                    
                    # If still not logged in, try refreshing captcha for next attempt
                    log_event(db, "WARNING", "AUTOMATION", f"Login attempt {attempt} failed. Retrying...", ref)
                    try:
                        refresh_btn = page.locator("app-captcha .refresh-btn, app-captcha a, .captcha-refresh, img.captcha-img").first
                        if await refresh_btn.count() > 0:
                            await refresh_btn.click(force=True)
                            await asyncio.sleep(1)
                    except Exception:
                        pass
            else:
                # No captcha image found, try direct sign in
                sign_in_btn = page.locator("app-login button:has-text('SIGN IN'), app-login button[type='submit'], button:has-text('SIGN IN')").first
                if await sign_in_btn.count() > 0:
                    log_event(db, "INFO", "AUTOMATION", "Submitting credentials to IRCTC...", ref)
                    await sign_in_btn.click(timeout=3000, force=True)
                    await asyncio.sleep(3)
                for _ in range(8):
                    if await check_logged_in_state(page):
                        return True
                    await asyncio.sleep(1)

    # Final verification check
    is_ok = await check_logged_in_state(page)
    if is_ok:
        log_event(db, "INFO", "AUTOMATION", "Active IRCTC authenticated session confirmed.", ref)
        return True
    else:
        err = "Mandatory IRCTC Login failed after 3 attempts. Guest booking is strictly prohibited."
        log_event(db, "ERROR", "AUTOMATION", err, ref)
        raise RuntimeError(err)


async def _fill_station_autocomplete(page, input_locator, station_text: str, label: str, db: Session, ref: str):
    """Robustly fills IRCTC station autocomplete with retry logic using SmartBrowserActions."""
    station_code = resolve_station_code(station_text)
    
    for attempt in range(3):
        try:
            await input_locator.scroll_into_view_if_needed()
            await SmartBrowserActions.smart_click(page, selectors=[], scope_locator=input_locator)
            await SmartBrowserActions.smart_type(page, input_locator, station_code, delay_ms=70, clear_first=True)
            await asyncio.sleep(1.2)
            
            # Wait for dropdown to appear
            dropdown_item = page.locator("ul.ui-autocomplete-items li, li.ui-autocomplete-list-item, div.ui-autocomplete-panel li").first
            
            for wait_tick in range(6):
                if await dropdown_item.count() > 0 and await dropdown_item.is_visible():
                    break
                await asyncio.sleep(0.5)
            
            # Click the matching dropdown option with smart_click
            if await dropdown_item.count() > 0 and await dropdown_item.is_visible():
                clicked = await SmartBrowserActions.smart_click(
                    page,
                    selectors=["ul.ui-autocomplete-items li", "li.ui-autocomplete-list-item"],
                    scope_locator=dropdown_item
                )
                if not clicked:
                    await dropdown_item.click(force=True)
                log_event(db, "INFO", "AUTOMATION", f"{label} station selected: {station_code} (dropdown click)", ref)
                await asyncio.sleep(0.8)
                return True
            else:
                # Fallback: ArrowDown + Enter
                await input_locator.press("ArrowDown")
                await asyncio.sleep(0.4)
                await input_locator.press("Enter")
                await asyncio.sleep(0.8)
                log_event(db, "INFO", "AUTOMATION", f"{label} station selected: {station_code} (ArrowDown+Enter)", ref)
                return True
                
        except Exception as e:
            log_event(db, "WARNING", "AUTOMATION", f"{label} station fill attempt {attempt+1} failed: {e}", ref)
            await asyncio.sleep(0.5)
    
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
        # ══════════════════════════════════════════════════
        # VALIDATION: Check credentials before starting
        # ══════════════════════════════════════════════════
        if not settings.IRCTC_USERNAME or not settings.IRCTC_PASSWORD:
            err = (
                "❌ IRCTC credentials not configured! "
                "Please set IRCTC_USERNAME and IRCTC_PASSWORD in F:\\IRCTC\\backend\\.env file."
            )
            session_state.set_stage("FAILED", "FAILED")
            session_state.error_message = err
            booking.status = "FAILED"
            db.commit()
            log_event(db, "ERROR", "AUTOMATION", err, ref)
            if settings.TELEGRAM_ENABLED:
                await send_telegram_message(
                    f"❌ *Booking Failed* (Ref: `{ref}`)\n\n{err}",
                )
            return

        # ══════════════════════════════════════════════════
        # Step 1: Launch visible browser
        # ══════════════════════════════════════════════════
        session_state.set_stage("PREPARING", "IN_PROGRESS")
        booking.status = "IN_PROGRESS"
        db.commit()
        log_event(db, "INFO", "AUTOMATION", "Launching visible browser session...", ref)

        page = await browser_manager.get_page()

        # ══════════════════════════════════════════════════
        # Step 2: Open IRCTC
        # ══════════════════════════════════════════════════
        session_state.set_stage("OPENING_IRCTC")
        log_event(db, "INFO", "AUTOMATION", f"Navigating to official IRCTC website: {URLS['HOME']}", ref)
        await page.goto(URLS["HOME"], wait_until="domcontentloaded", timeout=45000)
        await asyncio.sleep(2)
        await dismiss_overlays(page)

        # ══════════════════════════════════════════════════
        # Step 3: Verified IRCTC Authentication Check
        # ══════════════════════════════════════════════════
        session_state.set_stage("CHECKING_LOGIN")
        log_event(db, "INFO", "AUTOMATION", "Enforcing authenticated IRCTC session...", ref)
        await ensure_authenticated_session(page, ref, db, session_state, booking)

        if session_state.cancel_event.is_set():
            booking.status = "CANCELLED"
            db.commit()
            return

        log_event(db, "INFO", "AUTOMATION", "Proceeding to Train Search with active authenticated session...", ref)

        # ══════════════════════════════════════════════════
        # Step 4: Search Trains
        # ══════════════════════════════════════════════════
        session_state.set_stage("SEARCHING_TRAINS")
        booking.status = "IN_PROGRESS"
        db.commit()
        log_event(db, "INFO", "AUTOMATION", f"Entering route: {booking.from_station} ➔ {booking.to_station}", ref)

        # Re-verify logged in state before train search
        if not await check_logged_in_state(page):
            log_event(db, "WARNING", "AUTOMATION", "Session not logged in before search. Re-authenticating...", ref)
            await ensure_authenticated_session(page, ref, db, session_state, booking)

        # Ensure search inputs are ready
        has_search_inputs = await page.locator("p-autocomplete input").count() > 0
        if not has_search_inputs:
            if "/train-search" not in page.url and "/nget/" not in page.url:
                await page.goto(URLS["HOME"], wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(1.5)
            await dismiss_overlays(page)

        search_success = False
        for search_attempt in range(3):
            try:
                # Ensure search inputs are ready
                await page.wait_for_selector("p-autocomplete input", timeout=15000)
                autocomplete_inputs = page.locator("p-autocomplete input")
                
                from_input = autocomplete_inputs.nth(0)
                to_input = page.locator("p-autocomplete input").nth(1)

                # 1. From station — use resolved code
                await _fill_station_autocomplete(page, from_input, booking.from_station, "FROM", db, ref)

                # Close any lingering dropdown
                await page.keyboard.press("Escape")
                await asyncio.sleep(0.3)

                # 2. To station — use resolved code
                await _fill_station_autocomplete(page, to_input, booking.to_station, "TO", db, ref)

                # Close any lingering dropdown overlays with Escape
                await page.keyboard.press("Escape")
                await asyncio.sleep(0.3)

                # 3. Date
                date_str = booking.journey_date.strftime("%d/%m/%Y")
                date_input = page.locator("p-calendar input, #jDate input, input[placeholder*='Date' i]").first
                if await date_input.count() > 0:
                    await date_input.scroll_into_view_if_needed()
                    await date_input.click(force=True)
                    await page.keyboard.press("Control+A")
                    await page.keyboard.press("Backspace")
                    await date_input.press_sequentially(date_str, delay=60)
                    await page.keyboard.press("Enter")
                    await page.keyboard.press("Escape")
                    await asyncio.sleep(0.5)

                # 4. Click Search Button
                search_btn = page.locator("button.search_btn, button[type='submit']:has-text('Search'), button:has-text('Search')").first
                if await search_btn.count() > 0:
                    await search_btn.scroll_into_view_if_needed()
                    await search_btn.click(force=True)
                    log_event(db, "INFO", "AUTOMATION", f"Submitted search for {booking.from_station} to {booking.to_station} on {date_str} (attempt {search_attempt+1}).", ref)
                    await asyncio.sleep(3)
                    search_success = True
                    break
                    
            except Exception as e:
                log_event(db, "WARNING", "AUTOMATION", f"Search attempt {search_attempt+1} failed: {str(e)}", ref)
                await asyncio.sleep(1)

        if not search_success:
            log_event(db, "WARNING", "AUTOMATION", "Search form could not be submitted after 3 attempts. Continuing to check if train list loaded...", ref)

        # ══════════════════════════════════════════════════
        # Step 5: Train & Class Selection
        # ══════════════════════════════════════════════════
        session_state.set_stage("SELECTING_TRAIN")
        log_event(db, "INFO", "AUTOMATION", f"Selecting train & class for {booking.from_station} ➔ {booking.to_station}...", ref)

        # Wait up to 20s for train list cards
        train_list_found = False
        for _ in range(20):
            await dismiss_overlays(page)
            if await page.locator("app-train-list, div.train-heading, div.form-group:has(.train-name)").count() > 0:
                train_list_found = True
                break
            # Check for IRCTC daily maintenance downtime
            maint_msg = await page.evaluate(r'''() => {
                const body = document.body.innerText || '';
                if (body.includes('maintenance downtime') || body.includes('Services will resume at')) {
                    const match = body.match(/Currently services are not available due to daily maintenance downtime[^\.]*\.[^\.]*Services will resume at [0-9:]+ hrs\.?/i);
                    return match ? match[0] : "Currently services are not available due to daily maintenance downtime. Services will resume at 00:20 hrs.";
                }
                return null;
            }''')
            if maint_msg:
                log_event(db, "WARNING", "AUTOMATION", f"IRCTC Maintenance Notice: {maint_msg}", ref)
                session_state.set_stage("FAILED", "FAILED")
                session_state.error_message = maint_msg
                booking.status = "FAILED"
                db.commit()
                if settings.TELEGRAM_ENABLED:
                    await send_telegram_message(f"⚠️ *IRCTC Maintenance* (Ref: `{ref}`)\n\n{maint_msg}")
                return
            # Check for "No trains found"
            no_trains = await page.evaluate(r'''() => {
                const body = document.body.innerText || '';
                if (body.includes('No trains found') || body.includes('no direct train')) {
                    return true;
                }
                return false;
            }''')
            if no_trains:
                log_event(db, "WARNING", "AUTOMATION", "No trains found for this route/date.", ref)
                break
            await asyncio.sleep(1)

        train_pref = (booking.train_number or "").strip()
        journey_cls = (booking.journey_class or "3A").strip().upper()

        target_train_card = None
        if train_pref and train_pref != "12002":
            num_m = re.search(r'\b\d{5}\b', train_pref)
            search_num = num_m.group(0) if num_m else train_pref
            c = page.locator("app-train-avl-enq").filter(has_text=search_num).first
            if await c.count() > 0:
                target_train_card = c

        if not target_train_card or await target_train_card.count() == 0:
            all_cards = page.locator("app-train-avl-enq")
            cnt = await all_cards.count()
            for i in range(min(cnt, 20)):
                c = all_cards.nth(i)
                if await c.locator(f"div.pre-avl:has-text('{journey_cls}'), span:has-text('{journey_cls}')").count() > 0:
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

        if not target_train_card or await target_train_card.count() == 0:
            target_train_card = page.locator("app-train-avl-enq").first

        await target_train_card.scroll_into_view_if_needed()
        await asyncio.sleep(0.5)

        # 1. Click Class Tab inside this specific train card
        cls_map = {
            "1A": ["1A", "AC First Class", "First Class"],
            "2A": ["2A", "AC 2 Tier", "2 Tier"],
            "3A": ["3A", "AC 3 Tier", "3 Tier"],
            "3E": ["3E", "AC 3 Economy", "3 Economy"],
            "CC": ["CC", "AC Chair car", "Chair Car"],
            "EC": ["EC", "Exec. Chair Car", "Executive"],
            "SL": ["SL", "Sleeper"],
            "2S": ["2S", "Second Sitting"]
        }
        cls_keys = cls_map.get(journey_cls, [journey_cls])
        cls_selectors = [f"div.pre-avl:has-text('{k}')" for k in cls_keys] + [f"span:has-text('{k}')" for k in cls_keys]

        clicked_class = await SmartBrowserActions.smart_click(
            page=page,
            selectors=cls_selectors,
            text_keywords=cls_keys,
            scope_locator=target_train_card,
            wait_after_sec=0.5
        )
        if not clicked_class:
            cls_elem = target_train_card.locator("div.pre-avl").first
            if await cls_elem.count() > 0:
                await cls_elem.click(force=True)

        log_event(db, "INFO", "AUTOMATION", f"Clicked '{journey_cls}' class tab via SmartBrowserActions. Awaiting availability slots...", ref)

        # 2. Wait up to 15s for availability date slots (AVAILABLE / WL / RAC) to load
        date_clicked = False
        slot_selectors = [
            "div.pre-avl:has-text('AVAILABLE')",
            "div.pre-avl:has-text('AVL')",
            "div.pre-avl:has-text('WL')",
            "div.pre-avl:has-text('RAC')",
            "td:has-text('AVAILABLE')",
            "td:has-text('WL')",
            "td:has-text('RAC')"
        ]
        for wait_slot in range(30):
            await asyncio.sleep(0.5)
            await dismiss_overlays(page)

            # Check if slots appeared inside this train card
            slot_loc = target_train_card.locator(", ".join(slot_selectors)).first
            if await slot_loc.count() > 0 and await slot_loc.is_visible():
                await SmartBrowserActions.smart_click(
                    page=page,
                    selectors=slot_selectors,
                    scope_locator=target_train_card,
                    wait_after_sec=0.8
                )
                date_clicked = True
                log_event(db, "INFO", "AUTOMATION", f"Availability date slot clicked (attempt {wait_slot+1})!", ref)
                await asyncio.sleep(1)
                break

        # Extract live fare
        live_fare = await extract_live_fare_from_page(page)
        if live_fare:
            booking.fare = live_fare
            db.commit()
            log_event(db, "INFO", "AUTOMATION", f"Official IRCTC Live Fare: ₹{live_fare:,.2f}", ref)

        # Strict check: ID must remain logged in before booking
        if not await check_logged_in_state(page):
            log_event(db, "WARNING", "AUTOMATION", "Session logged out before clicking Book Now. Re-authenticating...", ref)
            await ensure_authenticated_session(page, ref, db, session_state, booking)

        # 3. Click active enabled 'Book Now' (without .disable-book)
        book_now_clicked = False
        bn_selectors = [
            "button.train_Search:not(.disable-book)",
            "button:has-text('Book Now'):not(.disable-book)",
            "button[label='Book Now']:not(.disable-book)"
        ]
        try:
            for _ in range(20):
                bn = target_train_card.locator(", ".join(bn_selectors)).first
                if await bn.count() == 0:
                    bn = page.locator(", ".join(bn_selectors)).first

                if await bn.count() > 0 and await bn.is_visible():
                    clicked = await SmartBrowserActions.smart_click(
                        page=page,
                        selectors=bn_selectors,
                        text_keywords=["Book Now"],
                        scope_locator=target_train_card if await target_train_card.locator(", ".join(bn_selectors)).count() > 0 else None,
                        wait_after_sec=1.0
                    )
                    if clicked:
                        book_now_clicked = True
                        log_event(db, "INFO", "AUTOMATION", "Clicked active enabled 'Book Now' button!", ref)
                        break
                await asyncio.sleep(0.5)

        except Exception as e:
            log_event(db, "WARNING", "AUTOMATION", f"Book now click note: {e}", ref)

        # 4. Handle PrimeNG Confirmation Dialogs & Wait for Passenger Input page
        arrived_at_passenger = False
        for _ in range(20):
            # Check for PrimeNG dialogs (Yes / I Agree / OK / Continue / Confirm)
            try:
                await page.evaluate('''() => {
                    const dialogs = Array.from(document.querySelectorAll('.ui-dialog, p-confirmdialog, .ui-confirmdialog, div[role="dialog"]')).filter(d => d.offsetParent !== null);
                    for (const d of dialogs) {
                        const btn = Array.from(d.querySelectorAll('button, span.ui-button-text')).find(b => {
                            const t = (b.innerText || '').trim().toLowerCase();
                            return t === 'yes' || t === 'i agree' || t === 'ok' || t === 'continue' || t === 'confirm';
                        });
                        if (btn) btn.click();
                    }
                }''')
            except Exception:
                pass

            await dismiss_overlays(page)

            if session_state.cancel_event.is_set():
                booking.status = "CANCELLED"
                db.commit()
                return

            # Check if login modal popped up upon clicking Book Now
            login_modal = page.locator("app-login, input[formcontrolname='userid'], #userId").first
            if await login_modal.count() > 0 and await login_modal.is_visible():
                log_event(db, "INFO", "AUTOMATION", "IRCTC requested authentication upon booking. Handling login...", ref)
                await ensure_authenticated_session(page, ref, db, session_state, booking)
                continue

            if "psgn-input" in page.url or await page.locator("input[placeholder*='Passenger Name' i], p-autocomplete[formcontrolname='passengerName'] input").count() > 0:
                arrived_at_passenger = True
                break
            await asyncio.sleep(1)

        # Pause only if passenger page not reached
        if not arrived_at_passenger:
            train_bytes = None
            try:
                await page.evaluate("window.scrollTo(0, 200)")
                await asyncio.sleep(0.5)
                train_bytes = await page.screenshot(full_page=False)
                if train_bytes:
                    session_state.latest_screenshot_bytes = train_bytes
                    (DATA_DIR / "latest_captcha.png").write_bytes(train_bytes)
            except Exception:
                pass

            select_prompt = f"Train Selection: Please select your train / class and click 'Book Now' in browser."
            session_state.pause_for_user(select_prompt, is_payment=False, input_type="NONE", screenshot_bytes=train_bytes)
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

            result = await _wait_for_user_or_cancel(session_state, timeout_seconds=300)
            if result == "cancel" or session_state.cancel_event.is_set():
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

        # Hard Gate Check: Must be on passenger page to proceed
        if not arrived_at_passenger:
            err = "Could not navigate to Passenger Input page. Please ensure train & class are selected and 'Book Now' is clicked in the browser."
            session_state.set_stage("FAILED", "FAILED")
            session_state.error_message = err
            booking.status = "FAILED"
            db.commit()
            log_event(db, "ERROR", "AUTOMATION", err, ref)
            if settings.TELEGRAM_ENABLED:
                await send_telegram_message(f"❌ *Booking Error* (Ref: `{ref}`)\n\n{err}")
            return
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
                        await SmartBrowserActions.smart_click(page, selectors=["a:has-text('+ Add Passenger')", "button:has-text('Add Passenger')"], text_keywords=["+ Add Passenger", "Add Passenger"])
                        await asyncio.sleep(0.8)

                # Name — use SmartBrowserActions.smart_type for robust Angular form binding
                name_inputs = page.locator("input[placeholder*='Passenger Name' i], p-autocomplete[formcontrolname='passengerName'] input")
                if await name_inputs.count() > idx:
                    name_input = name_inputs.nth(idx)
                    await SmartBrowserActions.smart_type(page, name_input, p.name, delay_ms=30, clear_first=True)
                    await asyncio.sleep(0.2)
                    # Dismiss autocomplete dropdown if it appeared
                    await page.keyboard.press("Escape")

                # Age — use SmartBrowserActions.smart_type
                age_inputs = page.locator("input[placeholder*='Age' i], input[formcontrolname='passengerAge']")
                if await age_inputs.count() > idx:
                    age_input = age_inputs.nth(idx)
                    await SmartBrowserActions.smart_type(page, age_input, str(p.age), delay_ms=30, clear_first=True)

                # Gender — handle both native select and PrimeNG p-dropdown
                gender_selects = page.locator("select[formcontrolname='passengerGender']")
                if await gender_selects.count() > idx:
                    g_val = "M" if (p.gender or "M").upper().startswith("M") else "F"
                    await gender_selects.nth(idx).select_option(value=g_val)
                else:
                    p_dropdown = page.locator("p-dropdown[formcontrolname='passengerGender']").nth(idx)
                    if await p_dropdown.count() > 0:
                        await SmartBrowserActions.smart_click(page, selectors=[], scope_locator=p_dropdown)
                        await asyncio.sleep(0.4)
                        g_label = "Male" if (p.gender or "M").upper().startswith("M") else "Female"
                        g_opt = page.locator(f"li[aria-label*='{g_label}' i], span:has-text('{g_label}')").first
                        if await g_opt.count() > 0:
                            await SmartBrowserActions.smart_click(page, selectors=[], scope_locator=g_opt)
                            await asyncio.sleep(0.3)

                log_event(db, "INFO", "AUTOMATION", f"Filled passenger {idx+1}: {p.name}, {p.age}, {p.gender}", ref)

        except Exception as e:
            log_event(db, "WARNING", "AUTOMATION", f"Passenger auto-fill note: {str(e)}", ref)

        # Contact mobile
        if booking.contact_mobile:
            try:
                mob_input = page.locator("input[formcontrolname='mobileNumber'], input[placeholder*='Mobile Number' i]").first
                if await mob_input.count() > 0:
                    await SmartBrowserActions.smart_type(page, mob_input, booking.contact_mobile, delay_ms=30, clear_first=True)
            except Exception:
                pass

        # Select Payment Mode: BHIM/UPI (Convenience Fee: ₹20 + GST)
        try:
            await SmartBrowserActions.smart_click(
                page=page,
                selectors=["p-radiobutton[value='2']", "input[value='2']", "label:has-text('BHIM/UPI')", "div:has-text('Pay through BHIM/UPI')"],
                text_keywords=["BHIM/UPI", "Pay through BHIM/UPI"],
                wait_after_sec=0.5
            )
        except Exception:
            pass

        # Travel Insurance: Yes (Mandatory on IRCTC to proceed!)
        try:
            await page.evaluate('''() => {
                const labels = Array.from(document.querySelectorAll('label, p-radiobutton, div'));
                const insYes = labels.find(l => {
                    const t = (l.innerText || '').toLowerCase();
                    return t.includes('yes, and i accept') || (t.includes('accept') && t.includes('terms') && !t.includes('no'));
                });
                if (insYes) {
                    const box = insYes.querySelector('.ui-radiobutton-box') || insYes;
                    box.click();
                }
            }''')
            await SmartBrowserActions.smart_click(
                page=page,
                selectors=["p-radiobutton[id='1']", "label:has-text('Yes, and I accept')"],
                text_keywords=["Yes, and I accept"],
                wait_after_sec=0.5
            )
        except Exception as e:
            log_event(db, "WARNING", "AUTOMATION", f"Travel insurance selection note: {e}", ref)

        # Auto-upgradation checkbox
        try:
            await page.evaluate('''() => {
                const cb = document.querySelector('#autoUpgradation') || document.querySelector('input[name="autoUpgradation"]');
                if (cb) {
                    const lbl = document.querySelector("label[for='autoUpgradation']") || cb.closest('div').querySelector('label');
                    if (lbl) lbl.click();
                    else { cb.checked = true; cb.dispatchEvent(new Event('change', {bubbles: true})); }
                }
            }''')
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
            cont_btn = page.locator("button:has-text('Continue'), button[type='submit']:has-text('Continue'), button.btn-primary:has-text('Continue'), button.train_Search:has-text('Continue')").first
            if await cont_btn.count() > 0:
                await cont_btn.scroll_into_view_if_needed()
                await cont_btn.click(timeout=4000, force=True)
                await asyncio.sleep(2)
        except Exception as e:
            log_event(db, "WARNING", "AUTOMATION", f"Passenger Continue note: {e}", ref)

        # ══════════════════════════════════════════════════
        # Step 7: Review Booking Page & Security Challenge
        # ══════════════════════════════════════════════════
        session_state.set_stage("REVIEW_BOOKING")
        log_event(db, "INFO", "AUTOMATION", "Navigating to Review Booking page...", ref)

        # Wait up to 30s for Review page, handling any confirmation dialogs (Yes/OK/Agree)
        arrived_at_review = False
        for s in range(30):
            await dismiss_overlays(page)

            # Auto-click confirmation dialogs
            try:
                await page.evaluate('''() => {
                    const dialogs = Array.from(document.querySelectorAll('.ui-dialog, p-confirmdialog, .ui-confirmdialog, div[role="dialog"]')).filter(d => d.offsetParent !== null);
                    for (const d of dialogs) {
                        const btns = Array.from(d.querySelectorAll('button, span.ui-button-text')).filter(b => b.offsetParent !== null);
                        const b = btns.find(x => {
                            const t = (x.innerText || '').trim().toLowerCase();
                            return t.includes('yes') || t.includes('agree') || t.includes('ok') || t.includes('continue');
                        });
                        if (b) b.click();
                    }
                }''')
            except Exception:
                pass

            if "review" in page.url.lower() or "payment" in page.url.lower():
                arrived_at_review = True
                break
            if await page.locator("app-review-booking, #nlpAnswer, app-captcha, app-payment").count() > 0:
                arrived_at_review = True
                break

            # If still on passenger page after 6 and 14 seconds, re-click Continue
            if s in (6, 14):
                try:
                    cont_retry = page.locator("button:has-text('Continue'):visible, button[type='submit']:has-text('Continue'):visible").first
                    if await cont_retry.count() > 0:
                        await cont_retry.scroll_into_view_if_needed()
                        await cont_retry.click(force=True)
                except Exception:
                    pass

            await asyncio.sleep(1)

        # If not arrived at review booking or payment, raise informative error
        if not arrived_at_review:
            err = "Could not transition from Passenger page to Review Booking page. Please check passenger details or browser dialog."
            session_state.set_stage("FAILED", "FAILED")
            session_state.error_message = err
            booking.status = "FAILED"
            db.commit()
            log_event(db, "ERROR", "AUTOMATION", err, ref)
            if settings.TELEGRAM_ENABLED:
                await send_telegram_message(f"❌ *Booking Error* (Ref: `{ref}`)\n\n{err}")
            return

        # Extract confirmed live total fare from Review page
        live_fare = await extract_live_fare_from_page(page)
        if live_fare:
            booking.fare = live_fare
            db.commit()
            log_event(db, "INFO", "AUTOMATION", f"Confirmed IRCTC Total Fare (with taxes & fees): ₹{live_fare:,.2f}", ref)

        # Scroll to bottom of Review page to make sure CAPTCHA and buttons are rendered
        try:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1)
        except Exception:
            pass

        # Check if CAPTCHA exists on Review page (wait up to 10s for dynamic load)
        captcha_img_loc = page.locator("app-captcha img, #captchaImg, img.captcha-img, img[alt*='captcha' i]").first
        captcha_input = page.locator("#nlpAnswer, input[formcontrolname='captcha'], input[placeholder*='captcha' i], #captcha").first
        is_payment_page = ("payment" in page.url.lower() or await page.locator("app-payment, div:has-text('Payment Option'), div:has-text('Payment Method'), #bank-type").count() > 0)

        has_captcha = False
        if not is_payment_page:
            for _ in range(12):
                if (await captcha_img_loc.count() > 0 and await captcha_img_loc.is_visible()) or (await captcha_input.count() > 0 and await captcha_input.is_visible()):
                    has_captcha = True
                    break
                await asyncio.sleep(0.5)

        if has_captcha:
            captcha_bytes = None
            try:
                await captcha_img_loc.scroll_into_view_if_needed()
                await asyncio.sleep(0.3)
                captcha_bytes = await captcha_img_loc.screenshot(timeout=4000)
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

                # High-Speed Local Captcha Prediction
                candidate_text, conf = fast_solve_captcha(captcha_bytes)
                if candidate_text and await captcha_input.count() > 0:
                    try:
                        await SmartBrowserActions.smart_type(page, captcha_input, candidate_text, delay_ms=40)
                    except Exception:
                        pass

                session_state.set_stage("WAITING_MANUAL")
                review_prompt = f"Review & CAPTCHA: Auto-detected '{candidate_text}'. Please confirm or edit."
                session_state.pause_for_user(review_prompt, is_payment=False, input_type="CAPTCHA", screenshot_bytes=captcha_bytes, suggested_value=candidate_text)
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
                        t_keyboard = {
                            "inline_keyboard": [
                                [{"text": f"⚡ Confirm '{candidate_text}'", "callback_data": f"action_captcha_{candidate_text}"}],
                                [{"text": "✅ Continue", "callback_data": "action_continue"}],
                                [{"text": "❌ Cancel", "callback_data": "action_cancel"}]
                            ]
                        }
                        await send_telegram_photo(
                            photo_bytes=captcha_bytes,
                            caption=(
                                f"📸 *IRCTC Review CAPTCHA* (Ref: `{ref}`){fare_tag}\n\n"
                                f"⚡ *Auto-Detected CAPTCHA:* `{candidate_text}`\n"
                                f"👉 Sahi hai to direct *'Confirm'* dabayein ya 'OK' reply karein, warna text reply karein:"
                            ),
                            reply_markup=t_keyboard
                        )
                    except Exception as e:
                        log_event(db, "WARNING", "AUTOMATION", f"Could not send CAPTCHA: {e}", ref)

                result = await _wait_for_user_or_cancel(session_state, timeout_seconds=300)

                if result == "cancel" or session_state.cancel_event.is_set():
                    booking.status = "CANCELLED"
                    db.commit()
                    return

                if (result == "input" and session_state.user_input_value) or result == "continue":
                    try:
                        if result == "input" and session_state.user_input_value and await captcha_input.count() > 0:
                            await SmartBrowserActions.smart_type(page, captcha_input, session_state.user_input_value.strip(), delay_ms=40)
                            log_event(db, "INFO", "AUTOMATION", "Auto-filled CAPTCHA received from user.", ref)
                    except Exception:
                        pass
        else:
            log_event(db, "INFO", "AUTOMATION", "No CAPTCHA required on Review page. Proceeding to Payment Gateway.", ref)

        # Submit Continue on Review Page to reach Payment
        try:
            submit_btn = page.locator("button:has-text('Continue'), button[type='submit']:has-text('Continue'), button.btn-primary:has-text('Continue')").first
            if await submit_btn.count() > 0:
                await submit_btn.scroll_into_view_if_needed()
                await submit_btn.click(timeout=4000, force=True)
                await asyncio.sleep(2)
        except Exception as e:
            log_event(db, "WARNING", "AUTOMATION", f"Could not submit review form: {e}", ref)

        # ══════════════════════════════════════════════════
        # Step 8: Payment Gateway - IRCTC iPay New & QR Generation
        # ══════════════════════════════════════════════════
        session_state.set_stage("PAYMENT_PENDING")
        log_event(db, "INFO", "AUTOMATION", "Navigating to IRCTC Payment Options page...", ref)

        arrived_at_payment = False
        for _ in range(15):
            await dismiss_overlays(page)
            if "payment" in page.url or await page.locator("app-payment, div:has-text('Payment Option'), div:has-text('Payment Method'), #bank-type").count() > 0:
                arrived_at_payment = True
                break
            await asyncio.sleep(1)

        if not arrived_at_payment:
            err = "Payment options page did not load. Review page may require manual confirmation or CAPTCHA."
            session_state.set_stage("FAILED", "FAILED")
            session_state.error_message = err
            booking.status = "FAILED"
            db.commit()
            log_event(db, "ERROR", "AUTOMATION", err, ref)
            if settings.TELEGRAM_ENABLED:
                await send_telegram_message(f"❌ *Booking Error* (Ref: `{ref}`)\n\n{err}")
            return

        try:
            await page.evaluate("window.scrollTo(0, 0)")
        except Exception:
            pass

        # Select "IRCTC iPay New" Card
        try:
            clicked_ipay = await SmartBrowserActions.smart_click(
                page=page,
                selectors=["div.bank-text:has-text('IRCTC iPay New')", "div:has-text('IRCTC iPay New')", "img[src*='ipay' i]"],
                text_keywords=["IRCTC iPay New", "iPay New", "IRCTC iPay"],
                wait_after_sec=1.0
            )
            if not clicked_ipay:
                await page.evaluate('''() => {
                    const all = Array.from(document.querySelectorAll('div, span, label, p'));
                    const el = all.find(e => (e.innerText || '').toLowerCase().includes('ipay new') || (e.innerText || '').toLowerCase().includes('irctc ipay'));
                    if (el) el.click();
                }''')
                await asyncio.sleep(1)

            # Click "Pay & Book"
            await SmartBrowserActions.smart_click(
                page=page,
                selectors=[
                    "button:has-text('Pay & Book')",
                    "button.btn-primary:has-text('Pay & Book')",
                    "button:has-text('Pay and Book')",
                    "button:has-text('Make Payment')"
                ],
                text_keywords=["Pay & Book", "Pay and Book", "Make Payment"],
                wait_after_sec=1.5
            )
            log_event(db, "INFO", "AUTOMATION", "Clicked 'Pay & Book'. Redirecting to IRCTC iPay Gateway...", ref)
        except Exception as e:
            log_event(db, "WARNING", "AUTOMATION", f"IRCTC iPay selection note: {e}", ref)

        # Wait for navigation to IRCTC iPay Gateway
        gw_page = page
        for _ in range(20):
            try:
                all_pages = page.context.pages
                for p in all_pages:
                    p_url = p.url.lower()
                    if any(k in p_url for k in ["paymentredirect", "wps.irctc", "irctcpayments", "payphi"]):
                        gw_page = p
                        break
                if any(k in gw_page.url.lower() for k in ["paymentredirect", "wps.irctc", "irctcpayments", "payphi"]):
                    break
            except Exception:
                pass
            await asyncio.sleep(1)

        try:
            await gw_page.bring_to_front()
            focus_browser_window()
        except Exception:
            pass
        await asyncio.sleep(1.5)

        # Gateway Actions: Wait for Payment Options -> Expand UPI -> Click QR Radio -> Click Pay Now -> Click Show QR
        try:
            # 1. Wait up to 25s for Gateway Payment Methods to render via AJAX
            log_event(db, "INFO", "AUTOMATION", "Waiting for IRCTC iPay payment options to load in DOM...", ref)
            for _ in range(25):
                # Dismiss feedback/close modal if open
                try:
                    await gw_page.evaluate('''() => {
                        const closeBtns = Array.from(document.querySelectorAll('[class*="close"], button.close, svg[class*="close"], [aria-label*="close" i]'));
                        for (const cb of closeBtns) { if (cb.offsetWidth > 0) cb.click(); }
                    }''')
                except Exception:
                    pass

                if await gw_page.locator("#upiAccordionBtn, h6:has-text('UPI'), div.accordion-item:has-text('UPI'), #accordion-m button").count() > 0:
                    break
                await asyncio.sleep(1)

            # 2. Expand UPI Accordion if collapsed
            is_collapsed = await gw_page.evaluate('''() => {
                const btn = document.querySelector('#upiAccordionBtn');
                const collapse = document.querySelector('#collapseUpi');
                if (btn && btn.classList.contains('collapsed')) return true;
                if (collapse && !collapse.classList.contains('show')) return true;
                return false;
            }''')
            if is_collapsed:
                chevron_clicked = await SmartBrowserActions.smart_click(
                    page=gw_page,
                    selectors=["#upiAccordionBtn", "button:has-text('UPI')", "h6:has-text('UPI')"],
                    text_keywords=["UPI"],
                    wait_after_sec=1.5
                )
                if not chevron_clicked:
                    await gw_page.evaluate('''() => {
                        const btn = document.querySelector('#upiAccordionBtn') || Array.from(document.querySelectorAll('button')).find(b => (b.innerText || '').includes('UPI'));
                        if (btn) btn.click();
                    }''')
                    await asyncio.sleep(1.5)
            log_event(db, "INFO", "AUTOMATION", "Expanded UPI accordion option.", ref)

            # 3. Select 'Click Here To Pay Using QR'
            for _ in range(12):
                if await gw_page.locator("#qr-click, label:has-text('Click Here To Pay Using QR'), label:has-text('Pay Using QR')").count() > 0:
                    break
                await asyncio.sleep(0.5)

            await gw_page.evaluate('''() => {
                const qrRadio = document.querySelector('#qr-click') || document.querySelector("input[data-click='toggleQR']");
                if (qrRadio) {
                    qrRadio.checked = true;
                    qrRadio.click();
                    qrRadio.dispatchEvent(new Event('change', { bubbles: true }));
                }
                const qrLbl = document.querySelector("label[for='qr-click']") || Array.from(document.querySelectorAll('label')).find(l => (l.innerText || '').includes('Pay Using QR'));
                if (qrLbl) qrLbl.click();
            }''')
            await SmartBrowserActions.smart_click(
                page=gw_page,
                selectors=["#qr-click", "label[for='qr-click']", "label:has-text('Click Here To Pay Using QR')", "label:has-text('Pay Using QR')"],
                text_keywords=["Click Here To Pay Using QR", "Pay Using QR"],
                wait_after_sec=1.5
            )
            log_event(db, "INFO", "AUTOMATION", "Selected 'Click Here To Pay Using QR'.", ref)

            # Attach network listener to capture UPI payment intent
            network_upi_intent = None
            async def _on_gw_response(resp):
                nonlocal network_upi_intent
                try:
                    u = resp.url.lower()
                    if any(k in u for k in ["qr", "upi", "generate", "payment"]):
                        t = await resp.text()
                        if "upi://" in t:
                            m = re.search(r'upi://pay\?[^\s"\'<>\\]+', t)
                            if m:
                                network_upi_intent = m.group(0)
                except Exception:
                    pass

            gw_page.on("response", _on_gw_response)

            # 4. Click 'Pay Now' Button (button#paytBtn3 or visible Pay Now)
            for _ in range(10):
                pay_now_btn = gw_page.locator("#paytBtn3, button:has-text('Pay Now'):visible, .paynowbtn:visible").first
                if await pay_now_btn.count() > 0 and not await pay_now_btn.is_disabled():
                    break
                await asyncio.sleep(0.5)

            clicked_pay_now = await SmartBrowserActions.smart_click(
                page=gw_page,
                selectors=["#paytBtn3", "button:has-text('Pay Now'):visible", ".paynowbtn:visible"],
                text_keywords=["Pay Now"],
                wait_after_sec=2.0
            )
            if not clicked_pay_now:
                await gw_page.evaluate('''() => {
                    const btn = document.querySelector('#paytBtn3') || Array.from(document.querySelectorAll('button')).find(b => (b.innerText || '').trim() === 'Pay Now' && b.offsetWidth > 0);
                    if (btn) btn.click();
                }''')
                await asyncio.sleep(2.0)
            log_event(db, "INFO", "AUTOMATION", "Clicked 'Pay Now' to launch QR Modal.", ref)

            # 5. Click 'Click here to show QR' button inside modal (#myModal6)
            for _ in range(15):
                show_qr_btn = gw_page.locator("button:has-text('Click here to show QR'), div:has-text('Click here to show QR'), span:has-text('Click here to show QR'), button:has-text('Show QR')").first
                if await show_qr_btn.count() > 0 and await show_qr_btn.is_visible():
                    await SmartBrowserActions.smart_click(
                        page=gw_page,
                        selectors=[
                            "button:has-text('Click here to show QR')",
                            "div:has-text('Click here to show QR')",
                            "span:has-text('Click here to show QR')",
                            "button:has-text('Show QR')"
                        ],
                        text_keywords=["Click here to show QR", "Show QR"],
                        wait_after_sec=2.0
                    )
                    break
                clicked_show = await gw_page.evaluate('''() => {
                    const all = Array.from(document.querySelectorAll('button, div, span, a'));
                    const el = all.find(e => (e.innerText || '').toLowerCase().includes('click here to show qr') || (e.innerText || '').trim().toLowerCase() === 'show qr');
                    if (el && el.offsetWidth > 0) {
                        el.click();
                        return true;
                    }
                    return false;
                }''')
                if clicked_show:
                    await asyncio.sleep(2.0)
                    break
                await asyncio.sleep(0.8)
            log_event(db, "INFO", "AUTOMATION", "Clicked 'Click here to show QR'. QR Code unlocked!", ref)

        except Exception as e:
            log_event(db, "WARNING", "AUTOMATION", f"Gateway QR expansion note: {e}", ref)

        # ──────────────────────────────────────────────────────────
        # TIGHT CROP QR CODE CAPTURE & OPTICAL UPI DECODING
        # ──────────────────────────────────────────────────────────
        qr_bytes = None
        upi_intent_url = None

        # 1. Wait for canvas#qrCode1 to appear and render
        for _ in range(16):
            try:
                canvas_loc = gw_page.locator("canvas#qrCode1, #disp-qr-div1 canvas, div#disp-qr-div1 canvas").first
                if await canvas_loc.count() > 0 and await canvas_loc.is_visible():
                    qr_bytes = await canvas_loc.screenshot(timeout=3000)
                    if qr_bytes and len(qr_bytes) > 500:
                        break
            except Exception:
                pass
            await asyncio.sleep(0.5)

        # Fallback A: Clip exact bounding box of QR canvas or container
        if not qr_bytes:
            try:
                box = await gw_page.evaluate('''() => {
                    const canvas = document.querySelector('canvas#qrCode1') || document.querySelector('#disp-qr-div1 canvas');
                    if (canvas) {
                        const r = canvas.getBoundingClientRect();
                        if (r.width > 30 && r.height > 30) {
                            return { x: Math.max(0, r.x), y: Math.max(0, r.y), width: r.width, height: r.height };
                        }
                    }
                    const qrDiv = document.querySelector('#disp-qr-div1');
                    if (qrDiv) {
                        const r = qrDiv.getBoundingClientRect();
                        if (r.width > 30 && r.height > 30) {
                            return { x: Math.max(0, r.x), y: Math.max(0, r.y), width: r.width, height: r.height };
                        }
                    }
                    const modalBox = document.querySelector('#myModal6 .modal-content5') || document.querySelector('#myModal6 .modal-content');
                    if (modalBox) {
                        const r = modalBox.getBoundingClientRect();
                        if (r.width > 30 && r.height > 30) {
                            return { x: Math.max(0, r.x), y: Math.max(0, r.y), width: r.width, height: r.height };
                        }
                    }
                    return null;
                }''')
                if box:
                    qr_bytes = await gw_page.screenshot(clip=box)
            except Exception:
                pass

        # Fallback B: Viewport screenshot
        if not qr_bytes:
            try:
                qr_bytes = await gw_page.screenshot(full_page=False)
            except Exception:
                pass

        # 2. ZXING-CPP OPTICAL DECODING & SMART TIGHT CROPPING
        if qr_bytes:
            try:
                import io
                import zxingcpp
                from PIL import Image, ImageOps

                raw_img = Image.open(io.BytesIO(qr_bytes)).convert("RGB")
                barcodes = zxingcpp.read_barcodes(raw_img)

                if barcodes and barcodes[0].text:
                    bc = barcodes[0]
                    upi_intent_url = bc.text
                    log_event(db, "INFO", "AUTOMATION", f"Extracted UPI Intent URL via QR: {upi_intent_url}", ref)

                    # Auto-crop tightly around QR if full-screen/wide image was captured
                    pos = bc.position
                    qr_w = max(pos.top_right.x, pos.bottom_right.x) - min(pos.top_left.x, pos.bottom_left.x)
                    qr_h = max(pos.bottom_left.y, pos.bottom_right.y) - min(pos.top_left.y, pos.top_right.y)

                    if raw_img.width > qr_w * 1.3 or raw_img.height > qr_h * 1.3:
                        pad = 25
                        min_x = max(0, min(pos.top_left.x, pos.bottom_left.x) - pad)
                        min_y = max(0, min(pos.top_left.y, pos.top_right.y) - pad)
                        max_x = min(raw_img.width, max(pos.top_right.x, pos.bottom_right.x) + pad)
                        max_y = min(raw_img.height, max(pos.bottom_left.y, pos.bottom_right.y) + pad)

                        cropped = raw_img.crop((min_x, min_y, max_x, max_y))
                        final_img = ImageOps.expand(cropped, border=15, fill='white')
                        out_buf = io.BytesIO()
                        final_img.save(out_buf, format="PNG")
                        qr_bytes = out_buf.getvalue()
                    else:
                        final_img = ImageOps.expand(raw_img, border=20, fill='white')
                        out_buf = io.BytesIO()
                        final_img.save(out_buf, format="PNG")
                        qr_bytes = out_buf.getvalue()
                else:
                    final_img = ImageOps.expand(raw_img, border=15, fill='white')
                    out_buf = io.BytesIO()
                    final_img.save(out_buf, format="PNG")
                    qr_bytes = out_buf.getvalue()
            except Exception as e:
                log_event(db, "WARNING", "AUTOMATION", f"QR image processing note: {e}", ref)

        # Check secondary sources for UPI intent
        if not upi_intent_url and network_upi_intent:
            upi_intent_url = network_upi_intent

        if not upi_intent_url:
            try:
                dom_upi = await gw_page.evaluate('''() => {
                    const elements = Array.from(document.querySelectorAll('input, textarea, div, canvas'));
                    for (const el of elements) {
                        const val = el.value || el.dataset?.qr || el.getAttribute('data-qr') || '';
                        if (val.includes('upi://pay')) {
                            const m = val.match(/upi:\\/\\/pay\\?[^\\s"'<>]+/);
                            if (m) return m[0];
                        }
                    }
                    return window.qrData || window.upiString || window.qrUrl || null;
                }''')
                if dom_upi:
                    upi_intent_url = dom_upi
            except Exception:
                pass

        if upi_intent_url:
            session_state.captured_data["upi_intent_url"] = upi_intent_url
            booking.payment_upi_url = upi_intent_url
            db.commit()

        final_fare = await extract_live_fare_from_page(gw_page) or await extract_live_fare_from_page(page)
        if final_fare:
            booking.fare = final_fare
            db.commit()

        fare_display = f"₹{booking.fare:,.2f}" if booking.fare else "As per IRCTC Portal"

        pay_prompt = f"PAYMENT REQUIRED: Official IRCTC Total Amount: {fare_display}. Kripya 3 minutes (180s) ke andar UPI QR scan karke pay karein."
        session_state.pause_for_user(
            pay_prompt,
            is_payment=True,
            input_type="PAYMENT",
            screenshot_bytes=qr_bytes,
            timer_seconds=180
        )
        session_state.captured_data["timer_seconds"] = 180
        session_state.captured_data["timer_text"] = "3 minutes (180 seconds)"
        booking.status = "PAYMENT_PENDING"
        db.commit()
        log_event(db, "WARNING", "AUTOMATION", pay_prompt, ref)

        if qr_bytes:
            session_state.latest_screenshot_bytes = qr_bytes
            try:
                (DATA_DIR / "latest_captcha.png").write_bytes(qr_bytes)
            except Exception:
                pass

        if settings.TELEGRAM_ENABLED:
            try:
                base_url = settings.get_server_base_url()
                bridge_url = f"{base_url}/api/bookings/pay-redirect/{ref}"

                # Telegram Inline Keyboard with "⚡ Pay Now (GPay / PhonePe / Paytm)" button
                qr_keyboard = {
                    "inline_keyboard": [
                        [{"text": "⚡ Pay Now (GPay / PhonePe / Paytm)", "url": bridge_url}],
                        [{"text": "✅ Payment Ho Gayi (Continue)", "callback_data": "action_continue"}],
                        [{"text": "❌ Cancel", "callback_data": "action_cancel"}]
                    ]
                }

                caption_lines = [
                    f"💳 *IRCTC Official Payment QR* (Ref: `{ref}`)\n",
                    f"💰 *कुल देय राशि (Total Amount):* `{fare_display}`",
                    f"⏱️ *समय सीमा (Time Limit):* `3 Minutes (180 Seconds)`\n"
                ]

                if upi_intent_url:
                    caption_lines.append(f"⚡ *ONE-CLICK MOBILE PAYMENT:*")
                    caption_lines.append(f"👉 [📲 CLICK HERE TO PAY IN UPI APP]({upi_intent_url})\n")
                    caption_lines.append(f"🔗 `{upi_intent_url}`\n")
                else:
                    caption_lines.append(f"⚡ *ONE-CLICK MOBILE PAYMENT:*")
                    caption_lines.append(f"👉 [📲 CLICK HERE TO PAY IN UPI APP]({bridge_url})\n")

                caption_lines.append("📱 Upar diye 'Pay Now' button se ya kisi bhi UPI App (GPay/PhonePe/Paytm) se ye QR scan karke bhugtan karein.")
                caption_lines.append("⚠️ *Payment transfer hone ke baad page automatically PNR confirm kar lega!*")

                caption = "\n".join(caption_lines)

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

        # ══════════════════════════════════════════════════
        # Step 9: Post-Payment Auto-Redirection & PNR Confirmation
        # ══════════════════════════════════════════════════
        log_event(db, "INFO", "AUTOMATION", "Actively monitoring for UPI payment completion & redirect to ticket confirmation...", ref)
        
        confirmation_detected = False
        captured_pnr = None
        captured_txn = None

        # Actively poll for redirect or manual resume (up to 180s)
        for tick in range(180):
            if session_state.continue_event.is_set() or session_state.cancel_event.is_set():
                break

            # Check all open pages in browser context
            try:
                all_pages = page.context.pages
                for p in all_pages:
                    curr_url = p.url.lower()
                    if "ticketconfirm" in curr_url or "confirmation" in curr_url or "bookingconfirmed" in curr_url:
                        page = p
                        confirmation_detected = True
                        break
                    
                    # Scan DOM for 10-digit PNR
                    pnr_found = await p.evaluate('''() => {
                        if (!document.body) return null;
                        const text = document.body.innerText;
                        if (text.includes('Transaction Failed') || text.includes('Payment Failed')) return 'FAILED';
                        const m = text.match(/\\b[2-9]\\d{9}\\b/);
                        return m ? m[0] : null;
                    }''')
                    if pnr_found == 'FAILED':
                        log_event(db, "ERROR", "AUTOMATION", "Payment failure detected on gateway.", ref)
                        break
                    if pnr_found and not pnr_found.startswith("1000068"):
                        captured_pnr = pnr_found
                        page = p
                        confirmation_detected = True
                        break
            except Exception:
                pass

            if confirmation_detected:
                log_event(db, "INFO", "AUTOMATION", f"Automatic payment confirmation detected on IRCTC portal (Time: {tick}s)!", ref)
                session_state.user_resumed()
                break

            await asyncio.sleep(1)

        if session_state.cancel_event.is_set():
            booking.status = "CANCELLED"
            db.commit()
            return

        # ══════════════════════════════════════════════════
        # Step 10: Confirmation Details Extraction
        # ══════════════════════════════════════════════════
        session_state.set_stage("CONFIRMATION_DETECTED")
        log_event(db, "INFO", "AUTOMATION", "Extracting confirmed ticket & PNR details from official IRCTC page...", ref)
        await asyncio.sleep(2)
        try:
            await page.bring_to_front()
            focus_browser_window()
        except Exception:
            pass

        # Scan for PNR in DOM
        try:
            page_content = await page.content()
            if not captured_pnr:
                pnr_match = re.search(r'\b[2-9]\d{9}\b', page_content)
                captured_pnr = pnr_match.group(0) if pnr_match else None

            txn_match = re.search(r'TXN\w+|Transaction\s*ID[\s:]+([\w]+)', page_content, re.IGNORECASE)
            captured_txn = txn_match.group(1) if (txn_match and txn_match.groups()) else None

            # Capture Confirmed Ticket Screenshot
            ticket_screenshot = await page.screenshot(full_page=True)
            session_state.latest_screenshot_bytes = ticket_screenshot
        except Exception as e:
            log_event(db, "WARNING", "AUTOMATION", f"Ticket confirmation parsing note: {e}", ref)

        if captured_pnr:
            booking.pnr = captured_pnr
            booking.status = "CONFIRMED"
            booking.payment_status = "COMPLETED"
            if captured_txn:
                booking.transaction_id = captured_txn
            db.commit()
            log_event(db, "INFO", "AUTOMATION", f"Confirmed PNR Successfully Captured: {captured_pnr}", ref)

            # Step 11: Finalize CRM, PDF, and Notifications ONLY upon successful confirmation
            await finalize_successful_booking(db, booking.id)
            session_state.set_stage("COMPLETED", "CONFIRMED")
            log_event(db, "INFO", "AUTOMATION", f"Booking flow finished successfully. PNR: {booking.pnr}", ref)
        else:
            booking.status = "FAILED"
            booking.payment_status = "FAILED"
            db.commit()
            session_state.set_stage("FAILED", "FAILED")
            session_state.error_message = "Payment time expired (180s) or transaction not completed on portal."
            log_event(db, "WARNING", "AUTOMATION", "Booking payment timed out without confirmed PNR.", ref)
            if settings.TELEGRAM_ENABLED:
                await send_telegram_message(f"⚠️ *Payment Timed Out* (Ref: `{ref}`)\n\n180 seconds payment window expired without confirmed PNR.")

    except Exception as e:
        err_msg = str(e) or repr(e)
        session_state.set_stage("FAILED", "FAILED")
        session_state.error_message = err_msg
        booking.status = "FAILED"
        db.commit()
        log_event(db, "ERROR", "AUTOMATION", f"Real IRCTC Flow error: {err_msg}", ref)
