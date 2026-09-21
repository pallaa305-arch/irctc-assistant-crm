import pytest
import asyncio
from datetime import date
from fastapi.testclient import TestClient
from app.main import app
from app.database.connection import SessionLocal, init_db
from app.database.models import Booking, BookingPassenger, Passenger, SavedJourney
from app.automation.flow_state import get_session

@pytest.mark.asyncio
async def test_full_booking_e2e():
    init_db()
    db_cleanup = SessionLocal()
    db_cleanup.query(BookingPassenger).delete()
    db_cleanup.query(Booking).delete()
    db_cleanup.commit()
    db_cleanup.close()
    with TestClient(app) as client:
        # 1. Test Passenger CRUD
        p_resp = client.post("/api/passengers", json={
            "name": "Amit Sharma",
            "age": 34,
            "gender": "M",
            "berth_preference": "LB",
            "food_preference": "V",
            "senior_citizen": False,
            "is_default": True
        })
        assert p_resp.status_code == 200
        p_data = p_resp.json()
        assert p_data["name"] == "Amit Sharma"

        # 2. Test Saved Journey CRUD
        j_resp = client.post("/api/journeys", json={
            "label": "Delhi to Bhopal Shatabdi",
            "from_station": "NDLS",
            "to_station": "BPL",
            "boarding_station": "NDLS",
            "train_preference": "12002",
            "preferred_class": "CC",
            "preferred_quota": "GN"
        })
        assert j_resp.status_code == 200

        # 3. Start a Demo Booking
        book_resp = client.post("/api/bookings/start", json={
            "from_station": "NDLS",
            "to_station": "BPL",
            "boarding_station": "NDLS",
            "journey_date": str(date(2026, 10, 15)),
            "journey_class": "CC",
            "quota": "GN",
            "train_preference": "12002",
            "contact_mobile": "9876543210",
            "contact_email": "amit@example.com",
            "passengers": [
                {
                    "name": "Amit Sharma",
                    "age": 34,
                    "gender": "M",
                    "berth_preference": "LB",
                    "food_preference": "V"
                }
            ],
            "demo_mode": True
        })
        assert book_resp.status_code == 200
        b_data = book_resp.json()
        ref = b_data["booking_ref"]

        # 4. Duplicate booking check verification (same passenger on same route/date)
        dup_resp = client.post("/api/bookings/start", json={
            "from_station": "NDLS",
            "to_station": "BPL",
            "journey_date": str(date(2026, 10, 15)),
            "passengers": [{"name": "Amit Sharma", "age": 34, "gender": "M"}]
        })
        assert dup_resp.status_code == 409

        # 5. Check state machine progress
        session_state = get_session(ref)
        assert session_state is not None

        # Wait for the flow to reach the first manual pause (CAPTCHA/Review)
        for _ in range(40):
            if session_state.is_paused:
                break
            await asyncio.sleep(0.5)

        assert session_state.is_paused
        assert session_state.status == "WAITING_MANUAL"

        # 6. Simulate user manual solve & click continue
        action_resp = client.post(f"/api/bookings/action/{ref}", json={"action": "continue"})
        assert action_resp.status_code == 200

        # Wait for the flow to reach the second manual pause (Payment Handoff)
        for _ in range(40):
            if session_state.is_paused:
                break
            await asyncio.sleep(0.5)

        assert session_state.is_paused
        assert session_state.status == "PAYMENT_PENDING"

        # 7. Simulate user completing payment & clicking continue
        pay_resp = client.post(f"/api/bookings/action/{ref}", json={"action": "continue"})
        assert pay_resp.status_code == 200

        # Wait for completion & confirmation
        for _ in range(40):
            if session_state.stage == "COMPLETED":
                break
            await asyncio.sleep(0.5)

        assert session_state.stage == "COMPLETED"
        assert session_state.status == "CONFIRMED"

        # 8. Verify CRM record in database
        db = SessionLocal()
        saved_booking = db.query(Booking).filter(Booking.booking_ref == ref).first()
        assert saved_booking is not None
        assert saved_booking.pnr is not None
        assert len(saved_booking.pnr) == 10
        assert saved_booking.status == "CONFIRMED"
        db.close()

        # 9. Verify stats endpoint
        stats_resp = client.get("/api/crm/stats")
        assert stats_resp.status_code == 200
        assert stats_resp.json()["successful_bookings"] >= 1
