import pytest
from app.automation.flow_state import BookingSessionState

@pytest.mark.asyncio
async def test_session_state_transitions_and_pause():
    session = BookingSessionState("BK-TEST-SESSION")
    assert session.stage == "PREPARING"
    assert session.status == "INITIATED"
    assert not session.is_paused

    # Simulate reaching CAPTCHA
    session.set_stage("WAITING_MANUAL")
    session.pause_for_user("Please solve CAPTCHA in browser", is_payment=False)
    assert session.is_paused
    assert session.status == "WAITING_MANUAL"
    assert "CAPTCHA" in session.manual_prompt

    # Simulate user resuming
    session.user_resumed()
    assert not session.is_paused
    assert session.status == "IN_PROGRESS"
    assert session.continue_event.is_set()

    # Simulate payment handoff
    session.pause_for_user("Complete bank payment", is_payment=True)
    assert session.is_paused
    assert session.status == "PAYMENT_PENDING"

    # Simulate user cancelling
    session.user_cancelled("User aborted")
    assert not session.is_paused
    assert session.status == "CANCELLED"
    assert session.cancel_event.is_set()

@pytest.mark.asyncio
async def test_session_state_with_screenshot():
    session = BookingSessionState("BK-TEST-SCREENSHOT")
    dummy_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    session.pause_for_user("Enter CAPTCHA", is_payment=False, input_type="CAPTCHA", screenshot_bytes=dummy_png)
    assert session.latest_screenshot_bytes == dummy_png
    assert session.waiting_input_type == "CAPTCHA"
    assert session.is_paused
