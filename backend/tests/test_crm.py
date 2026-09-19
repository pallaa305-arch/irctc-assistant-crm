from datetime import date, datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database.connection import Base
from app.database.models import Booking, BookingPassenger
from app.crm.crm_service import get_dashboard_stats, filter_bookings

def setup_in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return TestingSessionLocal()

def test_dashboard_stats_and_filtering():
    db = setup_in_memory_db()

    # Create test bookings
    b1 = Booking(
        booking_ref="BK-TEST-1",
        pnr="1234567890",
        from_station="NDLS",
        to_station="CNB",
        journey_date=date.today(),
        status="CONFIRMED",
        fare=850.0,
        passenger_count=1
    )
    b2 = Booking(
        booking_ref="BK-TEST-2",
        from_station="NDLS",
        to_station="BPL",
        journey_date=date.today(),
        status="FAILED",
        fare=1200.0,
        passenger_count=2
    )
    db.add_all([b1, b2])
    db.commit()

    stats = get_dashboard_stats(db)
    assert stats["total_bookings"] == 2
    assert stats["successful_bookings"] == 1
    assert stats["failed_bookings"] == 1
    assert stats["total_spend"] == 850.0

    filtered = filter_bookings(db, query_str="CNB")
    assert filtered["total"] == 1
    assert filtered["items"][0].booking_ref == "BK-TEST-1"
