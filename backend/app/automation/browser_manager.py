import asyncio
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright
from app.config import settings

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
            return self.page

        if not self.playwright:
            self.playwright = await async_playwright().start()

        profile_dir = str(settings.DATA_DIR / "browser_profile")
        if not self.context:
            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                headless=settings.BROWSER_HEADLESS,
                slow_mo=settings.BROWSER_SLOW_MO,
                no_viewport=True,
                args=[
                    "--start-maximized",
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox"
                ],
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )

        if self.context.pages:
            self.page = self.context.pages[0]
        else:
            self.page = await self.context.new_page()

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
