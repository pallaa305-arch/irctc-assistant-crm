import time
import pytest
from app.utils.image_gen import generate_mock_captcha_image
from app.automation.captcha_solver import fast_solve_captcha, captcha_solver
from app.automation.flow_state import BookingSessionState


def test_fast_captcha_solver_speed_and_format():
    """Verify captcha solving executes in <50ms and returns valid format."""
    mock_chars = "7K2X9"
    img_bytes = generate_mock_captcha_image(mock_chars)

    t0 = time.perf_counter()
    predicted, confidence = fast_solve_captcha(img_bytes)
    t_elapsed = (time.perf_counter() - t0) * 1000

    assert t_elapsed < 50.0, f"Execution took too long: {t_elapsed:.2f}ms"
    assert isinstance(predicted, str)
    assert len(predicted) >= 4
    assert 0.0 <= confidence <= 1.0


def test_session_state_suggested_captcha_confirmation():
    """Verify session state accepts 'OK' or 'YES' to confirm auto-suggested captcha."""
    state = BookingSessionState("BK-TEST-CAPTCHA-1")
    state.pause_for_user(
        prompt="Solve CAPTCHA",
        is_payment=False,
        input_type="CAPTCHA",
        suggested_value="P9X2M"
    )

    assert state.suggested_captcha == "P9X2M"
    assert state.waiting_input_type == "CAPTCHA"

    # Simulate user sending quick "OK" confirmation
    state.provide_user_input("OK")

    assert state.user_input_value == "P9X2M"
    assert state.status == "IN_PROGRESS"
    assert state.is_paused is False
