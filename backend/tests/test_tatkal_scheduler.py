import pytest
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from app.automation.tatkal_scheduler import (
    compute_tatkal_timings,
    get_due_tatkal_bookings,
    check_and_trigger_due_tatkal_bookings
)
from app.database.connection import SessionLocal
from app.database.models import Booking

def test_compute_tatkal_timings_ac_and_non_ac():
    # AC Class (3A) -> 10:00 AM opening, 09:58 AM warmup, T-1 day
    j_date = date(2026, 10, 20)
    timing_ac = compute_tatkal_timings(j_date, "3A")
    assert timing_ac["category"] == "AC"
    assert timing_ac["booking_date"] == date(2026, 10, 19)
    assert timing_ac["opening_time"] == datetime(2026, 10, 19, 10, 0, 0)
    assert timing_ac["warmup_time"] == datetime(2026, 10, 19, 9, 58, 0)

    # 2A / CC
    timing_cc = compute_tatkal_timings(j_date, "CC")
    assert timing_cc["category"] == "AC"
    assert timing_cc["opening_time"].hour == 10

    # Non-AC Class (SL) -> 11:00 AM opening, 10:58 AM warmup
    timing_sl = compute_tatkal_timings(j_date, "SL")
    assert timing_sl["category"] == "NON_AC"
    assert timing_sl["booking_date"] == date(2026, 10, 19)
    assert timing_sl["opening_time"] == datetime(2026, 10, 19, 11, 0, 0)
    assert timing_sl["warmup_time"] == datetime(2026, 10, 19, 10, 58, 0)

    # 2S
    timing_2s = compute_tatkal_timings(j_date, "2S")
    assert timing_2s["category"] == "NON_AC"
    assert timing_2s["opening_time"].hour == 11

def test_get_due_tatkal_bookings():
    db = SessionLocal()
    ref_due = "BK-TEST-DUE-001"
    ref_future = "BK-TEST-FUTURE-002"

    for r in [ref_due, ref_future]:
        old = db.query(Booking).filter(Booking.booking_ref == r).first()
        if old:
            db.delete(old)
    db.commit()

    now = datetime(2026, 10, 19, 9, 58, 5)

    b_due = Booking(
        booking_ref=ref_due,
        from_station="NDLS",
        to_station="MMCT",
        journey_date=date(2026, 10, 20),
        journey_class="3A",
        status="SCHEDULED_TATKAL",
        is_tatkal=True,
        scheduled_trigger_time=datetime(2026, 10, 19, 9, 58, 0)
    )
    b_future = Booking(
        booking_ref=ref_future,
        from_station="NDLS",
        to_station="MMCT",
        journey_date=date(2026, 10, 20),
        journey_class="3A",
        status="SCHEDULED_TATKAL",
        is_tatkal=True,
        scheduled_trigger_time=datetime(2026, 10, 19, 10, 58, 0)
    )
    db.add_all([b_due, b_future])
    db.commit()

    try:
        due_list = get_due_tatkal_bookings(db, as_of=now)
        due_refs = [b.booking_ref for b in due_list]
        assert ref_due in due_refs
        assert ref_future not in due_refs
    finally:
        for r in [ref_due, ref_future]:
            b = db.query(Booking).filter(Booking.booking_ref == r).first()
            if b:
                db.delete(b)
        db.commit()
        db.close()

@pytest.mark.asyncio
async def test_check_and_trigger_due_tatkal_bookings():
    db = SessionLocal()
    ref = "BK-TEST-TRIGGER-003"
    old = db.query(Booking).filter(Booking.booking_ref == ref).first()
    if old:
        db.delete(old)
        db.commit()

    b = Booking(
        booking_ref=ref,
        from_station="NDLS",
        to_station="CNB",
        journey_date=date(2026, 10, 20),
        journey_class="3A",
        status="SCHEDULED_TATKAL",
        is_tatkal=True,
        scheduled_trigger_time=datetime(2026, 10, 19, 9, 58, 0)
    )
    db.add(b)
    db.commit()
    b_id = b.id

    mock_trigger = AsyncMock()

    try:
        with patch("app.automation.tatkal_scheduler.send_telegram_message", new_callable=AsyncMock) as mock_send_tg:
            triggered = await check_and_trigger_due_tatkal_bookings(
                db, 
                as_of=datetime(2026, 10, 19, 9, 58, 10),
                trigger_func=mock_trigger
            )
            assert len(triggered) == 1
            assert triggered[0].booking_ref == ref
            assert mock_trigger.called
            assert mock_send_tg.called
            # Status should transition
            db.refresh(b)
            assert b.status == "IN_PROGRESS"
    finally:
        b_clean = db.query(Booking).filter(Booking.id == b_id).first()
        if b_clean:
            db.delete(b_clean)
            db.commit()
        db.close()
