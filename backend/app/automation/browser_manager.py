import asyncio
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright
from app.config import settings, BROWSER_PROFILE_DIR

import os

def focus_browser_window():
    """Forces the Chrome / IRCTC automation window to the foreground on Windows."""
    if os.name == 'nt':
        try:
            import ctypes
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            
            current_thread = kernel32.GetCurrentThreadId()
            fg_window = user32.GetForegroundWindow()
            fg_thread = user32.GetWindowThreadProcessId(fg_window, None)
            
            user32.AttachThreadInput(current_thread, fg_thread, True)
            user32.AllowSetForegroundWindow(-1)
            
            def enum_callback(hwnd, _):
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buff = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buff, length + 1)
                        title = buff.value.lower()
                        if "irctc" in title or "chrome" in title or "chromium" in title:
                            user32.ShowWindow(hwnd, 3)  # 3 = SW_MAXIMIZE
                            user32.SetForegroundWindow(hwnd)
                            user32.BringWindowToTop(hwnd)
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            user32.EnumWindows(WNDENUMPROC(enum_callback), 0)
            user32.AttachThreadInput(current_thread, fg_thread, False)
        except Exception:
            pass

class BrowserManager:
    """
    Manages a single visible browser session for low-spec optimization (4GB RAM target).
    Avoids spinning up multiple instances.
    """
    _instance: Optional['BrowserManager'] = None
    playwright: Optional[Playwright] = None
    browser: Optional[Browser] = None
    context: Optional[BrowserContext] = None
    page: Optional[Page] = None
    is_busy: bool = False

    @classmethod
    def get_instance(cls) -> 'BrowserManager':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def get_page(self) -> Page:
        if self.page and not self.page.is_closed():
            try:
                await self.page.bring_to_front()
                focus_browser_window()
            except Exception:
                pass
            return self.page

        if not self.playwright:
            self.playwright = await async_playwright().start()

        profile_dir = str(BROWSER_PROFILE_DIR)
        if not self.context:
            launch_args = {
                "user_data_dir": profile_dir,
                "headless": settings.BROWSER_HEADLESS,
                "slow_mo": settings.BROWSER_SLOW_MO,
                "bypass_csp": True,
                "ignore_https_errors": True,
                "no_viewport": not settings.BROWSER_HEADLESS,
                "ignore_default_args": ["--enable-automation"],
                "args": [
                    "--start-maximized",
                    "--disable-blink-features=AutomationControlled",
                    "--no-first-run",
                    "--disable-infobars",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu"
                ],
                "locale": "en-US"
            }
            if settings.BROWSER_HEADLESS:
                launch_args["viewport"] = {"width": 1366, "height": 768}

            if settings.PROXY_SERVER:
                proxy_dict = {"server": settings.PROXY_SERVER}
                if settings.PROXY_USERNAME:
                    proxy_dict["username"] = settings.PROXY_USERNAME
                if settings.PROXY_PASSWORD:
                    proxy_dict["password"] = settings.PROXY_PASSWORD
                launch_args["proxy"] = proxy_dict

            # Attempt to launch with real installed Google Chrome for visible window & recognition
            try:
                self.context = await self.playwright.chromium.launch_persistent_context(
                    **launch_args,
                    channel="chrome"
                )
            except Exception:
                # Fallback to bundled Playwright Chromium
                self.context = await self.playwright.chromium.launch_persistent_context(
                    **launch_args
                )

        if self.context.pages:
            self.page = self.context.pages[0]
        else:
            self.page = await self.context.new_page()

        # Attach auto-accept dialog handler to prevent Playwright freezes
        try:
            self.page.on("dialog", lambda d: asyncio.create_task(d.accept()))
            self.context.on("page", lambda p: p.on("dialog", lambda d: asyncio.create_task(d.accept())))
        except Exception:
            pass

        try:
            await self.page.bring_to_front()
            focus_browser_window()
        except Exception:
            pass

        return self.page

    async def close(self):
        try:
            if self.page and not self.page.is_closed():
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception:
            pass
        finally:
            self.page = None
            self.context = None
            self.browser = None
            self.playwright = None
            self.is_busy = False

browser_manager = BrowserManager.get_instance()
