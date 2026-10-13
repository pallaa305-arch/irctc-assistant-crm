import pytest
from datetime import datetime, date
from app.database.connection import SessionLocal
from app.database.models import Booking

def test_booking_tatkal_schema_fields():
    db = SessionLocal()
    ref = "BK-TEST-TATKAL-SCHEMA-001"
    old = db.query(Booking).filter(Booking.booking_ref == ref).first()
    if old:
        db.delete(old)
        db.commit()

    trigger_dt = datetime(2026, 10, 15, 9, 58, 0)
    booking = Booking(
        booking_ref=ref,
        from_station="NDLS",
        to_station="MMCT",
        journey_date=date(2026, 10, 16),
        journey_class="3A",
        status="SCHEDULED_TATKAL",
        is_tatkal=True,
        tatkal_quota_type="TQ",
        scheduled_trigger_time=trigger_dt,
        preferred_payment_mode="UPI_QR",
        master_list_synced=False
    )
    db.add(booking)
    db.commit()

    saved = db.query(Booking).filter(Booking.booking_ref == ref).first()
    try:
        assert saved is not None
        assert saved.is_tatkal is True
        assert saved.tatkal_quota_type == "TQ"
        assert saved.scheduled_trigger_time == trigger_dt
        assert saved.preferred_payment_mode == "UPI_QR"
        assert saved.master_list_synced is False
    finally:
        db.delete(saved)
        db.commit()
        db.close()
