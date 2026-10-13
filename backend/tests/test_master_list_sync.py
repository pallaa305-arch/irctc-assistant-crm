import pytest
from datetime import date, datetime
from unittest.mock import AsyncMock, patch, MagicMock

from app.automation.master_list_sync import (
    sync_passengers_to_irctc_master_list,
    normalize_passenger_master_data
)
from app.database.connection import SessionLocal
from app.database.models import Booking, BookingPassenger

def test_normalize_passenger_master_data():
    raw_p = {
        "name": "Amit Kumar  ",
        "age": 30,
        "gender": "male",
        "berth_preference": "lb",
        "food_choice": "Veg"
    }
    norm = normalize_passenger_master_data(raw_p)
    assert norm["name"] == "AMIT KUMAR"
    assert norm["age"] == 30
    assert norm["gender"] == "M"
    assert norm["berth_preference"] == "LB"
    assert norm["food_choice"] == "V"

    # Default fallbacks
    empty_p = {}
    norm_empty = normalize_passenger_master_data(empty_p)
    assert norm_empty["name"] == ""
    assert norm_empty["age"] == 0
    assert norm_empty["gender"] == "M"
    assert norm_empty["berth_preference"] == "NONE"

@pytest.mark.asyncio
async def test_sync_passengers_mock_mode():
    db = SessionLocal()
    ref = "BK-TEST-SYNC-001"
    old = db.query(Booking).filter(Booking.booking_ref == ref).first()
    if old:
        db.delete(old)
        db.commit()

    b = Booking(
        booking_ref=ref,
        from_station="NDLS",
        to_station="MMCT",
        journey_date=date(2026, 10, 20),
        journey_class="3A",
        status="SCHEDULED_TATKAL",
        is_tatkal=True,
        master_list_synced=False
    )
    db.add(b)
    db.commit()
    b_id = b.id

    passengers = [
        {"name": "Suresh Raina", "age": 35, "gender": "M", "berth_preference": "SL"},
        {"name": "Pooja Raina", "age": 32, "gender": "F", "berth_preference": "SU"}
    ]

    try:
        # Live mode False -> Mock mode
        res = await sync_passengers_to_irctc_master_list(
            passengers=passengers,
            booking_ref=ref,
            db=db,
            live_mode=False
        )
        assert res["success"] is True
        assert res["synced_count"] == 2
        assert res["mode"] == "MOCK"

        db.refresh(b)
        assert b.master_list_synced is True
    finally:
        b_clean = db.query(Booking).filter(Booking.id == b_id).first()
        if b_clean:
            db.delete(b_clean)
            db.commit()
        db.close()

@pytest.mark.asyncio
async def test_sync_passengers_live_mode_with_mocked_playwright():
    db = SessionLocal()
    ref = "BK-TEST-SYNC-002"
    old = db.query(Booking).filter(Booking.booking_ref == ref).first()
    if old:
        db.delete(old)
        db.commit()

    b = Booking(
        booking_ref=ref,
        from_station="NDLS",
        to_station="BPL",
        journey_date=date(2026, 10, 21),
        journey_class="2A",
        status="SCHEDULED_TATKAL",
        is_tatkal=True,
        master_list_synced=False
    )
    db.add(b)
    db.commit()
    b_id = b.id

    passengers = [
        {"name": "Vikas Gupta", "age": 29, "gender": "M", "berth_preference": "LB"}
    ]

    mock_page = AsyncMock()
    mock_page.url = "https://www.irctc.co.in/nget/profile/add-passenger"
    mock_page.inner_text = AsyncMock(return_value="Existing Passenger List")
    mock_page.fill = AsyncMock()
    mock_page.click = AsyncMock()
    mock_page.wait_for_timeout = AsyncMock()

    try:
        with patch("app.automation.master_list_sync.browser_manager.get_page", new_callable=AsyncMock) as mock_get_page, \
             patch("app.automation.master_list_sync.ensure_authenticated_session", new_callable=AsyncMock) as mock_auth:
            
            mock_auth.return_value = True
            mock_get_page.return_value = mock_page
            res = await sync_passengers_to_irctc_master_list(
                passengers=passengers,
                booking_ref=ref,
                db=db,
                live_mode=True
            )
            assert res["success"] is True
            assert res["synced_count"] == 1
            assert res["mode"] == "LIVE"

            db.refresh(b)
            assert b.master_list_synced is True
    finally:
        b_clean = db.query(Booking).filter(Booking.id == b_id).first()
        if b_clean:
            db.delete(b_clean)
            db.commit()
        db.close()
