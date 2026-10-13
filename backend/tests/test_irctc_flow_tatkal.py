import pytest
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from app.automation.irctc_flow import wait_for_tatkal_opening_sharp
from app.automation.flow_state import BookingSessionState
from app.database.connection import SessionLocal
from app.database.models import Booking

@pytest.mark.asyncio
async def test_wait_for_tatkal_opening_sharp_skips_non_tatkal():
    booking = Booking(
        booking_ref="BK-NON-TATKAL",
        is_tatkal=False,
        journey_date=date(2026, 10, 20),
        journey_class="3A"
    )
    db = SessionLocal()
    session_state = BookingSessionState("BK-NON-TATKAL")

    try:
        # Should return immediately without waiting
        await wait_for_tatkal_opening_sharp(booking, db, "BK-NON-TATKAL", session_state)
    finally:
        db.close()

@pytest.mark.asyncio
async def test_wait_for_tatkal_opening_sharp_tatkal_past_opening():
    # If opening time has already passed, should proceed immediately
    past_date = date.today() + timedelta(days=1)
    booking = Booking(
        booking_ref="BK-TATKAL-PAST",
        is_tatkal=True,
        journey_date=past_date,
        journey_class="3A"
    )
    db = SessionLocal()
    session_state = BookingSessionState("BK-TATKAL-PAST")

    # Mock compute_tatkal_timings to return an opening time in the past
    mock_timings = {
        "opening_time": datetime.now() - timedelta(seconds=5),
        "warmup_time": datetime.now() - timedelta(minutes=2)
    }

    try:
        with patch("app.automation.tatkal_scheduler.compute_tatkal_timings", return_value=mock_timings):
            await wait_for_tatkal_opening_sharp(booking, db, "BK-TATKAL-PAST", session_state)
            assert session_state.status != "FAILED"
    finally:
        db.close()
