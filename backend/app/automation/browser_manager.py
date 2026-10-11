import os
import shutil
import asyncio
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright
from app.config import settings, BROWSER_PROFILE_DIR


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
    owner: Optional[str] = None

    def claim(self, owner: str):
        # No await between checking and assigning: atomic on the application event loop.
        if self.owner and self.owner != owner:
            raise RuntimeError("IRCTC browser is already reserved by another booking. Finish or cancel it first.")
        self.owner = owner
        self.is_busy = True

    def release(self, owner: str):
        if self.owner == owner:
            self.owner = None
            self.is_busy = False

    @classmethod
    def get_instance(cls) -> 'BrowserManager':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @staticmethod
    def _purge_service_worker_cache(profile_dir: str):
        """
        Removes cached Angular ServiceWorker (ngsw-worker.js) storage from the profile
        so /nget/train-search always hits Akamai's edge server and receives fresh bm_sz / _abck cookies.
        """
        sw_dir = os.path.join(profile_dir, "Default", "Service Worker")
        if os.path.exists(sw_dir):
            try:
                shutil.rmtree(sw_dir, ignore_errors=True)
            except Exception:
                pass

    async def get_page(self, *, owner: Optional[str] = None, foreground: bool = True) -> Page:
        if self.owner and self.owner != owner:
            raise RuntimeError("IRCTC browser belongs to another active booking.")
        if self.page and not self.page.is_closed():
            try:
                if foreground:
                    await self.page.bring_to_front()
                    focus_browser_window()
            except Exception:
                pass
            return self.page

        if not self.playwright:
            self.playwright = await async_playwright().start()

        profile_dir = str(BROWSER_PROFILE_DIR)
        if not self.context:
            self._purge_service_worker_cache(profile_dir)

            launch_args = {
                "user_data_dir": profile_dir,
                "headless": settings.BROWSER_HEADLESS,
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
                    "--disable-dev-shm-usage"
                ],
                "locale": "en-US"
            }
            if settings.BROWSER_SLOW_MO > 0:
                launch_args["slow_mo"] = settings.BROWSER_SLOW_MO
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
                try:
                    # Fallback to bundled Playwright Chromium
                    self.context = await self.playwright.chromium.launch_persistent_context(
                        **launch_args
                    )
                except Exception as e_chromium:
                    err_str = str(e_chromium)
                    if "already in use" in err_str or "existing browser session" in err_str:
                        lock_files = ["SingletonLock", "SingletonCookie", "SingletonSocket"]
                        for lf in lock_files:
                            lp = os.path.join(profile_dir, lf)
                            if os.path.exists(lp):
                                try:
                                    os.remove(lp)
                                except Exception:
                                    pass
                        self._purge_service_worker_cache(profile_dir)
                        await asyncio.sleep(1.0)
                        self.context = await self.playwright.chromium.launch_persistent_context(
                            **launch_args
                        )
                    else:
                        raise e_chromium

        # Preserve native HTTP/2 connection pooling & multiplexing (no CDP route interception)
        # Real Chrome with --disable-blink-features=AutomationControlled leaves clean navigator.webdriver

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
            if foreground:
                await self.page.bring_to_front()
                focus_browser_window()
        except Exception:
            pass

        return self.page

    async def unregister_service_workers(self):
        """Unregisters Angular ServiceWorker (ngsw-worker.js) and clears CacheStorage in the active page."""
        if not self.page or self.page.is_closed():
            return
        try:
            await self.page.evaluate("""async () => {
                try {
                    if ('serviceWorker' in navigator) {
                        const regs = await navigator.serviceWorker.getRegistrations();
                        for (const r of regs) {
                            await r.unregister();
                        }
                    }
                } catch (e) {}
                try {
                    if ('caches' in window) {
                        const keys = await caches.keys();
                        for (const k of keys) {
                            await caches.delete(k);
                        }
                    }
                } catch (e) {}
            }""")
        except Exception:
            pass

    async def reset_akamai_cookies(self, force: bool = False) -> bool:
        """
        Clears flagged or blacklisted Akamai Bot Manager cookies (_abck, bm_*)
        when force=True (after HTTP 403) or when _abck is in a flagged (~-1~) state or bm_sz is missing.
        Also unregisters Angular ServiceWorker so the next navigation hits Akamai's edge server.
        Preserves valid (~0~) cookies during normal operation.
        """
        if not self.context:
            return False
        try:
            await self.unregister_service_workers()
            cookies = await self.context.cookies(["https://www.irctc.co.in"])
            abck = next((c["value"] for c in cookies if c["name"] == "_abck"), "")
            bm_sz = next((c["value"] for c in cookies if c["name"] == "bm_sz"), "")
            is_valid = ("~0~" in abck) and bool(bm_sz)
            if not force and is_valid:
                return False

            akamai_names = {
                "_abck", "bm_sz", "bm_sv", "bm_s", "bm_so", "bm_lso",
                "ak_bmsc", "PIM-SESSION-ID", "X-AK-PIM-INJECT"
            }
            for name in akamai_names:
                try:
                    await self.context.clear_cookies(name=name)
                except Exception:
                    pass
            return True
        except Exception:
            return False

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
            self.owner = None


browser_manager = BrowserManager.get_instance()
