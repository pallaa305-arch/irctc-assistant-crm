import pytest
from datetime import date, datetime
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.database.connection import SessionLocal
from app.database.models import Booking, BookingPassenger
from app.automation.flow_state import get_or_create_session, clear_all_waiting_sessions, BookingSessionState
from app.notifications.telegram_bot_service import telegram_bot_service, user_chat_states, user_languages

client = TestClient(app)

@pytest.fixture(autouse=True)
def clean_state():
    clear_all_waiting_sessions()
    user_chat_states.clear()
    yield
    clear_all_waiting_sessions()
    user_chat_states.clear()

def test_download_ticket_and_invoice_by_booking_ref():
    db = SessionLocal()
    ref = "BK-TEST-VERIFY-001"
    old = db.query(Booking).filter(Booking.booking_ref == ref).first()
    if old:
        db.delete(old)
        db.commit()

    booking = Booking(
        booking_ref=ref,
        from_station="NDLS",
        to_station="MMCT",
        journey_date=date.today(),
        train_number="12952",
        train_name="Mumbai Rajdhani",
        journey_class="3A",
        status="CONFIRMED",
        payment_status="COMPLETED",
        fare=2150.0,
        pnr="2451239999",
        passenger_count=1,
        created_at=datetime.utcnow()
    )
    db.add(booking)
    db.commit()

    pax = BookingPassenger(
        booking_id=booking.id,
        name="Deepak Kataria",
        age=28,
        gender="M",
        allocated_seat="B3-45",
        status="CNF"
    )
    db.add(pax)
    db.commit()
    booking_id = booking.id
    db.close()

    try:
        # Test downloading by string booking_ref
        res_ticket = client.get(f"/api/bookings/{ref}/ticket-pdf")
        assert res_ticket.status_code == 200
        assert res_ticket.headers["content-type"] == "application/pdf"
        assert len(res_ticket.content) > 1000

        res_inv = client.get(f"/api/bookings/{ref}/invoice-pdf")
        assert res_inv.status_code == 200
        assert res_inv.headers["content-type"] == "application/pdf"
        assert len(res_inv.content) > 1000

        # Also by integer ID
        res_id = client.get(f"/api/bookings/{booking_id}/ticket-pdf")
        assert res_id.status_code == 200
    finally:
        db = SessionLocal()
        b_clean = db.query(Booking).filter(Booking.booking_ref == ref).first()
        if b_clean:
            db.delete(b_clean)
            db.commit()
        db.close()

@pytest.mark.asyncio
async def test_telegram_action_continue_sends_verification_notice():
    ref = "BK-TEST-VERIFY-002"
    session = get_or_create_session(ref)
    session.pause_for_user("Please pay via UPI", is_payment=True, input_type="PAYMENT")

    chat_id = "777888999"
    user_languages[chat_id] = "hinglish"

    with patch("app.notifications.telegram_bot_service.send_telegram_message", new_callable=AsyncMock) as mock_send, \
         patch("app.notifications.telegram_bot_service.answer_callback_query", new_callable=AsyncMock):
        
        cb = {
            "id": "cb_verify_1",
            "data": "action_continue",
            "message": {"chat": {"id": int(chat_id)}}
        }
        await telegram_bot_service._handle_callback(cb)

        # Automation must resume
        assert session.is_paused is False
        assert session.status == "IN_PROGRESS"

        # Verification in progress message must be sent to Telegram
        mock_send.assert_called_once()
        sent_msg = mock_send.call_args[0][0]
        assert "Verification" in sent_msg or "सत्यापन" in sent_msg
        assert "15-30" in sent_msg or "IRCTC" in sent_msg

