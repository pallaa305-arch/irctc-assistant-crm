import asyncio
import logging
import re
from typing import Optional, List, Dict, Any, Tuple
from playwright.async_api import Page, Locator

logger = logging.getLogger("smart_browser")

class SmartBrowserActions:
    """
    Hybrid Browser Automation Engine combining Playwright with Browser-Use techniques:
    - DOM Perception & Clickable Element Detection
    - Exact Viewport Center-Coordinate Clicking (bypassing synthetic event blocks)
    - Angular / PrimeNG Event Dispatching (input, change, blur)
    - Multi-layer fallbacks for 100% click delivery
    """

    @staticmethod
    async def get_element_center_coordinates(page: Page, locator: Locator) -> Optional[Tuple[float, float]]:
        """Extracts exact viewport center coordinates using Playwright bounding box."""
        try:
            if await locator.count() > 0 and await locator.first.is_visible():
                await locator.first.scroll_into_view_if_needed()
                await asyncio.sleep(0.1)
                box = await locator.first.bounding_box()
                if box and box["width"] > 0 and box["height"] > 0:
                    cx = box["x"] + box["width"] / 2
                    cy = box["y"] + box["height"] / 2
                    return (cx, cy)
        except Exception as e:
            logger.debug(f"bounding_box error: {e}")
        return None

    @staticmethod
    async def smart_click(
        page: Page,
        selectors: List[str],
        text_keywords: Optional[List[str]] = None,
        scope_locator: Optional[Locator] = None,
        timeout_ms: int = 4000,
        wait_after_sec: float = 0.5
    ) -> bool:
        """
        Executes a bulletproof multi-layer click:
        Layer 1: Playwright locator bounding-box -> native mouse click at center coords (browser-use approach)
        Layer 2: Playwright locator standard click (force=True)
        Layer 3: DOM tree text/role inspection -> evaluate getBoundingClientRect -> mouse.click
        Layer 4: Synthetic DOM event dispatch (pointerdown, mousedown, pointerup, mouseup, click)
        """
        container = scope_locator if scope_locator is not None else page

        # Layer 1 & 2: Try provided selectors
        for sel in selectors:
            try:
                loc = container.locator(sel).first
                if await loc.count() > 0 and await loc.is_visible():
                    await loc.scroll_into_view_if_needed()
                    await asyncio.sleep(0.1)
                    
                    # Try native center-coordinate click (Browser-Use style)
                    coords = await SmartBrowserActions.get_element_center_coordinates(page, loc)
                    if coords:
                        await page.mouse.move(coords[0], coords[1])
                        await asyncio.sleep(0.05)
                        await page.mouse.click(coords[0], coords[1])
                        await asyncio.sleep(wait_after_sec)
                        return True

                    # Fallback to Playwright force click
                    await loc.click(timeout=timeout_ms, force=True)
                    await asyncio.sleep(wait_after_sec)
                    return True
            except Exception:
                continue

        # Layer 3 & 4: Deep DOM search via JS for text_keywords
        if text_keywords:
            try:
                clicked = await page.evaluate('''(keywords) => {
                    const allElems = Array.from(document.querySelectorAll('button, a, div, span, td, label, p, h6, input[type="button"], input[type="submit"]'));
                    for (const kw of keywords) {
                        const targetKw = kw.trim().toUpperCase();
                        for (const el of allElems) {
                            if (!el.offsetParent) continue; // Must be visible
                            const t = (el.innerText || el.textContent || el.value || '').trim().toUpperCase();
                            const matches = t === targetKw || 
                                            t.startsWith(targetKw + ' ') || 
                                            t.endsWith(' ' + targetKw) || 
                                            t.includes('(' + targetKw + ')') ||
                                            t.includes(targetKw);
                            if (matches) {
                                el.scrollIntoView({ behavior: 'instant', block: 'center' });
                                const rect = el.getBoundingClientRect();
                                if (rect.width > 0 && rect.height > 0) {
                                    // Dispatch complete synthetic mouse event chain
                                    const events = ['pointerover', 'mouseover', 'pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'];
                                    events.forEach(etype => {
                                        el.dispatchEvent(new MouseEvent(etype, {
                                            bubbles: true,
                                            cancelable: true,
                                            view: window,
                                            clientX: rect.x + rect.width / 2,
                                            clientY: rect.y + rect.height / 2
                                        }));
                                    });
                                    if (typeof el.click === 'function') el.click();
                                    return { success: true, x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
                                }
                            }
                        }
                    }
                    return { success: false };
                }''', text_keywords)

                if clicked and clicked.get("success"):
                    # Send a physical mouse click at the reported center coordinates too
                    if "x" in clicked and "y" in clicked:
                        try:
                            await page.mouse.click(clicked["x"], clicked["y"])
                        except Exception:
                            pass
                    await asyncio.sleep(wait_after_sec)
                    return True
            except Exception as e:
                logger.debug(f"DOM text click error: {e}")

        return False

    @staticmethod
    async def smart_type(
        page: Page,
        locator: Locator,
        text: str,
        delay_ms: int = 35,
        clear_first: bool = True
    ) -> bool:
        """
        Types text with human-like delay and dispatches Angular reactive form events.
        """
        try:
            if await locator.count() == 0:
                return False
            await locator.first.scroll_into_view_if_needed()
            await locator.first.click(force=True)
            await asyncio.sleep(0.1)

            if clear_first:
                # Select all and delete
                await page.keyboard.press("Control+A")
                await page.keyboard.press("Backspace")
                await asyncio.sleep(0.1)

            # Type with natural delay
            await locator.first.press_sequentially(text, delay=delay_ms)
            await asyncio.sleep(0.1)

            # Trigger synthetic Angular/React change detection events
            await locator.first.evaluate('''(el) => {
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
                el.dispatchEvent(new Event('blur', { bubbles: true }));
            }''')
            return True
        except Exception as e:
            logger.debug(f"smart_type error: {e}")
            return False

    @staticmethod
    async def select_train_class_and_slot(
        page: Page,
        train_number: Optional[str],
        journey_class: str
    ) -> Dict[str, Any]:
        """
        Coordinates clicking train card, selecting class tab, awaiting availability,
        clicking date slot, and clicking active Book Now button.
        Returns dict with status, train details, fare, and arrived_at_passenger boolean.
        """
        journey_cls = (journey_class or "3A").strip().upper()
        res = {
            "success": False,
            "train_number": None,
            "train_name": None,
            "fare": None,
            "arrived_at_passenger": False,
            "error": None
        }

        # 1. Locate Target Train Card (app-train-avl-enq)
        target_card = None
        if train_number and train_number.strip() and train_number.strip() != "12002":
            num_m = re.search(r'\b\d{5}\b', train_number)
            s_num = num_m.group(0) if num_m else train_number.strip()
            c = page.locator("app-train-avl-enq").filter(has_text=s_num).first
            if await c.count() > 0:
                target_card = c

        if not target_card or await target_card.count() == 0:
            # Find first card that offers the requested class
            all_cards = page.locator("app-train-avl-enq")
            cnt = await all_cards.count()
            for i in range(min(cnt, 20)):
                c = all_cards.nth(i)
                if await c.locator(f"div.pre-avl:has-text('{journey_cls}'), span:has-text('{journey_cls}')").count() > 0:
                    target_card = c
                    break

        if not target_card or await target_card.count() == 0:
            target_card = page.locator("app-train-avl-enq").first

        if await target_card.count() == 0:
            res["error"] = "No train cards (app-train-avl-enq) found on search results page."
            return res

        await target_card.scroll_into_view_if_needed()
        await asyncio.sleep(0.5)

        # Extract train name/number
        try:
            heading = (await target_card.locator(".train-heading, .train-name").first.inner_text()).strip()
            nm = re.search(r'\b\d{5}\b', heading)
            if nm:
                res["train_number"] = nm.group(0)
            res["train_name"] = heading.split('\n')[0].strip()
        except Exception:
            pass

        # 2. Click Class Tab (e.g. 1A, 2A, 3A, SL)
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
        cls_keywords = cls_map.get(journey_cls, [journey_cls])
        cls_selectors = [f"div.pre-avl:has-text('{k}')" for k in cls_keywords] + [f"span:has-text('{k}')" for k in cls_keywords]

        clicked_class = await SmartBrowserActions.smart_click(
            page=page,
            selectors=cls_selectors,
            text_keywords=cls_keywords,
            scope_locator=target_card,
            wait_after_sec=0.5
        )

        # 3. Wait up to 15s for Availability Date Slots to Load (AVAILABLE / WL / RAC)
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

        for _ in range(30):
            await asyncio.sleep(0.5)
            # Check if slots appeared inside target train card
            slot_loc = target_card.locator(", ".join(slot_selectors)).first
            if await slot_loc.count() > 0 and await slot_loc.is_visible():
                coords = await SmartBrowserActions.get_element_center_coordinates(page, slot_loc)
                if coords:
                    await page.mouse.click(coords[0], coords[1])
                else:
                    await slot_loc.click(force=True)
                date_clicked = True
                await asyncio.sleep(1.0)
                break

        # 4. Wait for 'Book Now' button to become active (lose .disable-book class)
        book_now_clicked = False
        bn_selectors = [
            "button.train_Search:not(.disable-book)",
            "button:has-text('Book Now'):not(.disable-book)",
            "button[label='Book Now']:not(.disable-book)"
        ]

        for _ in range(20):
            bn = target_card.locator(", ".join(bn_selectors)).first
            if await bn.count() == 0:
                bn = page.locator(", ".join(bn_selectors)).first
            
            if await bn.count() > 0 and await bn.is_visible():
                coords = await SmartBrowserActions.get_element_center_coordinates(page, bn)
                if coords:
                    await page.mouse.click(coords[0], coords[1])
                else:
                    await bn.click(force=True)
                book_now_clicked = True
                await asyncio.sleep(1.5)
                break
            await asyncio.sleep(0.5)

        # 5. Handle PrimeNG Confirmation Dialogs & Check Navigation
        for _ in range(25):
            # Auto-click PrimeNG dialog buttons (Yes / I Agree / OK / Continue / Confirm)
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

            if "psgn-input" in page.url or await page.locator("input[placeholder*='Passenger Name' i], p-autocomplete[formcontrolname='passengerName'] input").count() > 0:
                res["arrived_at_passenger"] = True
                res["success"] = True
                break
            await asyncio.sleep(1)

        return res
