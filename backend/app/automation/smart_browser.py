import asyncio
import logging
import math
import random
import re
from typing import Optional, List, Dict, Any, Tuple
from playwright.async_api import Page, Locator

logger = logging.getLogger("smart_browser")

class SmartBrowserActions:
    """
    Hybrid Browser Automation Engine combining Playwright with authentic human interactions:
    - DOM Perception & Clickable Element Detection
    - Human-like Bézier Mouse Movement & Micro-Jitter
    - Realistic Physical Hover & Click Dwell
    - Trusted Native Keystroke Dispatching
    - Multi-layer fallbacks for 100% click delivery
    """

    @staticmethod
    def get_bezier_curve(
        p0: Tuple[float, float],
        p1: Tuple[float, float],
        p2: Tuple[float, float],
        p3: Tuple[float, float],
        num_points: int = 20
    ) -> List[Tuple[float, float]]:
        """Generates smooth cubic Bézier trajectory with human micro-jitter."""
        points = []
        for i in range(num_points + 1):
            t = i / num_points
            t_eased = t * t * (3 - 2 * t)
            x = (1 - t_eased)**3 * p0[0] + 3 * (1 - t_eased)**2 * t_eased * p1[0] + 3 * (1 - t_eased) * t_eased**2 * p2[0] + t_eased**3 * p3[0]
            y = (1 - t_eased)**3 * p0[1] + 3 * (1 - t_eased)**2 * t_eased * p1[1] + 3 * (1 - t_eased) * t_eased**2 * p2[1] + t_eased**3 * p3[1]
            jitter_x = random.uniform(-0.8, 0.8)
            jitter_y = random.uniform(-0.8, 0.8)
            points.append((x + jitter_x, y + jitter_y))
        return points

    @staticmethod
    async def human_mouse_move(page: Page, target_x: float, target_y: float):
        """Moves mouse to target coordinates using an authentic human-like Bézier trajectory."""
        try:
            curr = getattr(page, "_last_mouse_pos", (250.0, 300.0))
            start_x, start_y = curr
            mid_x = (start_x + target_x) / 2
            mid_y = (start_y + target_y) / 2
            ctrl1 = (start_x + random.uniform(-60, 60), mid_y + random.uniform(-40, 40))
            ctrl2 = (mid_x + random.uniform(-40, 40), target_y + random.uniform(-30, 30))
            steps = random.randint(14, 22)
            points = SmartBrowserActions.get_bezier_curve((start_x, start_y), ctrl1, ctrl2, (target_x, target_y), steps)
            for px, py in points:
                await page.mouse.move(px, py)
                await asyncio.sleep(random.uniform(0.008, 0.020))
            page._last_mouse_pos = (target_x, target_y)
        except Exception:
            try:
                await page.mouse.move(target_x, target_y)
                page._last_mouse_pos = (target_x, target_y)
            except Exception:
                pass

    @staticmethod
    async def human_click(page: Page, locator: Locator, wait_after_sec: float = 0.4) -> bool:
        """Moves mouse organically to locator and clicks with authentic down/up dwell."""
        try:
            if await locator.count() == 0 or not await locator.first.is_visible():
                return False
            await locator.first.scroll_into_view_if_needed()
            await asyncio.sleep(0.1)
            coords = await SmartBrowserActions.get_element_center_coordinates(page, locator)
            if coords:
                await SmartBrowserActions.human_mouse_move(page, coords[0], coords[1])
                await asyncio.sleep(random.uniform(0.08, 0.16))
                await page.mouse.down()
                await asyncio.sleep(random.uniform(0.06, 0.10))
                await page.mouse.up()
                await asyncio.sleep(wait_after_sec)
                return True
            else:
                await locator.first.click()
                await asyncio.sleep(wait_after_sec)
                return True
        except Exception:
            try:
                await locator.first.click(force=True)
                await asyncio.sleep(wait_after_sec)
                return True
            except Exception:
                return False

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
        Layer 1: Playwright locator bounding-box -> human mouse move & click at center coords
        Layer 2: Playwright locator standard click (force=True)
        Layer 3: DOM tree text/role inspection -> evaluate getBoundingClientRect -> mouse.click
        """
        container = scope_locator if scope_locator is not None else page

        # Layer 1 & 2: Try provided selectors
        for sel in selectors:
            try:
                loc = container.locator(sel).first
                if await loc.count() > 0 and await loc.is_visible():
                    await loc.scroll_into_view_if_needed()
                    await asyncio.sleep(0.1)
                    
                    # Try native center-coordinate human click
                    coords = await SmartBrowserActions.get_element_center_coordinates(page, loc)
                    if coords:
                        await SmartBrowserActions.human_mouse_move(page, coords[0], coords[1])
                        await asyncio.sleep(0.06)
                        await page.mouse.down()
                        await asyncio.sleep(0.07)
                        await page.mouse.up()
                        await asyncio.sleep(wait_after_sec)
                        return True

                    # Fallback to Playwright force click
                    await loc.click(timeout=timeout_ms, force=True)
                    await asyncio.sleep(wait_after_sec)
                    return True
            except Exception:
                continue

        # Layer 3: Deep DOM search via JS for text_keywords
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
                                    if (typeof el.click === 'function') el.click();
                                    return { success: true, x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
                                }
                            }
                        }
                    }
                    return { success: false };
                }''', text_keywords)

                if clicked and clicked.get("success"):
                    if "x" in clicked and "y" in clicked:
                        try:
                            await SmartBrowserActions.human_mouse_move(page, clicked["x"], clicked["y"])
                            await page.mouse.down()
                            await asyncio.sleep(0.06)
                            await page.mouse.up()
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
        delay_ms: int = 45,
        clear_first: bool = True
    ) -> bool:
        """
        Types text with authentic human cadence and trusted Chromium keypresses.
        """
        try:
            if await locator.count() == 0:
                return False
            await locator.first.scroll_into_view_if_needed()
            coords = await SmartBrowserActions.get_element_center_coordinates(page, locator)
            if coords:
                await SmartBrowserActions.human_mouse_move(page, coords[0], coords[1])
                await asyncio.sleep(0.08)
                await page.mouse.down()
                await asyncio.sleep(0.07)
                await page.mouse.up()
            else:
                await locator.first.click()
            await asyncio.sleep(0.12)

            if clear_first:
                # Select all and delete
                await page.keyboard.press("Control+A")
                await page.keyboard.press("Backspace")
                await asyncio.sleep(0.08)

            # Type with natural delay (trusted native events)
            await locator.first.press_sequentially(text, delay=delay_ms)
            await asyncio.sleep(0.15)
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
            slot_loc = target_card.locator(", ".join(slot_selectors)).first
            if await slot_loc.count() > 0 and await slot_loc.is_visible():
                coords = await SmartBrowserActions.get_element_center_coordinates(page, slot_loc)
                if coords:
                    await SmartBrowserActions.human_mouse_move(page, coords[0], coords[1])
                    await page.mouse.down()
                    await asyncio.sleep(0.06)
                    await page.mouse.up()
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
                    await SmartBrowserActions.human_mouse_move(page, coords[0], coords[1])
                    await asyncio.sleep(0.08)
                    await page.mouse.down()
                    await asyncio.sleep(0.07)
                    await page.mouse.up()
                else:
                    await bn.click(force=True)
                book_now_clicked = True
                await asyncio.sleep(1.5)
                break
            await asyncio.sleep(0.5)

        # 5. Handle PrimeNG Confirmation Dialogs & Check Navigation
        for _ in range(25):
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
