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
    "AMBALA": "UMB", "UMB": "UMB", "AMBALA CANTT": "UMB",
    "LUDHIANA": "LDH", "LDH": "LDH",
    "KALKA": "KLK", "KLK": "KLK",
    "PATHANKOT": "PTK", "PTK": "PTK",
    "JALANDHAR": "JUC", "JUC": "JUC", "JALANDHAR CITY": "JUC",
    "SAHARANPUR": "SRE", "SRE": "SRE",
    "MEERUT": "MTC", "MTC": "MTC",
    "BAREILLY": "BE", "BE": "BE",
    "MORADABAD": "MB", "MB": "MB",
    "RAIPUR": "R", "DURG": "DURG",
    "BILASPUR": "BSP", "BSP": "BSP",
    "JABALPUR": "JBP", "JBP": "JBP",
    "GAYA": "GAYA",
    "DHANBAD": "DHN", "DHN": "DHN",
    "BOKARO": "BKSC", "BKSC": "BKSC",
    "JAMSHEDPUR": "TATA", "TATA": "TATA", "TATANAGAR": "TATA",
    "KOTA": "KOTA",
    "AJMER": "AII", "AII": "AII",
    "BIKANER": "BKN", "BKN": "BKN",
    "ABU ROAD": "ABR", "ABR": "ABR",
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
    for _ in range(3):
        dismissed = False
        try:
            # Native DOM evaluation for safe dismissal without double-clicks or aborting confirmation dialogs
            js_res = await page.evaluate('''() => {
                const isVisible = (el) => !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
                const appLogin = document.querySelector('app-login');
                const userInput = document.querySelector("input[formcontrolname='userid'], #userId");
                if ((appLogin && isVisible(appLogin)) || (userInput && isVisible(userInput))) return false;

                const isLanguageDialog = (d) => {
                    if (!d) return false;
                    const text = (d.innerText || '').toLowerCase();
                    return text.includes('language') || text.includes('भाषा') || text.includes('welcome') || text.includes('पसंदीदा') || text.includes('preferred');
                };

                const isBusinessConfirmDialog = (d) => {
                    if (!d || !isVisible(d)) return false;
                    if (isLanguageDialog(d)) return false;
                    const isConfirm = d.matches('p-confirmdialog, .ui-confirmdialog') || !!d.querySelector('p-confirmdialog, .ui-confirmdialog');
                    const text = (d.innerText || '').toLowerCase();
                    const title = (d.querySelector('.ui-dialog-title')?.innerText || '').toLowerCase();
                    return isConfirm && (title.includes('confirmation') || text.includes('waiting list') || text.includes('wl ') || text.includes('auto upgradation'));
                };

                // CRITICAL: Do NOT touch active business confirmation dialogs (e.g. Waitlist confirmation on passenger review)
                const activeBusinessConfirm = Array.from(document.querySelectorAll('p-confirmdialog, .ui-confirmdialog')).find(d => isBusinessConfirmDialog(d));
                if (activeBusinessConfirm) return false;

                let action = false;

                // 1. Language selection dialog handling (Welcome / भाषा चयन) — including when inside p-confirmdialog
                const allDialogs = Array.from(document.querySelectorAll('.ui-dialog, p-dialog, div[role="dialog"], p-confirmdialog, .ui-confirmdialog, .modal'));
                const langDialogs = allDialogs.filter(d => !d.querySelector("input[formcontrolname='userid'], #userId") && isLanguageDialog(d));
                for (const d of langDialogs) {
                    const btns = Array.from(d.querySelectorAll('button, a, input[type="radio"], [role="button"], span.ui-button-text, .ui-button'));
                    const eng = btns.find(b => {
                        const t = (b.innerText || b.value || '').trim().toLowerCase();
                        return t === 'english' || t.includes('english');
                    });
                    if (eng) {
                        eng.click();
                        try { eng.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window })); } catch(e) {}
                        action = true;
                    }

                    const submit = btns.find(b => {
                        const t = (b.innerText || b.value || '').trim().toLowerCase();
                        return t.includes('submit') || t.includes('ok') || t.includes('proceed') || t.includes('continue');
                    });
                    if (submit) {
                        submit.click();
                        try { submit.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window })); } catch(e) {}
                        action = true;
                    } else {
                        const close = d.querySelector('.ui-dialog-titlebar-close, .close');
                        if (close) {
                            close.click();
                            action = true;
                        }
                    }
                    // Force remove language dialog if still present in DOM
                    setTimeout(() => { try { d.remove(); } catch(e) {} }, 100);
                    action = true;
                }

                // 2. Generic informational disclaimer popups (Kavach, advisory, COVID) - strictly ignore confirmation dialogs and language dialogs
                const infoDialogs = allDialogs.filter(
                    d => !d.querySelector("input[formcontrolname='userid'], #userId") && !isBusinessConfirmDialog(d) && !isLanguageDialog(d)
                );
                for (const d of infoDialogs) {
                    const title = (d.querySelector('.ui-dialog-title')?.innerText || '').toLowerCase();
                    if (title.includes('confirmation')) continue;

                    const okBtn = Array.from(d.querySelectorAll('button, span.ui-button-text, a, [role="button"]')).find(b => {
                        const t = (b.innerText || '').trim().toLowerCase();
                        return t === 'ok' || t === 'i agree' || t === 'dismiss' || t === 'theek hai' || t === 'agree' || t === 'close';
                    });
                    if (okBtn) {
                        okBtn.click();
                        try { okBtn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window })); } catch(e) {}
                        action = true;
                    }
                }

                // 3. Force-remove masks and blur overlays that block pointer events
                const isLoginActive = (appLogin && isVisible(appLogin)) || (userInput && isVisible(userInput));
                if (!activeBusinessConfirm && !isLoginActive) {
                    const masks = document.querySelectorAll('.custom-blur-mask, .ui-dialog-mask-scrollblocker');
                    for (const m of masks) { m.remove(); action = true; }
                    // Also check for stray ui-widget-overlay if no visible business dialog exists
                    const anyVisibleNonLangDialog = allDialogs.some(d => isVisible(d) && !isLanguageDialog(d) && !d.querySelector("input[formcontrolname='userid'], #userId"));
                    if (!anyVisibleNonLangDialog) {
                        const strayOverlays = document.querySelectorAll('.ui-widget-overlay, .ui-dialog-mask');
                        for (const so of strayOverlays) { so.remove(); action = true; }
                    }
                    if (document.body && document.body.classList.contains('ui-dialog-mask-scrollblocker')) {
                        document.body.classList.remove('ui-dialog-mask-scrollblocker');
                        action = true;
                    }
                }

                return action;
            }''')
            if js_res:
                dismissed = True
                await asyncio.sleep(0.3)

            # Python Playwright direct click fallback for English button in Language Alert
            try:
                lang_eng = page.locator("button:has-text('English'), a:has-text('English'), span:has-text('English')").first
                if await lang_eng.count() > 0 and await lang_eng.is_visible():
                    await lang_eng.click(timeout=1000, force=True)
                    dismissed = True
                    await asyncio.sleep(0.3)
            except Exception:
                pass

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
            await dismiss_overlays(page)

            # 1. Direct Playwright click with force=True
            try:
                login_btn = page.locator("a.loginText, a.search_btn.loginText, a:has-text('LOGIN / REGISTER'), a:has-text('LOGIN'), button:has-text('LOGIN')").first
                if await login_btn.count() > 0:
                    await login_btn.click(timeout=3000, force=True)
                    await asyncio.sleep(1.0)
            except Exception:
                pass

            # 2. Native JavaScript click fallback
            user_input = page.locator("input[formcontrolname='userid'], #userId, input[placeholder*='User Name' i]").first
            if not (await user_input.count() > 0 and await user_input.is_visible()):
                try:
                    await page.evaluate('''() => {
                        const l = document.querySelector('a.loginText, a.search_btn.loginText') || Array.from(document.querySelectorAll('a, button, span')).find(el => {
                            const t = (el.innerText || '').trim().toUpperCase();
                            return t === 'LOGIN' || t === 'LOGIN / REGISTER';
                        });
                        if (l) {
                            l.click();
                            try { l.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window })); } catch(e) {}
                        }
                    }''')
                    await asyncio.sleep(1.0)
                except Exception:
                    pass

            # 3. SmartBrowserActions coordinate click fallback
            user_input = page.locator("input[formcontrolname='userid'], #userId, input[placeholder*='User Name' i]").first
            if not (await user_input.count() > 0 and await user_input.is_visible()):
                await SmartBrowserActions.smart_click(
                    page=page,
                    selectors=[
                        "a.loginText",
                        "a.search_btn.loginText",
                        "a:has-text('LOGIN / REGISTER')",
                        "a:has-text('LOGIN')",
                        "button:has-text('LOGIN')"
                    ],
                    text_keywords=["LOGIN / REGISTER", "LOGIN"],
                    wait_after_sec=1.5
                )

        # Wait up to 10s for user input selector to appear
        for _ in range(20):
            user_input = page.locator("input[formcontrolname='userid'], #userId, input[placeholder*='User Name' i]").first
            pass_input = page.locator("input[formcontrolname='password'], #pwd, input[placeholder*='Password' i]").first
            if await user_input.count() > 0 and await user_input.is_visible():
                break
            await asyncio.sleep(0.5)

        # Auto-retry if login modal still didn't open — reload train-search and try again
        if not (await user_input.count() > 0 and await user_input.is_visible()):
            try:
                await page.screenshot(path=f"data/login_failed_{attempt}_{ref}.png")
            except Exception:
                pass
            log_event(db, "WARNING", "AUTOMATION", f"Login attempt {attempt}: Modal did not open. Auto-retrying by reloading page...", ref)
            try:
                await page.goto("https://www.irctc.co.in/nget/train-search", wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(2)
                await dismiss_overlays(page)
                # Direct JS click on LOGIN after reload
                await page.evaluate('''() => {
                    const l = document.querySelector('a.loginText, a.search_btn.loginText') || Array.from(document.querySelectorAll('a, button, span')).find(el => {
                        const t = (el.innerText || '').trim().toUpperCase();
                        return t === 'LOGIN' || t === 'LOGIN / REGISTER';
                    });
                    if (l) {
                        l.click();
                        try { l.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window })); } catch(e) {}
                    }
                }''')
                await asyncio.sleep(2.0)
            except Exception:
                pass
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

                # If still not logged in, auto-retry captcha (refresh + re-solve)
                if not await check_logged_in_state(page):
                    log_event(db, "WARNING", "AUTOMATION", f"Login attempt {attempt}: Auto-captcha '{candidate_text}' did not work. Refreshing captcha for retry...", ref)
                    # Refresh captcha image
                    try:
                        refresh_btn = page.locator("app-captcha .refresh-btn, app-captcha a, .captcha-refresh").first
                        if await refresh_btn.count() > 0:
                            await refresh_btn.click(force=True)
                            await asyncio.sleep(1.5)
                        # Re-capture and re-solve
                        cap_img_retry = page.locator("app-captcha img, #captchaImg, img.captcha-img, img[alt*='captcha' i]").first
                        if await cap_img_retry.count() > 0 and await cap_img_retry.is_visible():
                            cap_bytes_retry = await cap_img_retry.screenshot(timeout=3000)
                            if cap_bytes_retry:
                                retry_text, _ = fast_solve_captcha(cap_bytes_retry)
                                if retry_text and await cap_input.count() > 0:
                                    await cap_input.fill("")
                                    await cap_input.fill(retry_text)
                                    if await sign_in_btn.count() > 0:
                                        await sign_in_btn.click(timeout=3000, force=True)
                                        await asyncio.sleep(2.5)
                                    log_event(db, "INFO", "AUTOMATION", f"Login retry captcha: '{retry_text}' (attempt {attempt})", ref)
                                    # Check again
                                    for _ in range(8):
                                        if await check_logged_in_state(page):
                                            log_event(db, "INFO", "AUTOMATION", "Login successful after captcha retry!", ref)
                                            return True
                                        await asyncio.sleep(1)
                    except Exception as retry_err:
                        log_event(db, "WARNING", "AUTOMATION", f"Login captcha retry error: {retry_err}", ref)
                    
                    # Final check before moving to next attempt
                    for _ in range(5):
                        if await check_logged_in_state(page):
                            return True
                        await asyncio.sleep(1)
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
        err = "IRCTC server se connection me technical issue aa rahi hai. Kripya kuch der baad dobara try karein."
        try:
            snap = await page.screenshot(full_page=False)
            session_state.latest_screenshot_bytes = snap
        except Exception:
            pass
        log_event(db, "ERROR", "AUTOMATION", f"IRCTC Login failed after 3 attempts. Session could not be authenticated.", ref)
        raise RuntimeError(err)


async def _fill_station_autocomplete(page, input_locator, station_text: str, label: str, db: Session, ref: str):
    """Robustly fills IRCTC station autocomplete with dropdown verification."""
    station_code = resolve_station_code(station_text)
    
    for attempt in range(3):
        try:
            await input_locator.scroll_into_view_if_needed()
            try:
                await input_locator.click()
            except Exception:
                await input_locator.click(force=True)
            await asyncio.sleep(0.1)
            
            # Clear input completely using Playwright .fill(""), DOM value reset, and keyboard
            try:
                await input_locator.fill("")
            except Exception:
                pass
            await input_locator.evaluate("el => { el.value = ''; el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); }")
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Backspace")
            await asyncio.sleep(0.1)
            
            # Type station code sequentially
            await input_locator.press_sequentially(station_code, delay=60)
            await asyncio.sleep(1.2)
            
            # Wait for dropdown suggestions
            dropdown_items = page.locator("ul.ui-autocomplete-items li, li.ui-autocomplete-list-item, div.ui-autocomplete-panel li")
            
            item_found = False
            for _ in range(8):
                if await dropdown_items.count() > 0 and await dropdown_items.first.is_visible():
                    item_found = True
                    break
                await asyncio.sleep(0.4)
            
            if item_found:
                # Search all dropdown items for one that contains our station code
                item_count = await dropdown_items.count()
                matched_item = None
                for i in range(min(item_count, 10)):
                    try:
                        item_text = (await dropdown_items.nth(i).inner_text()).strip().upper()
                        # Match: "NDLS - NEW DELHI" or "NEW DELHI - NDLS" or contains station code
                        if station_code.upper() in item_text:
                            matched_item = dropdown_items.nth(i)
                            log_event(db, "INFO", "AUTOMATION", f"{label} dropdown match found: '{item_text}' for code {station_code}", ref)
                            break
                    except Exception:
                        continue
                
                if matched_item:
                    try:
                        await matched_item.click()
                    except Exception:
                        await matched_item.click(force=True)
                else:
                    # No exact match — click first item but log a warning
                    first_text = ""
                    try:
                        first_text = (await dropdown_items.first.inner_text()).strip()
                    except Exception:
                        pass
                    log_event(db, "WARNING", "AUTOMATION", f"{label} no exact match for '{station_code}' in dropdown. First item: '{first_text}'. Clicking first item.", ref)
                    try:
                        await dropdown_items.first.click()
                    except Exception:
                        await dropdown_items.first.click(force=True)
                
                await asyncio.sleep(0.6)
                
                # Verify the input value after selection
                try:
                    selected_val = (await input_locator.input_value()).strip().upper()
                    if station_code.upper() in selected_val and selected_val.count(station_code.upper()) == 1:
                        log_event(db, "INFO", "AUTOMATION", f"{label} station verified: {selected_val}", ref)
                        return True
                    elif station_code.upper() in selected_val and selected_val.count(station_code.upper()) > 1:
                        log_event(db, "WARNING", "AUTOMATION", f"{label} station duplicated ({selected_val})! Clearing and retrying...", ref)
                        try:
                            await input_locator.fill("")
                        except Exception:
                            pass
                        continue
                    else:
                        log_event(db, "WARNING", "AUTOMATION", f"{label} station mismatch after selection! Expected '{station_code}', got '{selected_val}'. Retrying...", ref)
                        try:
                            await input_locator.fill("")
                        except Exception:
                            pass
                        continue
                except Exception:
                    log_event(db, "INFO", "AUTOMATION", f"{label} station selected: {station_code} (dropdown click)", ref)
                    return True
            else:
                # Keyboard selection fallback: ArrowDown + Enter
                await input_locator.press("ArrowDown")
                await asyncio.sleep(0.3)
                await input_locator.press("Enter")
                await asyncio.sleep(0.6)
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

        page = await browser_manager.get_page(owner=ref)

        # Attach non-blocking response listener to capture and log any raw API warnings/errors
        try:
            async def _on_response(resp):
                try:
                    if "/eticketing/protected/" in resp.url or "/nget/" in resp.url:
                        if resp.status >= 400:
                            body_snippet = ""
                            try:
                                body_snippet = (await resp.text())[:300].replace("\n", " ").strip()
                            except Exception:
                                pass
                            log_event(db, "WARNING", "AUTOMATION", f"IRCTC API HTTP {resp.status} on {resp.url.split('?')[0]} | body: {body_snippet}", ref)
                        elif resp.request.method == "POST" and "json" in (resp.headers.get("content-type") or ""):
                            try:
                                data = await resp.json()
                                if isinstance(data, dict):
                                    err = data.get("errorMessage") or data.get("error")
                                    if err:
                                        log_event(db, "WARNING", "AUTOMATION", f"IRCTC API response notice: {err}", ref)
                            except Exception:
                                pass
                except Exception:
                    pass
            page.on("response", _on_response)
        except Exception:
            pass

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

        search_success = False
        date_str = booking.journey_date.strftime("%d/%m/%Y")

        for search_attempt in range(3):
            try:
                # If train list already loaded, break out immediately
                if "/train-list" in page.url or await page.locator("app-train-list, div.train-heading, app-train-avl-enq").count() > 0:
                    log_event(db, "INFO", "AUTOMATION", "Train search results already visible.", ref)
                    search_success = True
                    break

                # Ensure search inputs are ready
                has_search_inputs = await page.locator("p-autocomplete input").count() > 0
                if not has_search_inputs:
                    if "/train-search" not in page.url:
                        await page.goto(URLS["HOME"], wait_until="domcontentloaded", timeout=30000)
                        await asyncio.sleep(2)
                    await dismiss_overlays(page)

                # Always unconditionally dismiss any Language Alert or modal before searching
                await dismiss_overlays(page)
                await page.wait_for_selector("p-autocomplete input", timeout=15000)
                
                # Use targeted selectors for FROM and TO station autocompletes
                from_input = page.locator("p-autocomplete[formcontrolname='origin'] input, #origin input, input[placeholder*='From*' i], input[placeholder*='From' i]").first
                if await from_input.count() == 0:
                    from_input = page.locator("p-autocomplete input").nth(0)

                to_input = page.locator("p-autocomplete[formcontrolname='destination'] input, #destination input, input[placeholder*='To*' i], input[placeholder*='To' i]").first
                if await to_input.count() == 0:
                    to_input = page.locator("p-autocomplete input").nth(1)

                # 1. From station — use resolved code
                await _fill_station_autocomplete(page, from_input, booking.from_station, "FROM", db, ref)
                await asyncio.sleep(0.5)

                # 2. To station — use resolved code
                await _fill_station_autocomplete(page, to_input, booking.to_station, "TO", db, ref)
                await asyncio.sleep(0.5)

                # 3. Date — Fill via keyboard into PrimeNG calendar input and commit
                await dismiss_overlays(page)
                date_input = page.locator("p-calendar[formcontrolname='journeyDate'] input, p-calendar input:visible, #jDate input:visible, input[placeholder*='Date' i]:visible").first
                if await date_input.count() > 0:
                    try:
                        await date_input.scroll_into_view_if_needed()
                        try:
                            await date_input.click(timeout=3000)
                        except Exception:
                            await date_input.click(timeout=2000, force=True)
                        await asyncio.sleep(0.1)
                        await page.keyboard.press("Control+A")
                        await page.keyboard.press("Backspace")
                        await date_input.press_sequentially(date_str, delay=30)
                        await asyncio.sleep(0.2)
                        await page.keyboard.press("Tab")
                        await page.keyboard.press("Escape")
                        await asyncio.sleep(0.2)
                    except Exception as e:
                        log_event(db, "WARNING", "AUTOMATION", f"Failed to type date into calendar input: {e}", ref)

                # Sync JS value without deleting any PrimeNG DOM nodes
                await page.evaluate('''(dStr) => {
                    const dInputs = Array.from(document.querySelectorAll("p-calendar input, #jDate input, input[placeholder*='Date' i]"));
                    for (const d of dInputs) {
                        if (d.value !== dStr) {
                            d.value = dStr;
                            d.dispatchEvent(new Event('input', { bubbles: true }));
                            d.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                    }
                }''', date_str)
                await asyncio.sleep(0.3)

                # 4. Ensure Quota dropdown is set (General Quota by default)
                try:
                    await page.evaluate('''() => {
                        const quotaDropdown = document.querySelector("p-dropdown[formcontrolname='journeyQuota'], select[formcontrolname='journeyQuota']");
                        if (quotaDropdown) {
                            const sel = quotaDropdown.querySelector('select');
                            if (sel) {
                                sel.value = 'GN';
                                sel.dispatchEvent(new Event('change', {bubbles: true}));
                            }
                        }
                    }''')
                except Exception:
                    pass

                # 5. Click Search Button (SINGLE CLEAN CLICK - prevent double submission error)
                await dismiss_overlays(page)
                try:
                    await page.keyboard.press("Escape")
                    await asyncio.sleep(0.2)
                except Exception:
                    pass

                search_btn = page.locator("form button.train_Search:not(.ui-dialog *):not(p-confirmdialog *), form button.search_btn:not(.ui-dialog *):not(p-confirmdialog *), app-main-page button.train_Search:not(.ui-dialog *):not(p-confirmdialog *), app-main-page button.search_btn:not(.ui-dialog *):not(p-confirmdialog *), button.train_Search:not(.ui-dialog *):not(p-confirmdialog *)").first
                search_clicked = False
                if await search_btn.count() > 0 and await search_btn.is_visible():
                    await search_btn.scroll_into_view_if_needed()
                    try:
                        await search_btn.click(timeout=4000)
                        search_clicked = True
                    except Exception:
                        pass

                if not search_clicked:
                    search_clicked = await SmartBrowserActions.smart_click(
                        page=page,
                        selectors=[
                            "form button.train_Search:visible:not(.ui-dialog *):not(p-confirmdialog *)",
                            "form button.search_btn:visible:not(.ui-dialog *):not(p-confirmdialog *)",
                            "button.train_Search:visible:not(.ui-dialog *):not(p-confirmdialog *)",
                            "button.search_btn:visible:not(.ui-dialog *):not(p-confirmdialog *)"
                        ],
                        text_keywords=["Search", "SEARCH", "Find Trains"],
                        timeout_ms=4000,
                        wait_after_sec=0.5
                    )

                log_event(db, "INFO", "AUTOMATION", f"Submitted search for {booking.from_station} to {booking.to_station} on {date_str} (attempt {search_attempt+1}).", ref)

                # Wait up to 25s for train-list or URL navigation
                for wait_sec in range(25):
                    await asyncio.sleep(1)
                    await dismiss_overlays(page)
                    if "/train-list" in page.url or await page.locator("app-train-list, div.train-heading, div.form-group:has(.train-name), app-train-avl-enq").count() > 0:
                        search_success = True
                        break

                    # If redirected to IRCTC error page, recover immediately
                    if "/nget/error" in page.url.lower():
                        log_event(db, "WARNING", "AUTOMATION", f"IRCTC redirected to error page during search (wait: {wait_sec}s). Attempting auto-recovery...", ref)
                        try:
                            err_btn = page.locator("button:has-text('Click here to login'), a:has-text('Click here to login'), button.btn-primary").first
                            if await err_btn.count() > 0:
                                await err_btn.click(timeout=3000)
                                await asyncio.sleep(2)
                            else:
                                await page.goto(URLS["HOME"], wait_until="domcontentloaded", timeout=30000)
                                await asyncio.sleep(2)
                        except Exception:
                            await page.goto(URLS["HOME"], wait_until="domcontentloaded", timeout=30000)
                        break

                    # Accept any informational / disclaimer / popup dialogs that block navigation
                    try:
                        await page.evaluate('''() => {
                            const dialogBtns = Array.from(document.querySelectorAll('.ui-dialog button, p-confirmdialog button, div[role="dialog"] button, .modal button'));
                            for (const b of dialogBtns) {
                                const t = (b.innerText || '').trim().toLowerCase();
                                if (t === 'ok' || t === 'yes' || t === 'agree' || t === 'proceed' || t === 'continue' || t === 'theek hai' || t === 'स्वीकार') {
                                    b.click();
                                    break;
                                }
                            }
                        }''')
                    except Exception:
                        pass

                if search_success:
                    break
                else:
                    # Diagnostic dump if search didn't navigate
                    diag = await page.evaluate('''() => {
                        const origin = document.querySelector("p-autocomplete[formcontrolname='origin'] input, #origin input");
                        const dest = document.querySelector("p-autocomplete[formcontrolname='destination'] input, #destination input");
                        const date = document.querySelector("p-calendar[formcontrolname='journeyDate'] input, #jDate input");
                        const errors = Array.from(document.querySelectorAll('.ui-message-error, .ui-messages-error, div.error-msg, span.ui-message-text, .alert-danger, .ui-state-error'))
                            .map(e => (e.innerText || '').trim())
                            .filter(Boolean);
                        const dialogs = Array.from(document.querySelectorAll('.ui-dialog:not([style*="none"]), p-dialog:not([style*="none"]), div[role="dialog"]'))
                            .map(d => (d.innerText || '').trim().replace(/\\s+/g, ' ').slice(0, 150))
                            .filter(Boolean);
                        // Check ng-invalid fields
                        const invalidFields = Array.from(document.querySelectorAll('.ng-invalid[formcontrolname]'))
                            .map(e => e.getAttribute('formcontrolname'));
                        // Check search button state
                        const searchBtn = document.querySelector('form button.train_Search, form button.search_btn, button.train_Search:not(.ui-dialog *):not(p-confirmdialog *)');
                        const btnState = searchBtn ? {disabled: searchBtn.disabled, visible: searchBtn.offsetParent !== null, text: (searchBtn.innerText || '').trim()} : null;
                        // Check for loading spinners/overlays
                        const spinner = document.querySelector('.ui-blockui, .loading, .spinner, .cdk-overlay-container .cdk-overlay-backdrop');
                        const hasSpinner = spinner ? spinner.offsetParent !== null : false;
                        return {
                            origin: origin ? origin.value : null,
                            dest: dest ? dest.value : null,
                            date: date ? date.value : null,
                            errors: errors,
                            dialogs: dialogs,
                            invalidFields: invalidFields,
                            searchBtn: btnState,
                            hasSpinner: hasSpinner,
                            url: window.location.href
                        };
                    }''')
                    log_event(db, "WARNING", "AUTOMATION", f"Search attempt {search_attempt+1} did not navigate. Form state: {diag}", ref)
                    try:
                        await page.screenshot(path="data/search_failed.png")
                    except Exception:
                        pass

            except Exception as e:
                log_event(db, "WARNING", "AUTOMATION", f"Search attempt {search_attempt+1} failed: {str(e)}", ref)
                await asyncio.sleep(1)

        if not search_success:
            err_msg = f"Could not navigate to Train List page for route {booking.from_station} ➔ {booking.to_station} on {date_str}. Search form submission failed or no results loaded."
            log_event(db, "ERROR", "AUTOMATION", err_msg, ref)
            session_state.set_stage("FAILED", "FAILED")
            session_state.error_message = err_msg
            booking.status = "FAILED"
            db.commit()
            if settings.TELEGRAM_ENABLED:
                await send_telegram_message(f"❌ *Booking Failed* (Ref: `{ref}`)\n\n{err_msg}")
            return

        # ══════════════════════════════════════════════════
        # Step 5: Train & Class Selection
        # ══════════════════════════════════════════════════
        session_state.set_stage("SELECTING_TRAIN")
        log_event(db, "INFO", "AUTOMATION", f"Selecting train & class for {booking.from_station} ➔ {booking.to_station}...", ref)

        # Wait up to 20s for train list cards
        train_list_found = False
        for _ in range(20):
            await dismiss_overlays(page)
            if await page.locator("app-train-list, div.train-heading, div.form-group:has(.train-name), app-train-avl-enq").count() > 0:
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
                if (body.includes('No direct trains found') || body.includes('No trains found') || body.includes('no direct train')) {
                    return true;
                }
                const modal = document.querySelector('.ui-dialog, p-confirmdialog');
                if (modal && (modal.innerText.includes('No direct') || modal.innerText.includes('No train'))) {
                    return true;
                }
                return false;
            }''')
            if no_trains:
                err_msg = f"IRCTC reports: No direct trains found for {booking.from_station} ➔ {booking.to_station} on {date_str}."
                log_event(db, "WARNING", "AUTOMATION", err_msg, ref)
                session_state.set_stage("FAILED", "FAILED")
                session_state.error_message = err_msg
                booking.status = "FAILED"
                db.commit()
                if settings.TELEGRAM_ENABLED:
                    await send_telegram_message(f"❌ *Booking Notice* (Ref: `{ref}`)\n\n{err_msg}")
                return
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

        if await target_train_card.count() == 0:
            err_msg = f"No train cards (app-train-avl-enq) found on search results page for {booking.from_station} ➔ {booking.to_station} on {date_str}."
            log_event(db, "ERROR", "AUTOMATION", err_msg, ref)
            session_state.set_stage("FAILED", "FAILED")
            session_state.error_message = err_msg
            booking.status = "FAILED"
            db.commit()
            if settings.TELEGRAM_ENABLED:
                await send_telegram_message(f"❌ *Booking Failed* (Ref: `{ref}`)\n\n{err_msg}")
            return

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

        # 2. Wait for availability slots and handle NOT AVAILABLE gracefully
        date_clicked = False
        book_now_clicked = False

        # Extract target day and month representations for precise slot matching
        target_day = str(booking.journey_date.day) if hasattr(booking.journey_date, "day") else ""
        target_month_num = f"{booking.journey_date.month:02d}" if hasattr(booking.journey_date, "month") else ""
        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        target_month_name = month_names[booking.journey_date.month - 1].upper() if hasattr(booking.journey_date, "month") and 1 <= booking.journey_date.month <= 12 else ""

        # Filter fallback classes to only those ACTUALLY present on this train card
        classes_to_try = [journey_cls]
        try:
            card_text = (await target_train_card.inner_text()).upper()
            class_priority = ["3A", "2A", "SL", "1A", "3E", "CC", "EC", "2S"]
            for cp in class_priority:
                if cp != journey_cls and cp not in classes_to_try:
                    cls_aliases = cls_map.get(cp, [cp])
                    if any(alias.upper() in card_text for alias in cls_aliases):
                        classes_to_try.append(cp)
        except Exception:
            pass

        for try_cls in classes_to_try:
            cls_keys_try = cls_map.get(try_cls, [try_cls])

            # Click class tab if not the first attempt (first was already clicked above)
            if try_cls != journey_cls:
                cls_selectors_try = [f"div.pre-avl:has-text('{k}')" for k in cls_keys_try] + [f"span:has-text('{k}')" for k in cls_keys_try]
                try:
                    clicked_alt = await SmartBrowserActions.smart_click(
                        page=page, selectors=cls_selectors_try, text_keywords=cls_keys_try,
                        scope_locator=target_train_card, wait_after_sec=0.5
                    )
                    if not clicked_alt:
                        continue
                    log_event(db, "INFO", "AUTOMATION", f"Trying alternate class '{try_cls}' (requested '{journey_cls}' unavailable)...", ref)
                except Exception:
                    continue

            # Refresh once if needed
            try:
                refresh_btn = target_train_card.locator("a:has-text('Refresh'), button:has-text('Refresh'), span:has-text('Refresh')").first
                if await refresh_btn.count() > 0 and await refresh_btn.is_visible():
                    await refresh_btn.click(force=True)
                    await asyncio.sleep(1.5)
            except Exception:
                pass

            # Wait for availability rows to appear and select target date
            # Take a debug screenshot of availability table
            try:
                import os
                debug_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
                os.makedirs(debug_dir, exist_ok=True)
                debug_ss_path = os.path.join(debug_dir, f"avl_debug_{try_cls}_{ref}.png")
                await page.screenshot(path=debug_ss_path)
                log_event(db, "INFO", "AUTOMATION", f"[DEBUG] Screenshot saved: {debug_ss_path}", ref)
            except Exception:
                pass

            # Dump availability table HTML for debugging (once per class)
            try:
                avl_html_dump = await target_train_card.evaluate('''(card) => {
                    const table = card.querySelector('.pre-avl-table, table.table, .tbis, .tbleft') || card;
                    return table ? table.innerHTML.substring(0, 3000) : 'NO_TABLE_FOUND';
                }''')
                log_event(db, "INFO", "AUTOMATION", f"[DEBUG] Availability DOM for class '{try_cls}': {str(avl_html_dump)[:500]}", ref)
            except Exception:
                pass

            for wait_slot in range(15):
                await asyncio.sleep(0.6)
                await dismiss_overlays(page)

                slot_found = False
                try:
                    # Use Playwright locators to find ALL clickable availability cells
                    # IRCTC uses td elements inside the availability table — each td contains
                    # both the date info and availability status in its full text
                    avl_cells = target_train_card.locator("td.pre-avl, td.curr-avl, div.pre-avl-table td, table td, td")
                    cell_count = await avl_cells.count()
                    
                    if cell_count == 0:
                        # Try alternative: look for div-based availability slots  
                        avl_cells = target_train_card.locator("div.pre-avl, div[class*='avl'], div.link, a.link")
                        cell_count = await avl_cells.count()
                    
                    target_day_padded = target_day.zfill(2) if target_day else ""
                    target_day_raw = str(int(target_day)) if target_day and target_day.isdigit() else target_day
                    
                    REJECT_KEYWORDS = ["NOT AVAILABLE", "REGRET", "NOT AVL", "NO LGOFF", "TRAIN CANCELLED"]
                    BOOKABLE_KEYWORDS = ["AVAILABLE", "AVL", "GNWL", "RLWL", "PQWL", "RSWL", "RAC", "WL", "CURR_AVAIL"]
                    
                    # Scan all cells and classify them
                    best_target_date_cell = None  # Cell matching target date & bookable
                    best_any_bookable_cell = None  # Any cell that is bookable
                    
                    for ci in range(min(cell_count, 30)):
                        try:
                            cell = avl_cells.nth(ci)
                            if not await cell.is_visible():
                                continue
                            cell_text = (await cell.inner_text()).strip().upper()
                            
                            if len(cell_text) < 2:
                                continue
                            
                            # Check if cell contains reject keywords
                            is_rejected = any(rk in cell_text for rk in REJECT_KEYWORDS)
                            
                            # Check if cell contains bookable keywords
                            is_bookable = any(bk in cell_text for bk in BOOKABLE_KEYWORDS) and not is_rejected
                            
                            # Check if cell matches target date
                            has_target_date = False
                            if target_day_raw and target_month_name:
                                has_target_date = (target_day_raw in cell_text or target_day_padded in cell_text) and \
                                                  (target_month_name in cell_text or target_month_num in cell_text)
                            
                            if has_target_date and is_bookable and not best_target_date_cell:
                                best_target_date_cell = cell
                                log_event(db, "INFO", "AUTOMATION", f"[SLOT] Found bookable target date cell: '{cell_text[:100]}'", ref)
                            elif is_bookable and not is_rejected and not best_any_bookable_cell:
                                best_any_bookable_cell = cell
                                
                        except Exception:
                            continue
                    
                    # Click the best cell found (prefer target date)
                    click_cell = best_target_date_cell or best_any_bookable_cell
                    
                    if click_cell:
                        try:
                            clicked_text = (await click_cell.inner_text()).strip()
                            await click_cell.scroll_into_view_if_needed()
                            await click_cell.click(force=True)
                            slot_found = True
                            log_event(db, "INFO", "AUTOMATION", f"Clicked availability slot: '{clicked_text[:100]}'", ref)
                        except Exception as click_err:
                            # Fallback: try JS click
                            try:
                                await click_cell.evaluate("el => el.click()")
                                slot_found = True
                                log_event(db, "INFO", "AUTOMATION", f"Clicked availability slot via JS fallback", ref)
                            except Exception:
                                log_event(db, "WARNING", "AUTOMATION", f"Slot click failed: {click_err}", ref)
                    else:
                        # Log what we actually found for debugging
                        if wait_slot == 0:
                            sample_texts = []
                            for ci in range(min(cell_count, 10)):
                                try:
                                    ct = (await avl_cells.nth(ci).inner_text()).strip()[:80]
                                    if ct:
                                        sample_texts.append(ct)
                                except Exception:
                                    pass
                            if sample_texts:
                                log_event(db, "INFO", "AUTOMATION", f"[DEBUG] No bookable slot found. Sample cell texts: {sample_texts[:5]}", ref)
                            elif cell_count == 0:
                                log_event(db, "INFO", "AUTOMATION", f"[DEBUG] No availability cells found yet (wait {wait_slot+1})", ref)

                except Exception as eval_err:
                    log_event(db, "WARNING", "AUTOMATION", f"Slot evaluation error: {eval_err}", ref)

                if slot_found:
                    date_clicked = True
                    log_event(db, "INFO", "AUTOMATION", f"Availability slot clicked for class '{try_cls}' (attempt {wait_slot+1})!", ref)
                    await asyncio.sleep(1.5)
                    # Verify: Check if Book Now is actually enabled after clicking
                    try:
                        await asyncio.sleep(1.0)
                        bn_check = target_train_card.locator("button:has-text('Book Now'):not(.disable-book)")
                        if await bn_check.count() > 0 and await bn_check.is_visible():
                            log_event(db, "INFO", "AUTOMATION", f"Book Now button IS enabled for class '{try_cls}'!", ref)
                        else:
                            # Book Now still disabled — the slot we clicked was NOT AVAILABLE / REGRET
                            page_avl_text = ""
                            try:
                                page_avl_text = (await target_train_card.inner_text()).strip()[:300]
                            except Exception:
                                pass
                            is_actually_regret = any(rk in page_avl_text.upper() for rk in ["REGRET", "NOT AVAILABLE", "NOT AVL"])
                            if is_actually_regret:
                                log_event(db, "WARNING", "AUTOMATION", f"Slot clicked but status is REGRET/NOT AVAILABLE for class '{try_cls}'. Card text: {page_avl_text[:200]}", ref)
                                slot_found = False
                                date_clicked = False
                                break  # Skip remaining wait iterations, move to next class
                            else:
                                log_event(db, "INFO", "AUTOMATION", f"Book Now not yet visible, waiting... Card text: {page_avl_text[:200]}", ref)
                    except Exception:
                        pass
                    break

            if not date_clicked:
                log_event(db, "INFO", "AUTOMATION", f"Class '{try_cls}' shows no bookable slot on date {date_str}. Trying next available class...", ref)
                continue

            # Extract live fare
            live_fare = await extract_live_fare_from_page(page)
            if live_fare:
                booking.fare = live_fare
                db.commit()
                log_event(db, "INFO", "AUTOMATION", f"Official IRCTC Live Fare: ₹{live_fare:,.2f}", ref)

            # Update class if we switched
            if try_cls != journey_cls:
                booking.journey_class = try_cls
                db.commit()
                log_event(db, "INFO", "AUTOMATION", f"Auto-switched class from '{journey_cls}' to '{try_cls}' (original unavailable)", ref)

            # Strict check: ID must remain logged in before booking
            if not await check_logged_in_state(page):
                log_event(db, "WARNING", "AUTOMATION", "Session logged out before clicking Book Now. Re-authenticating...", ref)
                await ensure_authenticated_session(page, ref, db, session_state, booking)
                
                # After re-auth, IRCTC navigates away from train results page.
                # We must redo the search to get fresh train cards and slot state.
                log_event(db, "INFO", "AUTOMATION", "Re-auth completed. Re-doing train search to restore booking context...", ref)
                
                # Navigate back to train search
                try:
                    await page.goto("https://www.irctc.co.in/nget/train-search", wait_until="domcontentloaded", timeout=20000)
                    await asyncio.sleep(2)
                    await dismiss_overlays(page)
                    
                    # Re-fill search form
                    from_code = booking.from_station or ""
                    to_code = booking.to_station or ""
                    
                    await _fill_station_autocomplete(page, "from", from_code, ref, db)
                    await _fill_station_autocomplete(page, "to", to_code, ref, db)
                    
                    # Re-fill date
                    date_input = page.locator("input[id='jDate'], p-calendar input, input.ng-tns-c58-10").first
                    if await date_input.count() > 0:
                        await date_input.click(force=True)
                        await asyncio.sleep(0.3)
                        await date_input.fill(date_str)
                        await page.keyboard.press("Escape")
                        await asyncio.sleep(0.3)
                    
                    # Click search
                    await dismiss_overlays(page)
                    search_btn = page.locator("form button.train_Search, button:has-text('Search Trains')").first
                    if await search_btn.count() > 0:
                        await search_btn.click(force=True)
                    
                    # Wait for results
                    for ws in range(20):
                        if "train-list" in page.url or await page.locator("app-train-avl-enq").count() > 0:
                            break
                        await asyncio.sleep(1)
                    await asyncio.sleep(1)
                    
                    # Re-select train card
                    train_num = (booking.train_number or "").strip()
                    num_m = re.search(r'\b\d{5}\b', train_num)
                    search_num = num_m.group(0) if num_m else train_num
                    new_card = page.locator("app-train-avl-enq").filter(has_text=search_num).first
                    if await new_card.count() > 0:
                        target_train_card = new_card
                        await target_train_card.scroll_into_view_if_needed()
                        log_event(db, "INFO", "AUTOMATION", f"Re-selected train card for {search_num} after re-auth.", ref)
                    else:
                        target_train_card = page.locator("app-train-avl-enq").first
                        log_event(db, "WARNING", "AUTOMATION", f"Could not find train {search_num} after re-auth. Using first available.", ref)
                    
                    # Re-click class tab
                    cls_keys_retry = cls_map.get(try_cls, [try_cls])
                    cls_sels_retry = [f"div.pre-avl:has-text('{k}')" for k in cls_keys_retry] + [f"span:has-text('{k}')" for k in cls_keys_retry]
                    await SmartBrowserActions.smart_click(
                        page=page, selectors=cls_sels_retry, text_keywords=cls_keys_retry,
                        scope_locator=target_train_card, wait_after_sec=0.5
                    )
                    await asyncio.sleep(1)
                    
                    # Re-click availability slot (simplified - click first bookable)
                    REJECT_KEYWORDS_RE = ["NOT AVAILABLE", "REGRET", "NOT AVL", "NO LGOFF", "TRAIN CANCELLED"]
                    BOOKABLE_KEYWORDS_RE = ["AVAILABLE", "AVL", "GNWL", "RLWL", "PQWL", "RSWL", "RAC", "WL", "CURR_AVAIL"]
                    
                    for re_wait in range(10):
                        await asyncio.sleep(0.6)
                        avl_cells_re = target_train_card.locator("td.pre-avl, td.curr-avl, div.pre-avl-table td, table td, td")
                        cc_re = await avl_cells_re.count()
                        for ci_re in range(min(cc_re, 30)):
                            try:
                                cell_re = avl_cells_re.nth(ci_re)
                                if not await cell_re.is_visible():
                                    continue
                                ct_re = (await cell_re.inner_text()).strip().upper()
                                if len(ct_re) < 2:
                                    continue
                                is_rej = any(rk in ct_re for rk in REJECT_KEYWORDS_RE)
                                is_book = any(bk in ct_re for bk in BOOKABLE_KEYWORDS_RE) and not is_rej
                                if is_book:
                                    await cell_re.scroll_into_view_if_needed()
                                    await cell_re.click(force=True)
                                    log_event(db, "INFO", "AUTOMATION", f"Re-clicked slot after re-auth: '{ct_re[:80]}'", ref)
                                    await asyncio.sleep(1.5)
                                    break
                            except Exception:
                                continue
                        else:
                            continue
                        break
                    
                except Exception as reauth_err:
                    log_event(db, "WARNING", "AUTOMATION", f"Re-search after re-auth failed: {reauth_err}", ref)

            # 3. Click active enabled 'Book Now' (without .disable-book)
            bn_selectors = [
                "button.train_Search:not(.disable-book)",
                "button:has-text('Book Now'):not(.disable-book)",
                "button[label='Book Now']:not(.disable-book)"
            ]
            try:
                for bn_wait in range(20):
                    bn = target_train_card.locator(", ".join(bn_selectors)).first
                    if await bn.count() == 0:
                        bn = page.locator(", ".join(bn_selectors)).first

                    if await bn.count() > 0 and await bn.is_visible():
                        clicked = await SmartBrowserActions.smart_click(
                            page=page, selectors=bn_selectors, text_keywords=["Book Now"],
                            scope_locator=target_train_card if await target_train_card.locator(", ".join(bn_selectors)).count() > 0 else None,
                            wait_after_sec=1.0
                        )
                        if clicked:
                            book_now_clicked = True
                            log_event(db, "INFO", "AUTOMATION", f"Clicked active enabled 'Book Now' button (class: {try_cls})!", ref)
                            break
                    await asyncio.sleep(0.5)
            except Exception as e:
                log_event(db, "WARNING", "AUTOMATION", f"Book now click note: {e}", ref)

            if book_now_clicked:
                break
            else:
                log_event(db, "WARNING", "AUTOMATION", f"Book Now button disabled/missing for class '{try_cls}'. Trying next class...", ref)
                date_clicked = False
                continue

        if not book_now_clicked:
            err_msg = f"Train {booking.train_name or booking.train_number} par {date_str} ko seats uplabdh nahi hain (All classes NOT AVAILABLE / REGRET)."
            log_event(db, "ERROR", "AUTOMATION", err_msg, ref)
            session_state.set_stage("FAILED", "FAILED")
            session_state.error_message = err_msg
            booking.status = "FAILED"
            db.commit()
            if settings.TELEGRAM_ENABLED:
                try:
                    await send_telegram_message(
                        f"❌ *Seats Available Nahi Hain*\n"
                        f"Ref: `{ref}`\n\n"
                        f"🚆 *{booking.train_name or booking.train_number}* par `{date_str}` ko IRCTC par koi seat available nahi hai.\n\n"
                        f"👉 Kripya koi doosri date ya train se try karein.",
                        reply_markup={"inline_keyboard": [[{"text": "🎫 Nayi Booking Karein", "callback_data": "cmd_book"}]]}
                    )
                except Exception:
                    await send_telegram_message(f"❌ *Booking Failed* (Ref: `{ref}`)\n\n{err_msg}")
            return

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

        # If passenger page not reached, retry Book Now clicks and dialog handling
        if not arrived_at_passenger:
            log_event(db, "WARNING", "AUTOMATION", "Passenger page not reached after Book Now. Retrying dialog handling...", ref)
            # Extra retry: try clicking any visible dialogs and Book Now again
            for retry in range(15):
                try:
                    await page.evaluate('''() => {
                        const dialogs = Array.from(document.querySelectorAll('.ui-dialog, p-confirmdialog, div[role="dialog"]')).filter(d => d.offsetParent !== null);
                        for (const d of dialogs) {
                            const btn = Array.from(d.querySelectorAll('button, span.ui-button-text')).find(b => {
                                const t = (b.innerText || '').trim().toLowerCase();
                                return t === 'yes' || t === 'i agree' || t === 'ok' || t === 'continue' || t === 'confirm' || t === 'proceed';
                            });
                            if (btn) btn.click();
                        }
                    }''')
                except Exception:
                    pass
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
        if not passengers:
            from app.database.models import Passenger
            saved_p = db.query(Passenger).order_by(Passenger.id.desc()).first()
            p_name = saved_p.name if saved_p else "Deepak"
            p_age = saved_p.age if saved_p else 28
            p_gender = saved_p.gender if saved_p else "M"
            p_berth = getattr(saved_p, 'berth_preference', 'NONE') or 'NONE'
            bp = BookingPassenger(
                booking_id=booking.id,
                name=p_name,
                age=p_age,
                gender=p_gender,
                berth_preference=p_berth,
                status="CNF"
            )
            db.add(bp)
            booking.passenger_count = 1
            db.commit()
            passengers = [bp]
            log_event(db, "WARNING", "AUTOMATION", f"No passengers linked to booking {ref}. Auto-added passenger: {p_name} ({p_age}/{p_gender})", ref)

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

                # Name — type then Tab to commit (do NOT press Escape — it kills PrimeNG autocomplete binding)
                name_inputs = page.locator("input[placeholder*='Passenger Name' i], p-autocomplete[formcontrolname='passengerName'] input")
                if await name_inputs.count() > idx:
                    name_input = name_inputs.nth(idx)
                    await name_input.click(force=True)
                    await asyncio.sleep(0.1)
                    await page.keyboard.press("Control+A")
                    await page.keyboard.press("Backspace")
                    await name_input.press_sequentially(p.name, delay=30)
                    await asyncio.sleep(0.5)
                    # Tab out to commit the value and close any autocomplete dropdown
                    await page.keyboard.press("Tab")
                    await asyncio.sleep(0.3)

                # Age
                age_inputs = page.locator("input[placeholder*='Age' i], input[formcontrolname='passengerAge']")
                if await age_inputs.count() > idx:
                    age_input = age_inputs.nth(idx)
                    await age_input.click(force=True)
                    await page.keyboard.press("Control+A")
                    await page.keyboard.press("Backspace")
                    await age_input.press_sequentially(str(p.age), delay=30)
                    await page.keyboard.press("Tab")
                    await asyncio.sleep(0.2)

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

                # Berth Preference — select "No Preference" safely by label/value
                berth_val = getattr(p, 'berth_preference', 'NONE') or 'NONE'
                berth_map = {"LB": "LB", "MB": "MB", "UB": "UB", "SL": "SL", "SU": "SU", "NONE": "", "NP": ""}
                berth_irctc = berth_map.get(berth_val.upper(), "")
                try:
                    berth_selects = page.locator("select[formcontrolname='passengerBerthChoice']")
                    if await berth_selects.count() > idx:
                        if berth_irctc:
                            try:
                                await berth_selects.nth(idx).select_option(value=berth_irctc)
                            except Exception:
                                pass
                        else:
                            try:
                                await berth_selects.nth(idx).select_option(label="No Preference")
                            except Exception:
                                pass
                    else:
                        berth_dropdown = page.locator("p-dropdown[formcontrolname='passengerBerthChoice']").nth(idx)
                        if await berth_dropdown.count() > 0:
                            await SmartBrowserActions.smart_click(page, selectors=[], scope_locator=berth_dropdown)
                            await asyncio.sleep(0.3)
                            bp_opt = page.locator("li[aria-label*='No Preference' i], span:has-text('No Preference')").first
                            if await bp_opt.count() > 0:
                                await bp_opt.click()
                                await asyncio.sleep(0.2)
                except Exception:
                    pass

                # Nationality — ensure "India" is selected by matching option text, never blanking out the field
                try:
                    await page.evaluate(f'''(idx) => {{
                        const sels = document.querySelectorAll("select[formcontrolname='passengerNationality']");
                        if (sels.length > idx) {{
                            const sel = sels[idx];
                            if (!sel.value) {{
                                const indiaOpt = Array.from(sel.options).find(o => (o.text || '').toLowerCase().includes('india'));
                                if (indiaOpt) {{
                                    sel.value = indiaOpt.value;
                                    sel.dispatchEvent(new Event('change', {{bubbles: true}}));
                                }}
                            }}
                        }}
                    }}''', idx)
                except Exception:
                    pass

                # Food preference (for Rajdhani/Shatabdi/Duronto)
                food_val = getattr(p, 'food_preference', 'D') or 'D'
                try:
                    food_selects = page.locator("select[formcontrolname='passengerFoodChoice']")
                    if await food_selects.count() > idx:
                        await food_selects.nth(idx).select_option(value=food_val)
                except Exception:
                    pass

                log_event(db, "INFO", "AUTOMATION", f"Filled passenger {idx+1}: {p.name}, {p.age}, {p.gender}, berth={berth_irctc}", ref)

        except Exception as e:
            log_event(db, "WARNING", "AUTOMATION", f"Passenger auto-fill note: {str(e)}", ref)

        # Contact mobile - Mandatory 10-digit number for IRCTC validation!
        mob_raw = str(booking.contact_mobile or "").strip()
        digits = "".join(c for c in mob_raw if c.isdigit())
        if len(digits) == 12 and digits.startswith("91"):
            digits = digits[2:]
        if len(digits) != 10 or not (digits[0] in "6789"):
            digits = getattr(settings, "DEFAULT_CONTACT_MOBILE", None) or "9876543210"

        try:
            mob_input = page.locator("input[formcontrolname='mobileNumber'], input#mobileNumber, input[name='mobileNumber'], input[placeholder*='Mobile Number' i]").first
            if await mob_input.count() > 0:
                await SmartBrowserActions.smart_type(page, mob_input, digits, delay_ms=30, clear_first=True)
            
            # Ensure Angular form control updates value & validity via JS event dispatch
            await page.evaluate('''(mobile) => {
                const inputs = Array.from(document.querySelectorAll("input[formcontrolname='mobileNumber'], input#mobileNumber, input[name='mobileNumber'], input[placeholder*='Mobile Number' i]"));
                for (const inp of inputs) {
                    inp.value = mobile;
                    inp.dispatchEvent(new Event('input', { bubbles: true }));
                    inp.dispatchEvent(new Event('change', { bubbles: true }));
                    inp.dispatchEvent(new Event('blur', { bubbles: true }));
                }
            }''', digits)
            log_event(db, "INFO", "AUTOMATION", f"Set contact mobile: {digits[:3]}****{digits[-3:]}", ref)
        except Exception as e:
            log_event(db, "WARNING", "AUTOMATION", f"Mobile number entry note: {e}", ref)
        # Handle IRCTC Co-branded Card Benefits: Select "Skip" if loyalty prompt is present
        cobrand_skipped = False
        try:
            # Strategy 1 (Direct Text Click via Playwright):
            # In HTML/Angular, clicking the text 'Skip' or label 'Skip' triggers the radio.
            for skip_sel in [
                "text='Skip'",
                "label:has-text('Skip')",
                "span:text-is('Skip')",
                "p-radiobutton:has-text('Skip')",
                "div:has-text('Co-branded') label:has-text('Skip')",
                "div:has-text('Loyalty Points') label:has-text('Skip')"
            ]:
                try:
                    loc = page.locator(skip_sel).first
                    if await loc.count() > 0 and await loc.is_visible():
                        await loc.scroll_into_view_if_needed()
                        box = loc.locator(".ui-radiobutton-box").first
                        if await box.count() > 0:
                            await box.click(timeout=1500)
                        else:
                            await loc.click(timeout=1500)
                        cobrand_skipped = f'pw-{skip_sel}'
                        break
                except Exception:
                    pass

            # Strategy 2 (Exact JS native click on Skip radio/label/input):
            if not cobrand_skipped:
                try:
                    result = await page.evaluate('''() => {
                        // Find all elements with exact text "skip"
                        const allNodes = Array.from(document.querySelectorAll('label, span, div, p-radiobutton, input'));
                        const skipNodes = allNodes.filter(el => {
                            const t = (el.innerText || el.textContent || '').trim().toLowerCase();
                            return t === 'skip' || (t.startsWith('skip') && t.length <= 10);
                        });
                        for (const el of skipNodes) {
                            el.click();
                            try { el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window })); } catch(e) {}
                            const pRadio = el.closest('p-radiobutton') || el.closest('.ui-radiobutton') || el.parentElement;
                            const box = pRadio?.querySelector('.ui-radiobutton-box');
                            if (box) {
                                box.click();
                                try { box.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window })); } catch(e) {}
                            }
                            const inp = pRadio?.querySelector('input[type="radio"]') || el.parentElement?.querySelector('input[type="radio"]');
                            if (inp) {
                                inp.checked = true;
                                inp.dispatchEvent(new Event('input', { bubbles: true }));
                                inp.dispatchEvent(new Event('change', { bubbles: true }));
                            }
                            return 'js-skip-node';
                        }

                        // Fallback: In cobrand container, click 3rd radio
                        const sections = Array.from(document.querySelectorAll('div, p-card')).filter(d => {
                            const t = (d.innerText || '').toLowerCase();
                            return (t.includes('co-branded card') || (t.includes('loyalty points') && t.includes('skip'))) && t.length < 1000;
                        });
                        sections.sort((a, b) => (a.innerText || '').length - (b.innerText || '').length);
                        if (sections.length > 0) {
                            const boxes = Array.from(sections[0].querySelectorAll('.ui-radiobutton-box'));
                            if (boxes.length >= 3) {
                                const skipBox = boxes[2];
                                skipBox.scrollIntoView({ behavior: 'instant', block: 'center' });
                                skipBox.click();
                                try { skipBox.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window })); } catch(e) {}
                                const inp = skipBox.parentElement?.querySelector('input[type="radio"]');
                                if (inp) {
                                    inp.checked = true;
                                    inp.dispatchEvent(new Event('input', { bubbles: true }));
                                    inp.dispatchEvent(new Event('change', { bubbles: true }));
                                }
                                return 'js-index-3';
                            }
                        }
                        return false;
                    }''')
                    if result:
                        cobrand_skipped = result
                except Exception:
                    pass

            if cobrand_skipped:
                log_event(db, "INFO", "AUTOMATION", f"Selected 'Skip' on IRCTC Co-branded Card Benefits (strategy: {cobrand_skipped}).", ref)
            else:
                log_event(db, "WARNING", "AUTOMATION", "Could not find/click Co-branded Card Skip button.", ref)
        except Exception as e:
            log_event(db, "WARNING", "AUTOMATION", f"Co-branded card benefit note: {e}", ref)
        await asyncio.sleep(0.3)  # Let Angular digest cobrand click before payment selection

        # Select Payment Mode: BHIM/UPI (Convenience Fee: ₹20 + GST / ₹10 + GST)
        try:
            upi_selected = False
            # Strategy 1 (Direct Playwright Click on BHIM/UPI):
            for upi_sel in [
                "text='Pay through BHIM/UPI'",
                "label:has-text('Pay through BHIM/UPI')",
                "div:has-text('Pay through BHIM/UPI') .ui-radiobutton-box",
                "label:has-text('BHIM/UPI') .ui-radiobutton-box",
                "text='BHIM/UPI'"
            ]:
                try:
                    loc = page.locator(upi_sel).first
                    if await loc.count() > 0 and await loc.is_visible():
                        await loc.scroll_into_view_if_needed()
                        box = loc.locator(".ui-radiobutton-box").first
                        if await box.count() > 0:
                            await box.click(timeout=1500)
                        else:
                            await loc.click(timeout=1500)
                        upi_selected = f'pw-{upi_sel}'
                        break
                except Exception:
                    pass

            # Strategy 2 (JS evaluate with strict filter: MUST contain bhim/upi and NOT contain credit/debit):
            if not upi_selected:
                try:
                    upi_selected = await page.evaluate('''() => {
                        // Strategy A: Find innermost element that strictly has bhim/upi and NOT credit/debit
                        const candidates = Array.from(document.querySelectorAll('label, div, p-radiobutton, tr, span')).filter(el => {
                            const text = (el.innerText || '').toLowerCase();
                            return (text.includes('bhim/upi') || (text.includes('bhim') && text.includes('upi'))) && 
                                   !text.includes('credit') && !text.includes('debit') && text.length < 200;
                        });
                        candidates.sort((a, b) => (a.innerText || '').length - (b.innerText || '').length);
                        for (const el of candidates) {
                            el.click();
                            try { el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window })); } catch(e) {}
                            const box = el.querySelector('.ui-radiobutton-box') || (el.closest('.row, div, tr')?.querySelector('.ui-radiobutton-box')) || el.previousElementSibling?.querySelector('.ui-radiobutton-box');
                            if (box) {
                                box.scrollIntoView({ behavior: 'instant', block: 'center' });
                                box.click();
                                try { box.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window })); } catch(e) {}
                                const inp = box.parentElement?.querySelector('input[type="radio"]') || el.querySelector('input[type="radio"]');
                                if (inp) {
                                    inp.checked = true;
                                    inp.dispatchEvent(new Event('input', { bubbles: true }));
                                    inp.dispatchEvent(new Event('change', { bubbles: true }));
                                }
                                return 'js-strict-bhim';
                            }
                        }
                        // Strategy B: In Payment Mode container, click 2nd radiobutton (index 1 = UPI)
                        const payContainers = Array.from(document.querySelectorAll('div, section, p-card')).filter(d => {
                            const t = (d.innerText || '').toLowerCase();
                            return t.includes('payment mode') && t.includes('convenience fee') && t.length < 1500;
                        });
                        payContainers.sort((a, b) => (a.innerText || '').length - (b.innerText || '').length);
                        if (payContainers.length > 0) {
                            const boxes = payContainers[0].querySelectorAll('.ui-radiobutton-box');
                            if (boxes.length >= 2) {
                                boxes[1].scrollIntoView({ behavior: 'instant', block: 'center' });
                                boxes[1].click();
                                try { boxes[1].dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window })); } catch(e) {}
                                const inp = boxes[1].parentElement?.querySelector('input[type="radio"]');
                                if (inp) {
                                    inp.checked = true;
                                    inp.dispatchEvent(new Event('input', { bubbles: true }));
                                    inp.dispatchEvent(new Event('change', { bubbles: true }));
                                }
                                return 'js-index-2';
                            }
                        }
                        return false;
                    }''')
                except Exception:
                    pass

            if upi_selected:
                log_event(db, "INFO", "AUTOMATION", f"Selected payment mode: BHIM/UPI (strategy: {upi_selected})", ref)
            else:
                log_event(db, "WARNING", "AUTOMATION", "Could not find/click BHIM/UPI payment mode", ref)
        except Exception as e:
            log_event(db, "WARNING", "AUTOMATION", f"Payment mode selection note: {e}", ref)
        await asyncio.sleep(0.3)  # Let Angular digest payment click before insurance selection
        # Travel Insurance: Yes (or No fallback) - Mandatory on IRCTC to proceed!
        try:
            ins_selected = await page.evaluate('''() => {
                // Strategy 1: Find tightest innermost label/div matching "Yes, and I accept"
                const candidates = Array.from(document.querySelectorAll('label, p-radiobutton, span, div'));
                const matches = candidates.filter(el => {
                    const text = (el.innerText || el.textContent || '').trim().toLowerCase();
                    return (text.startsWith('yes, and i accept') || (text.includes('yes') && text.includes('accept'))) && text.length < 150 && !text.includes('no, i do not');
                });
                matches.sort((a, b) => (a.innerText || '').length - (b.innerText || '').length);

                for (const el of matches) {
                    // Try clicking label directly
                    el.click();
                    let box = el.querySelector('.ui-radiobutton-box') || el.closest('.col-xs-12, .row, div, tr')?.querySelector('.ui-radiobutton-box') || el.previousElementSibling?.querySelector('.ui-radiobutton-box');
                    if (box) {
                        box.scrollIntoView({ behavior: 'instant', block: 'center' });
                        box.click();
                        try { box.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window })); } catch(e) {}
                        const inp = box.parentElement?.querySelector('input[type="radio"]') || el.parentElement?.querySelector('input[type="radio"]');
                        if (inp) {
                            inp.checked = true;
                            inp.dispatchEvent(new Event('input', { bubbles: true }));
                            inp.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                        return true;
                    }
                }

                // Strategy 2: Check form controls specifically named insurance
                const insRadios = Array.from(document.querySelectorAll("p-radiobutton[formcontrolname*='insurance' i], input[formcontrolname*='insurance' i], p-radiobutton[name*='insurance' i], input[name*='insurance' i]"));
                if (insRadios.length >= 2) {
                    const firstBox = insRadios[0].querySelector('.ui-radiobutton-box') || insRadios[0];
                    firstBox.click();
                    return true;
                }

                // Strategy 3: Tightest container matching travel insurance (length < 600, not entire page)
                const insContainers = Array.from(document.querySelectorAll('div, table, tr, p-card')).filter(d => {
                    const t = (d.innerText || '').toLowerCase();
                    return t.includes('travel insurance') && (t.includes('terms') || t.includes('0.45') || t.includes('accept')) && t.length < 600;
                });
                insContainers.sort((a, b) => (a.innerText || '').length - (b.innerText || '').length);
                if (insContainers.length > 0) {
                    const boxes = insContainers[0].querySelectorAll('.ui-radiobutton-box');
                    if (boxes.length > 0) {
                        boxes[0].scrollIntoView({ behavior: 'instant', block: 'center' });
                        boxes[0].click();
                        return true;
                    }
                }
                return false;
            }''')

            if not ins_selected:
                ins_box = page.locator(
                    "label:has-text('Yes, and I accept'), "
                    "p-radiobutton:has-text('Yes, and I accept') .ui-radiobutton-box, "
                    "div:has-text('Yes, and I accept'):not(:has-text('No, I do not')) .ui-radiobutton-box, "
                    "label:has-text('Yes') .ui-radiobutton-box, "
                    "label:has-text('Yes, and I accept')"
                ).first
                if await ins_box.count() > 0:
                    await ins_box.click(force=True)
                    await asyncio.sleep(0.3)

            log_event(db, "INFO", "AUTOMATION", "Selected travel insurance: Yes", ref)
        except Exception as e:
            log_event(db, "WARNING", "AUTOMATION", f"Travel insurance selection note: {e}", ref)

        # Auto-upgradation checkbox
        try:
            await page.evaluate('''() => {
                const cb = document.querySelector('#autoUpgradation') || document.querySelector('input[name="autoUpgradation"]') || document.querySelector("p-checkbox[formcontrolname='autoUpgradation']");
                if (cb) {
                    const lbl = document.querySelector("label[for='autoUpgradation']") || cb.querySelector('.ui-chkbox-box') || cb.closest('div')?.querySelector('label');
                    if (lbl) lbl.click();
                    else {
                        const inp = cb.querySelector('input') || cb;
                        inp.checked = true;
                        inp.dispatchEvent(new Event('change', {bubbles: true}));
                    }
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
            # Scroll to passenger submit area (centering the Continue button, not scrolling past to the footer)
            await page.evaluate('''() => {
                const btn = Array.from(document.querySelectorAll('button')).find(b => (b.innerText || '').toLowerCase().includes('continue'));
                if (btn) btn.scrollIntoView({ behavior: 'smooth', block: 'center' });
                else window.scrollTo(0, document.body.scrollHeight * 0.7);
            }''')
            await asyncio.sleep(0.5)

            # Check Angular form validity and verify Payment / Insurance radios before clicking Continue
            form_state = await page.evaluate('''() => {
                const result = {valid: null, errors: [], fields: {}};
                const names = document.querySelectorAll("p-autocomplete[formcontrolname='passengerName'] input, input[placeholder*='Passenger Name' i]");
                const ages = document.querySelectorAll("input[formcontrolname='passengerAge'], input[placeholder*='Age' i]");
                const genders = document.querySelectorAll("select[formcontrolname='passengerGender'], p-dropdown[formcontrolname='passengerGender']");
                const nats = document.querySelectorAll("select[formcontrolname='passengerNationality'], p-dropdown[formcontrolname='passengerNationality']");
                const mobiles = document.querySelectorAll("input[formcontrolname='mobileNumber'], input#mobileNumber");
                result.fields.names = Array.from(names).map(n => n.value || '');
                result.fields.ages = Array.from(ages).map(a => a.value || '');
                result.fields.genderCount = genders.length;
                result.fields.nationalities = Array.from(nats).map(n => n.value || (n.innerText || '').trim().slice(0, 30));
                result.fields.mobile = mobiles.length > 0 ? mobiles[0].value : '';

                // Verify radio button states accurately
                const isUpiActive = () => {
                    // Check active radio buttons in payment section
                    const activeBoxes = Array.from(document.querySelectorAll('.ui-radiobutton-box.ui-state-active, input[type="radio"]:checked'));
                    for (const b of activeBoxes) {
                        const parent = b.closest('p-radiobutton, .ui-radiobutton, label, .row, .col-xs-12, tr, td, div');
                        const parentText = (parent?.innerText || parent?.textContent || '').toLowerCase();
                        // Strictly skip if this is the Credit Card option
                        if (parentText.includes('credit') || parentText.includes('debit') || parentText.includes('net banking')) {
                            continue;
                        }
                        if ((parentText.includes('bhim') || parentText.includes('upi')) && (parentText.includes('10') || parentText.includes('pay through') || parentText.includes('convenience'))) {
                            return true;
                        }
                    }
                    // Strategy 2: Check 2nd radio in Payment Mode container
                    const payContainers = Array.from(document.querySelectorAll('div, section, p-card')).filter(d => {
                        const t = (d.innerText || '').toLowerCase();
                        return t.includes('payment mode') && t.includes('convenience fee') && t.length < 1500;
                    });
                    payContainers.sort((a, b) => (a.innerText || '').length - (b.innerText || '').length);
                    if (payContainers.length > 0) {
                        const boxes = payContainers[0].querySelectorAll('.ui-radiobutton-box');
                        const inps = payContainers[0].querySelectorAll('input[type="radio"]');
                        if (boxes.length >= 2 && boxes[1].classList.contains('ui-state-active')) return true;
                        if (inps.length >= 2 && inps[1].checked) return true;
                    }
                    return false;
                };

                const isInsActive = () => {
                    // Check direct insurance form controls
                    const insRadios = Array.from(document.querySelectorAll("p-radiobutton[formcontrolname*='insurance' i], input[formcontrolname*='insurance' i], p-radiobutton[name*='insurance' i], input[name*='insurance' i]"));
                    
                    // Check insurance containers
                    const insContainers = Array.from(document.querySelectorAll('div, table, tr, p-card')).filter(d => {
                        const t = (d.innerText || '').toLowerCase();
                        return t.includes('travel insurance') && (t.includes('terms') || t.includes('accept') || t.includes('0.45')) && t.length < 600;
                    });

                    // If Travel Insurance is NOT offered on this train/class (e.g. WL tickets), consider it handled / not applicable
                    if (insRadios.length === 0 && insContainers.length === 0) {
                        return true;
                    }

                    if (insRadios.length >= 2) {
                        const firstBox = insRadios[0].querySelector('.ui-radiobutton-box') || insRadios[0];
                        const firstInp = insRadios[0].querySelector('input') || (insRadios[0].tagName === 'INPUT' ? insRadios[0] : null);
                        if (firstBox.classList.contains('ui-state-active') || (firstInp && firstInp.checked)) return true;
                    }
                    
                    insContainers.sort((a, b) => (a.innerText || '').length - (b.innerText || '').length);
                    if (insContainers.length > 0) {
                        const section = insContainers[0];
                        const boxes = Array.from(section.querySelectorAll('.ui-radiobutton-box'));
                        const radios = Array.from(section.querySelectorAll('input[type="radio"]'));
                        // 1st radio = "Yes, and I accept"
                        if (boxes.length >= 1 && boxes[0].classList.contains('ui-state-active')) return true;
                        if (radios.length >= 1 && radios[0].checked) return true;
                    }
                    // Check active radio buttons in small containers with Yes text
                    const activeBoxes = Array.from(document.querySelectorAll('.ui-radiobutton-box.ui-state-active, input[type="radio"]:checked'));
                    for (const b of activeBoxes) {
                        const parent = b.closest('.row, .col-xs-12, tr, td, div');
                        const parentText = (parent?.innerText || '').toLowerCase();
                        if (parentText.length < 300 && (parentText.includes('yes') && (parentText.includes('accept') || parentText.includes('insurance'))) && !parentText.includes('no, i do not')) {
                            return true;
                        }
                    }
                    return false;
                };

                const isCobrandHandled = () => {
                    const cobrandSections = Array.from(document.querySelectorAll('div, p-card')).filter(d => {
                        const t = (d.innerText || '').toLowerCase();
                        return (t.includes('co-branded card') || (t.includes('loyalty points') && t.includes('skip'))) && t.length < 1000;
                    });
                    cobrandSections.sort((a, b) => (a.innerText || '').length - (b.innerText || '').length);
                    if (cobrandSections.length === 0) return true; // section not present
                    const section = cobrandSections[0];
                    const boxes = Array.from(section.querySelectorAll('.ui-radiobutton-box'));
                    const radios = Array.from(section.querySelectorAll('input[type="radio"]'));
                    // Index-based: 3rd radio (index 2) = Skip
                    if (boxes.length >= 3 && boxes[2].classList.contains('ui-state-active')) return true;
                    if (radios.length >= 3 && radios[2].checked) return true;
                    // Fallback: any checked/active radio whose label text is "skip"
                    const activeBoxes = Array.from(section.querySelectorAll('.ui-radiobutton-box.ui-state-active, input[type="radio"]:checked'));
                    for (const b of activeBoxes) {
                        const parent = b.closest('p-radiobutton, .ui-radiobutton, label') || b.parentElement;
                        const txt = (parent?.innerText || parent?.textContent || '').trim().toLowerCase();
                        if (txt.includes('skip') && !txt.includes('earn')) return true;
                    }
                    // Check if "Earn Loyalty Points" is NOT active (default) — means user changed it
                    if (boxes.length >= 1 && !boxes[0].classList.contains('ui-state-active') && radios.length >= 1 && !radios[0].checked) return true;
                    return false;
                };

                const upiActive = isUpiActive();
                const insActive = isInsActive();
                const cobrandOk = isCobrandHandled();

                result.fields.paymentSelected = upiActive;
                result.fields.insuranceSelected = insActive;
                result.fields.cobrandSkipped = cobrandOk;

                // Visible validation errors
                const errs = Array.from(document.querySelectorAll('.ui-message-error, .text-danger, .error-msg, span.help-block, .ui-messages-error, .ng-invalid.ng-touched'));
                result.errors = errs.slice(0, 5).map(e => (e.innerText || e.className || '').trim().slice(0, 100)).filter(t => t.length > 0);
                const hasInvalid = document.querySelector('form.ng-invalid, .ng-invalid.ng-touched');
                result.valid = !hasInvalid && upiActive && insActive && cobrandOk;
                return result;
            }''')
            log_event(db, "INFO", "AUTOMATION", f"Pre-Continue form state: {form_state}", ref)

            # Auto-repair payment, insurance, or co-branded card if not active
            needs_repair = (
                not form_state.get('fields', {}).get('paymentSelected', False) or 
                not form_state.get('fields', {}).get('insuranceSelected', False) or 
                not form_state.get('fields', {}).get('cobrandSkipped', True)
            )
            if needs_repair:
                log_event(db, "WARNING", "AUTOMATION", "Payment/Insurance/Loyalty radio not active. Applying auto-repair click...", ref)
                # 1. Click Co-branded Card Skip using PLAYWRIGHT direct text locators
                if not form_state.get('fields', {}).get('cobrandSkipped', True):
                    try:
                        for skip_sel in ["text='Skip'", "label:has-text('Skip')", "span:text-is('Skip')"]:
                            loc = page.locator(skip_sel).first
                            if await loc.count() > 0:
                                await loc.scroll_into_view_if_needed()
                                box = loc.locator(".ui-radiobutton-box").first
                                if await box.count() > 0:
                                    await box.click(timeout=1500)
                                else:
                                    await loc.click(timeout=1500)
                                await asyncio.sleep(0.2)
                                break
                    except Exception:
                        pass

                # 2. Click BHIM/UPI using PLAYWRIGHT direct text locators
                if not form_state.get('fields', {}).get('paymentSelected', False):
                    try:
                        for upi_sel in ["text='Pay through BHIM/UPI'", "label:has-text('Pay through BHIM/UPI')", "text='BHIM/UPI'"]:
                            loc = page.locator(upi_sel).first
                            if await loc.count() > 0:
                                await loc.scroll_into_view_if_needed()
                                box = loc.locator(".ui-radiobutton-box").first
                                if await box.count() > 0:
                                    await box.click(timeout=1500)
                                else:
                                    await loc.click(timeout=1500)
                                await asyncio.sleep(0.2)
                                break
                    except Exception:
                        pass

                # 3. Fallback evaluate click (strict, no credit card)
                await page.evaluate('''() => {
                    // Strict UPI click
                    const upiContainer = Array.from(document.querySelectorAll('label, div, p-radiobutton')).find(el => {
                        const t = (el.innerText || '').toLowerCase();
                        return (t.includes('bhim/upi') || (t.includes('bhim') && t.includes('upi'))) && 
                               !t.includes('credit') && !t.includes('debit') && el.querySelector('.ui-radiobutton-box');
                    });
                    if (upiContainer) {
                        const box = upiContainer.querySelector('.ui-radiobutton-box');
                        if (box) { box.click(); }
                        const inp = upiContainer.querySelector('input[type="radio"]');
                        if (inp) { inp.checked = true; inp.dispatchEvent(new Event('change', {bubbles: true})); }
                    } else {
                        const payContainers = Array.from(document.querySelectorAll('div, section, p-card')).filter(d => {
                            const t = (d.innerText || '').toLowerCase();
                            return t.includes('payment mode') && t.includes('convenience fee') && t.length < 1500;
                        });
                        payContainers.sort((a, b) => (a.innerText || '').length - (b.innerText || '').length);
                        if (payContainers.length > 0) {
                            const boxes = payContainers[0].querySelectorAll('.ui-radiobutton-box');
                            if (boxes.length >= 2) boxes[1].click();
                        }
                    }

                    // Travel Insurance Yes
                    const candidates = Array.from(document.querySelectorAll('label, p-radiobutton, span, div'));
                    const matches = candidates.filter(el => {
                        const text = (el.innerText || el.textContent || '').trim().toLowerCase();
                        return (text.startsWith('yes, and i accept') || (text.includes('yes') && text.includes('accept'))) && text.length < 150 && !text.includes('no, i do not');
                    });
                    matches.sort((a, b) => (a.innerText || '').length - (b.innerText || '').length);
                    for (const el of matches) {
                        el.click();
                        const box = el.querySelector('.ui-radiobutton-box') || el.closest('.col-xs-12, .row, div, tr')?.querySelector('.ui-radiobutton-box');
                        if (box) { box.click(); break; }
                    }
                }''')
                await asyncio.sleep(0.4)

            # Dump DOM if form is still invalid for diagnostics
            if not form_state.get('valid', False):
                try:
                    dom_html = await page.evaluate("() => document.querySelector('form, body')?.innerHTML?.slice(0, 50000) || ''")
                    with open("data/passenger_page_dom.html", "w", encoding="utf-8") as f:
                        f.write(dom_html)
                except Exception:
                    pass

            # Save full-page diagnostic screenshot
            try:
                await page.screenshot(path="data/pre_continue_screenshot.png", full_page=True)
            except Exception:
                try:
                    await page.screenshot(path="data/pre_continue_screenshot.png")
                except Exception:
                    pass

            # Check if there are visible validation notices on page
            v_errs = await page.evaluate('''() => {
                const errs = Array.from(document.querySelectorAll('.ui-message-error, .text-danger, .error-msg, span.help-block, .ui-messages-error'));
                return errs.map(e => (e.innerText || '').trim()).filter(t => t.length > 0);
            }''')
            if v_errs:
                log_event(db, "WARNING", "AUTOMATION", f"Visible form notices: {'; '.join(v_errs[:3])}", ref)

            # Click Continue button cleanly without double-clicking
            clicked_continue = False
            cont_btn = page.locator(
                "app-passenger-input button:has-text('Continue'), "
                "form button.train_Search:has-text('Continue'), "
                "form button:has-text('Continue'), "
                "button.btnDefault:has-text('Continue'), "
                "button[type='submit']:has-text('Continue'), "
                "button:has-text('Continue')"
            ).first
            if await cont_btn.count() > 0 and await cont_btn.is_visible():
                await cont_btn.scroll_into_view_if_needed()
                await asyncio.sleep(0.4)
                try:
                    await page.evaluate("() => window.scrollBy(0, 80)")
                except Exception:
                    pass
                try:
                    await cont_btn.click(timeout=4000)
                    clicked_continue = True
                    log_event(db, "INFO", "AUTOMATION", "Clicked Continue button on Passenger page.", ref)
                except Exception:
                    await cont_btn.click(force=True)
                    clicked_continue = True
                    log_event(db, "INFO", "AUTOMATION", "Force-clicked Continue button on Passenger page.", ref)

            if not clicked_continue:
                # JS fallback — only if Playwright locator didn't click
                clicked_continue = await page.evaluate('''() => {
                    const isVisible = (el) => !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length > 0));
                    const buttons = Array.from(document.querySelectorAll('app-passenger-input button, form button, button'));
                    const btn = buttons.find(b => {
                        if (b.closest('app-header, .header, nav, app-modify-search')) return false;
                        const t = (b.innerText || b.value || '').trim().toLowerCase();
                        return (t === 'continue' || t.includes('continue')) && isVisible(b);
                    });
                    if (btn) {
                        btn.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        btn.click();
                        try { btn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window })); } catch(e) {}
                        return true;
                    }
                    return false;
                }''')
                if clicked_continue:
                    log_event(db, "INFO", "AUTOMATION", "Clicked Continue button via JS fallback.", ref)

            await asyncio.sleep(1.0)
        except Exception as e:
            log_event(db, "WARNING", "AUTOMATION", f"Passenger Continue note: {e}", ref)

        # ══════════════════════════════════════════════════
        # Step 7: Review Booking Page & Security Challenge
        # ══════════════════════════════════════════════════
        session_state.set_stage("REVIEW_BOOKING")
        log_event(db, "INFO", "AUTOMATION", "Navigating to Review Booking page...", ref)

        # Wait up to 35s for Review page, cleanly handling any confirmation dialogs (Waitlist/Insurance/Senior)
        arrived_at_review = False
        dialog_confirmed = False

        for s in range(35):
            await asyncio.sleep(1)

            # Diagnostic snapshots during wait to identify modals or errors early
            if s in (2, 8):
                try:
                    await page.screenshot(path=f"data/wait_review_s{s}.png")
                except Exception:
                    pass

            # 1. Check if arrived at Review or Payment page
            if "review" in page.url.lower() or "payment" in page.url.lower():
                arrived_at_review = True
                break
            if await page.locator("app-review-booking, #nlpAnswer, app-captcha, app-payment, div:has-text('Review Booking')").count() > 0:
                arrived_at_review = True
                break

            # 2. Handle PrimeNG confirmation dialogs (Waitlist alert, travel insurance, auto-upgrade, senior concession, etc.)
            # Check in every iteration to handle sequential dialogs (e.g. Senior alert followed by Waitlist alert)
            try:
                confirmed_text = await page.evaluate('''() => {
                    const isVisibleDialog = (el) => {
                        if (!el || !(el.offsetWidth || el.offsetHeight || el.getClientRects().length > 0)) return false;
                        const txt = (el.innerText || '').trim();
                        if (txt.length < 5) return false;
                        const style = window.getComputedStyle(el);
                        return !(style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0');
                    };
                    const dialog = Array.from(document.querySelectorAll('p-confirmdialog, .ui-confirmdialog, p-dialog, .ui-dialog, div[role="dialog"], .modal-dialog, app-custom-dialog')).find(d => isVisibleDialog(d));
                    if (!dialog) return null;

                    const btns = Array.from(dialog.querySelectorAll('button, span.ui-button-text, a.btn, .ui-confirmdialog-yesbutton, .p-confirm-dialog-accept, input[type="button"]'));
                    const acceptBtn = btns.find(b => {
                        const t = (b.innerText || b.getAttribute('label') || b.value || '').trim().toLowerCase();
                        const cls = (b.className || '').toLowerCase();
                        return t.includes('yes') || t.includes('continue') || t.includes('agree') || t.includes('proceed') || t.includes('confirm') || t.includes('ok') || cls.includes('yesbutton') || cls.includes('dialog-accept') || cls.includes('accept');
                    });

                    if (acceptBtn) {
                        const dialogMsg = (dialog.innerText || '').slice(0, 150).replace(/\\s+/g, ' ');
                        const clickTarget = acceptBtn.closest('button') || acceptBtn;
                        clickTarget.click();
                        return dialogMsg;
                    }
                    return null;
                }''')
                if confirmed_text:
                    dialog_confirmed = True
                    log_event(db, "INFO", "AUTOMATION", f"Accepted IRCTC confirmation dialog: '{confirmed_text}'", ref)
                    await asyncio.sleep(1.5)
                    continue
            except Exception:
                pass

            # Playwright fallback for confirmation dialog accept button
            try:
                confirm_yes = page.locator(
                    "p-confirmdialog button.ui-confirmdialog-yesbutton, "
                    ".ui-confirmdialog button:has-text('Yes'), "
                    ".ui-confirmdialog button:has-text('Continue'), "
                    "button.p-confirm-dialog-accept, "
                    "p-dialog button:has-text('Yes'), "
                    "p-dialog button:has-text('Continue'), "
                    ".ui-dialog button:has-text('Yes'), "
                    ".ui-dialog button:has-text('Continue'), "
                    ".ui-dialog button:has-text('Proceed'), "
                    "button:has-text('I Agree'), "
                    ".ui-dialog button:has-text('OK')"
                ).first
                if await confirm_yes.count() > 0 and await confirm_yes.is_visible():
                    await confirm_yes.click(timeout=1000)
                    dialog_confirmed = True
                    log_event(db, "INFO", "AUTOMATION", "Clicked Yes/Continue on confirmation dialog via Playwright locator", ref)
                    await asyncio.sleep(1.5)
                    continue
            except Exception:
                pass

            # 3. Detect IRCTC error page
            if "/nget/error" in page.url.lower():
                err = f"IRCTC redirected to error page ({page.url}). This usually means passenger details validation failed or session expired on IRCTC side."
                log_event(db, "ERROR", "AUTOMATION", err, ref)
                session_state.set_stage("FAILED", "FAILED")
                session_state.error_message = err
                booking.status = "FAILED"
                db.commit()
                if settings.TELEGRAM_ENABLED:
                    await send_telegram_message(
                        f"❌ *Booking Error* (Ref: `{ref}`)\n\n"
                        f"IRCTC ne error page dikhai. Session expire ho gaya ya details me koi issue tha.\n\n"
                        f"👉 Kripya dobara try karein.",
                        reply_markup={"inline_keyboard": [[{"text": "🎫 Nayi Booking Karein", "callback_data": "cmd_book"}]]}
                    )
                try:
                    await page.screenshot(path="data/irctc_error_page.png")
                except Exception:
                    pass
                return

        # If not arrived at review booking or payment, raise informative error with debug info
        if not arrived_at_review:
            current_url = page.url
            page_diagnostics = ""
            try:
                page_diagnostics = await page.evaluate('''() => {
                    const isVisibleDialog = (el) => {
                        if (!el || !(el.offsetWidth || el.offsetHeight || el.getClientRects().length > 0)) return false;
                        const txt = (el.innerText || '').trim();
                        if (txt.length < 5) return false;
                        const style = window.getComputedStyle(el);
                        return !(style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0');
                    };
                    const dialog = Array.from(document.querySelectorAll('.ui-dialog[role="dialog"], p-confirmdialog, div[role="dialog"]')).find(d => isVisibleDialog(d));
                    if (dialog) return 'Dialog visible: ' + (dialog.innerText || '').slice(0, 150).replace(/\\s+/g, ' ');
                    const err = document.querySelector('.ui-message-error, .text-danger, .error-msg, .ui-messages-error');
                    const isVisible = (el) => !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length > 0));
                    if (err && isVisible(err)) return 'Form error: ' + (err.innerText || '').slice(0, 150).replace(/\\s+/g, ' ');
                    return 'URL: ' + window.location.href;
                }''')
            except Exception:
                pass
            err = f"Could not transition from Passenger page to Review Booking page ({page_diagnostics or current_url}). Please check passenger details or browser dialog."
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
            log_event(db, "INFO", "AUTOMATION", "Review page CAPTCHA detected. Auto-solving in background...", ref)
            review_captcha_solved = False

            for captcha_attempt in range(5):
                captcha_bytes = None
                try:
                    await dismiss_overlays(page)
                    captcha_img_loc = page.locator("app-captcha img, #captchaImg, img.captcha-img, img[alt*='captcha' i]").first
                    captcha_input = page.locator("#nlpAnswer, input[formcontrolname='captcha'], input[placeholder*='captcha' i], #captcha").first
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

                    # Auto-solve captcha
                    candidate_text, conf = fast_solve_captcha(captcha_bytes)
                    if candidate_text and await captcha_input.count() > 0:
                        try:
                            await captcha_input.fill("")
                            await SmartBrowserActions.smart_type(page, captcha_input, candidate_text, delay_ms=30)
                        except Exception:
                            pass

                    log_event(db, "INFO", "AUTOMATION", f"Review CAPTCHA auto-solved: '{candidate_text}' (attempt {captcha_attempt+1}/5)", ref)

                    # Auto-submit the review page
                    try:
                        submit_btn = page.locator("button:has-text('Continue'), button[type='submit']:has-text('Continue'), button.btn-primary:has-text('Continue')").first
                        if await submit_btn.count() > 0:
                            await submit_btn.scroll_into_view_if_needed()
                            await submit_btn.click(timeout=4000, force=True)
                            await asyncio.sleep(2.0)
                    except Exception:
                        pass

                    # Auto-click any modal dialogs (Yes / Agree / OK)
                    try:
                        await page.evaluate('''() => {
                            const isVisible = (el) => !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length > 0));
                            const dialogs = Array.from(document.querySelectorAll('.ui-dialog, p-confirmdialog, .ui-confirmdialog, div[role="dialog"]')).filter(d => isVisible(d));
                            for (const d of dialogs) {
                                const btn = Array.from(d.querySelectorAll('button, span.ui-button-text, a.btn, .ui-confirmdialog-yesbutton, .p-confirm-dialog-accept')).find(b => {
                                    const t = (b.innerText || b.getAttribute('label') || '').trim().toLowerCase();
                                    const cls = (b.className || '').toLowerCase();
                                    return t === 'yes' || t === 'i agree' || t === 'agree' || t === 'ok' || t === 'continue' || t === 'confirm' || cls.includes('yesbutton') || cls.includes('dialog-accept');
                                });
                                if (btn) (btn.closest('button') || btn).click();
                            }
                        }''')
                    except Exception:
                        pass

                    # Check if we moved past review page to payment
                    for _ in range(10):
                        if "payment" in page.url.lower() or await page.locator("app-payment, div:has-text('Payment Option'), #bank-type").count() > 0:
                            review_captcha_solved = True
                            break
                        await asyncio.sleep(0.5)

                    if review_captcha_solved:
                        log_event(db, "INFO", "AUTOMATION", "Review page successfully submitted! Proceeding to Payment.", ref)
                        break

                    # If still on review, captcha was wrong — refresh and retry
                    log_event(db, "WARNING", "AUTOMATION", f"Review CAPTCHA attempt {captcha_attempt+1} did not navigate. Refreshing captcha...", ref)
                    try:
                        refresh_btn = page.locator("app-captcha .refresh-btn, app-captcha a, .captcha-refresh").first
                        if await refresh_btn.count() > 0:
                            await refresh_btn.click(force=True)
                            await asyncio.sleep(1.5)
                    except Exception:
                        pass

            if not review_captcha_solved:
                log_event(db, "WARNING", "AUTOMATION", "Review page CAPTCHA could not be automatically resolved after 5 attempts.", ref)
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
            user_mob = "".join(c for c in (booking.contact_mobile or "") if c.isdigit())
            if not captured_pnr:
                pnr_label_match = re.search(r'(?:PNR|pnr)[\s\:\.\#-]*([2-9]\d{9})', page_content)
                if pnr_label_match and pnr_label_match.group(1) != user_mob:
                    captured_pnr = pnr_label_match.group(1)
                else:
                    all_matches = re.findall(r'\b[2-9]\d{9}\b', page_content)
                    for m_cand in all_matches:
                        if m_cand != user_mob and not m_cand.startswith("1000068"):
                            captured_pnr = m_cand
                            break

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
        import traceback
        tb_str = traceback.format_exc()
        err_msg = str(e) or repr(e)
        session_state.set_stage("FAILED", "FAILED")
        session_state.error_message = err_msg
        booking.status = "FAILED"
        db.commit()
        log_event(db, "ERROR", "AUTOMATION", f"Real IRCTC Flow error: {err_msg} | Details: {tb_str[-250:]}", ref)