@pytest.mark.asyncio
async def test_finalize_successful_booking_attaches_download_buttons():
    from app.crm.crm_service import finalize_successful_booking
    from app.config import settings

    db = SessionLocal()
    ref = "BK-TEST-VERIFY-003"
    old = db.query(Booking).filter(Booking.booking_ref == ref).first()
    if old:
        db.delete(old)
        db.commit()

    booking = Booking(
        booking_ref=ref,
        from_station="NDLS",
        to_station="PNVL",
        journey_date=date.today(),
        train_number="12952",
        train_name="Rajdhani Express",
        journey_class="3A",
        status="CONFIRMED",
        payment_status="COMPLETED",
        fare=1800.0,
        pnr="2819283746",
        passenger_count=1,
        created_at=datetime.utcnow()
    )
    db.add(booking)
    db.commit()
    b_id = booking.id
    db.close()

    try:
        with patch.object(settings, "TELEGRAM_ENABLED", True), \
             patch("app.crm.crm_service.send_telegram_message", new_callable=AsyncMock) as mock_send_msg, \
             patch("app.crm.crm_service.send_telegram_document", new_callable=AsyncMock) as mock_send_doc:
            
            db = SessionLocal()
            await finalize_successful_booking(db, b_id)
            db.close()

            # 1. Message must have been sent
            assert mock_send_msg.called
            call_kwargs = mock_send_msg.call_args[1]
            reply_markup = call_kwargs.get("reply_markup") or {}
            inline_kb = reply_markup.get("inline_keyboard", [])
            assert len(inline_kb) > 0
            btn_urls = [btn.get("url", "") for row in inline_kb for btn in row]
            assert any(f"/api/bookings/{ref}/ticket-pdf" in u for u in btn_urls)

            # 2. Both Ticket PDF and Invoice PDF documents must be dispatched
            assert mock_send_doc.call_count == 2
    finally:
        db = SessionLocal()
        b_clean = db.query(Booking).filter(Booking.booking_ref == ref).first()
        if b_clean:
            db.delete(b_clean)
            db.commit()
        db.close()

def test_pay_redirect_xss_prevention_and_404():
    # 1. Non-existent booking ref returns 404
    res_404 = client.get("/api/bookings/pay-redirect/NONEXISTENT-REF-999")
    assert res_404.status_code == 404

    # 2. Existing booking with special characters is HTML escaped
    db = SessionLocal()
    ref_xss = "BK-XSS-TEST-99"
    old = db.query(Booking).filter(Booking.booking_ref == ref_xss).first()
    if old:
        db.delete(old)
        db.commit()

    booking = Booking(
        booking_ref=ref_xss,
        from_station="NDLS",
        to_station="HWH",
        journey_date=date.today(),
        status="PAYMENT_PENDING",
        fare=500.0,
        passenger_count=1,
        payment_upi_url="upi://pay?pa=irctc@axisbank&pn=IRCTC&am=500.00"
    )
    db.add(booking)
    db.commit()
    b_id = booking.id
    db.close()

    try:
        # Access via booking_ref
        res = client.get(f"/api/bookings/pay-redirect/{ref_xss}")
        assert res.status_code == 200
        text = res.text
        assert ref_xss in text
        assert "upi://pay?pa=irctc@axisbank" in text

        # Access via integer ID
        res_id = client.get(f"/api/bookings/pay-redirect/{b_id}")
        assert res_id.status_code == 200
        assert ref_xss in res_id.text
    finally:
        db = SessionLocal()
        b = db.query(Booking).filter(Booking.booking_ref == ref_xss).first()
        if b:
            db.delete(b)
            db.commit()
        db.close()

@pytest.mark.asyncio
async def test_send_telegram_document_markdown_retry():
    from app.notifications.telegram import send_telegram_document_detailed

    # Mock response object
    class FakeResponse:
        def __init__(self, status_code, text):
            self.status_code = status_code
            self.text = text

    # First call fails with entity error, second retry succeeds
    mock_post = AsyncMock(side_effect=[
        FakeResponse(400, "Bad Request: can't parse entities in caption"),
        FakeResponse(200, '{"ok": true}')
    ])

    fake_client = MagicMock()
    fake_client.post = mock_post

    with patch("app.notifications.telegram.get_telegram_client", return_value=fake_client), \
         patch("app.notifications.telegram.settings.TELEGRAM_BOT_TOKEN", "123:TOKEN"), \
         patch("app.notifications.telegram.settings.TELEGRAM_CHAT_ID", "12345"):

        result = await send_telegram_document_detailed(
            document_bytes=b"%PDF-1.4 test dummy",
            filename="ticket_file_name_with_underscores.pdf",
            caption="*Invoice_File_123* with _markdown_ error"
        )

        assert result is True
        assert mock_post.call_count == 2
        # Second call must NOT have parse_mode in data
        second_call_data = mock_post.call_args_list[1][1]["data"]
        assert "parse_mode" not in second_call_data

def test_flow_state_is_payment_attribute():
    state = BookingSessionState("BK-TEST-IS-PAYMENT")
    assert state.is_payment is False

    state.pause_for_user("Please complete UPI payment", is_payment=True, input_type="PAYMENT")
    assert state.is_payment is True
    assert state.status == "PAYMENT_PENDING"

    state.user_resumed()
    assert state.is_payment is False
    assert state.is_paused is False
