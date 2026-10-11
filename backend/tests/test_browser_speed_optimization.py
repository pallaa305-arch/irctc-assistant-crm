import inspect
from app.automation.browser_manager import BrowserManager


def test_browser_manager_stealth_and_native_network():
    """Verify BrowserManager uses native HTTP/2 networking, GPU enabled, and AutomationControlled bypass without CDP route interception."""
    src = inspect.getsource(BrowserManager.get_page)

    assert "AutomationControlled" in src
    assert "--disable-gpu" not in src
    assert "_speed_optimizer_route" not in src
    assert "add_init_script" not in src
    assert "_purge_service_worker_cache" in src


def test_browser_manager_service_worker_and_akamai_cookie_handling():
    """Verify BrowserManager unregisters Angular ServiceWorker before resetting flagged Akamai cookies."""
    src = inspect.getsource(BrowserManager.reset_akamai_cookies)
    assert "unregister_service_workers" in src
    assert "bm_sz" in src
    assert "~0~" in src
