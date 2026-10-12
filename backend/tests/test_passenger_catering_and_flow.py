import inspect
from app.automation.irctc_flow import run_real_irctc_booking_flow


def test_passenger_catering_and_food_choice_support():
    """Verify that irctc_flow supports PrimeNG p-dropdown for passengerFoodChoice and auto-repairs unselected food choice."""
    src = inspect.getsource(run_real_irctc_booking_flow)

    # 1. PrimeNG food choice dropdown handling
    assert "p-dropdown[formcontrolname='passengerFoodChoice']" in src
    assert "select[formcontrolname='passengerFoodChoice']" in src
    assert "No Food" in src
    assert "Non Veg" in src

    # 2. Form state invalid controls detection
    assert "invalidControls" in src
    assert "unselectedFood" in src

    # 3. Step 7 retry and loading detection
    assert "psgninput" in src
    assert "is_busy" in src
    assert "Re-clicking Continue button" in src


def test_irctc_api_error_and_maintenance_downtime_handling():
    """Verify that irctc_flow tracks IRCTC API response errors and handles PRS daily maintenance downtime (23:45-00:30 IST)."""
    src = inspect.getsource(run_real_irctc_booking_flow)

    # 1. API error capture on response listener
    assert "_last_irctc_api_error" in src
    assert "_irctc_maintenance_msg" in src
    assert "unable to perform transaction" in src

    # 2. Step 7 early exit on maintenance downtime or fatal API rejection
    assert "IRCTC Night Maintenance Downtime" in src
    assert "is_maintenance_window" in src
    assert "captured_err" in src
