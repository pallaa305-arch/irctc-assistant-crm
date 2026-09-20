import pytest
from httpx import AsyncClient, ASGITransport
from datetime import date
from app.main import app
from app.database.connection import SessionLocal
from app.database.models import Booking, BookingPassenger
from app.services.pdf_service import pdf_service

@pytest.mark.asyncio
async def test_pdf_service_ticket_and_invoice_generation():
    booking_data = {
        "pnr": "2451234567",
        "train_number": "12952",
        "train_name": "NEW DELHI TEJAS RAJDHANI",
        "from_station": "NDLS",
        "to_station": "MMCT",
        "journey_date": "25/10/2026",
        "journey_class": "3A",
        "quota": "GENERAL (GN)",
        "fare": 2150.0,
        "booking_ref": "BK-20261025-TEST01",
        "booking_time": "25-Oct-2026 10:00:00"
    }
    passengers = [
        {
            "name": "Deepak Sharma",
            "age": 28,
            "gender": "M",
            "allocated_seat": "B4-45 [MB]",
            "status": "CNF"
        }
    ]

    # Test Ticket PDF Generation
    ticket_pdf = pdf_service.generate_ticket_pdf(booking_data, passengers, save_to_disk=True)
    assert isinstance(ticket_pdf, bytes)
    assert len(ticket_pdf) > 1000
    assert ticket_pdf.startswith(b"%PDF")

    # Test Invoice PDF Generation
    invoice_pdf = pdf_service.generate_invoice_pdf(booking_data, passengers, save_to_disk=True)
    assert isinstance(invoice_pdf, bytes)
    assert len(invoice_pdf) > 1000
    assert invoice_pdf.startswith(b"%PDF")

@pytest.mark.asyncio
async def test_booking_pdf_download_endpoints():
    # Insert test booking in DB
    db = SessionLocal()
    b = Booking(
        booking_ref="BK-TEST-PDF-001",
        from_station="NDLS",
        to_station="BSB",
        boarding_station="NDLS",
        journey_date=date(2026, 11, 15),
        journey_class="3A",
        quota="GN",
        train_number="22436",
        train_name="VANDE BHARAT",
        pnr="2898765432",
        passenger_count=1,
        fare=1750.0,
        status="CONFIRMED",
        payment_status="COMPLETED"
    )
    db.add(b)
    db.commit()
    db.refresh(b)

    bp = BookingPassenger(
        booking_id=b.id,
        name="Deepak",
        age=28,
        gender="M",
        berth_preference="NONE",
        allocated_seat="C4-25",
        status="CNF"
    )
    db.add(bp)
    db.commit()
    b_id = b.id
    db.close()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Download Ticket PDF endpoint
        res_ticket = await ac.get(f"/api/bookings/{b_id}/ticket-pdf")
        assert res_ticket.status_code == 200
        assert res_ticket.headers["content-type"] == "application/pdf"
        assert res_ticket.content.startswith(b"%PDF")
        assert "IRCTC_Ticket" in res_ticket.headers.get("content-disposition", "")

        # 2. Download Invoice PDF endpoint
        res_invoice = await ac.get(f"/api/bookings/{b_id}/invoice-pdf")
        assert res_invoice.status_code == 200
        assert res_invoice.headers["content-type"] == "application/pdf"
        assert res_invoice.content.startswith(b"%PDF")
        assert "Invoice_Bill" in res_invoice.headers.get("content-disposition", "")
