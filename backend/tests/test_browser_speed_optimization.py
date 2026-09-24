import inspect
from app.automation.browser_manager import BrowserManager


def test_browser_manager_speed_optimization_flags():
    """Verify BrowserManager has bypass_csp, stealth flags, and route speed optimizer."""
    src = inspect.getsource(BrowserManager.get_page)

    assert "bypass_csp" in src
    assert "AutomationControlled" in src
    assert "_speed_optimizer_route" in src
    assert "captcha" in src.lower()
    assert "navigator.webdriver" in src
    assert "add_init_script" in src
