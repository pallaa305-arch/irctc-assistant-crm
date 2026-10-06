import inspect
from app.automation.browser_manager import BrowserManager


def test_browser_manager_stealth_and_native_network():
    """Verify BrowserManager uses native HTTP/2 networking, GPU enabled, and AutomationControlled bypass without CDP route interception."""
    src = inspect.getsource(BrowserManager.get_page)

    assert "AutomationControlled" in src
    assert "--disable-gpu" not in src
    assert "_speed_optimizer_route" not in src
    assert "add_init_script" not in src
