import asyncio
import random
from datetime import datetime
from sqlalchemy.orm import Session
from app.automation.flow_state import BookingSessionState
from app.database.models import Booking, BookingPassenger
from app.crm.crm_service import log_event, finalize_successful_booking
from app.notifications.telegram import send_telegram_message, format_action_required_telegram
from app.config import settings

async def run_mock_booking_flow(db: Session, booking_id: int, session_state: BookingSessionState):
    """
    Executes a high-fidelity mock booking flow that strictly adheres to the state machine
    and human-in-the-loop pauses without contacting real IRCTC.
    """
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        session_state.set_stage("FAILED", "FAILED")
        session_state.error_message = "Booking record not found in database."
        return

    ref = booking.booking_ref
    try:
        # Step 1: Preparing
        session_state.set_stage("PREPARING", "IN_PROGRESS")
        booking.status = "IN_PROGRESS"
        db.commit()
        log_event(db, "INFO", "AUTOMATION", "Mock: Session prepared and validated.", ref)
        await asyncio.sleep(0.3)

        if session_state.cancel_event.is_set():
            return

        # Step 2: Opening IRCTC
        session_state.set_stage("OPENING_IRCTC")
        log_event(db, "INFO", "AUTOMATION", "Mock: Opening official IRCTC portal (simulated)", ref)
        await asyncio.sleep(0.3)

        # Step 3: Searching Trains
        session_state.set_stage("SEARCHING_TRAINS")
        log_event(db, "INFO", "AUTOMATION", f"Mock: Searching trains from {booking.from_station} to {booking.to_station} on {booking.journey_date}", ref)
        await asyncio.sleep(0.3)

        # Step 4: Selecting Train
        session_state.set_stage("SELECTING_TRAIN")
        if not booking.train_name:
            booking.train_number = "12002"
            booking.train_name = "Bhopal Shatabdi Express"
            booking.departure_time = "06:00"
            booking.arrival_time = "11:45"
            db.commit()
        log_event(db, "INFO", "AUTOMATION", f"Mock: Selected train {booking.train_number} {booking.train_name}", ref)
        await asyncio.sleep(0.3)

        # Step 5: Filling Passengers
        session_state.set_stage("FILLING_PASSENGERS")
        passengers = db.query(BookingPassenger).filter(BookingPassenger.booking_id == booking.id).all()
        log_event(db, "INFO", "AUTOMATION", f"Mock: Filled details for {len(passengers)} passenger(s)", ref)
        await asyncio.sleep(0.3)

        # Step 6: Challenge Detection -> Human-in-the-Loop PAUSE
        session_state.set_stage("WAITING_MANUAL")
        prompt_text = "Security Verification: Please solve the visual CAPTCHA and review passenger details."
        session_state.pause_for_user(prompt_text, is_payment=False, input_type="CAPTCHA")
        booking.status = "WAITING_MANUAL"
        db.commit()
        log_event(db, "WARNING", "AUTOMATION", f"Mock: {prompt_text}", ref)

        from app.utils.image_gen import generate_mock_captcha_image, generate_mock_upi_qr_image
        from app.notifications.telegram import send_telegram_photo

        sample_captcha_chars = "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", k=5))
        captcha_png = generate_mock_captcha_image(sample_captcha_chars)
        session_state.captured_data["captcha_expected"] = sample_captcha_chars

        if settings.TELEGRAM_ENABLED:
            await send_telegram_photo(
                photo_bytes=captcha_png,
                caption=(
                    f"📸 *IRCTC CAPTCHA Check* (Ref: `{ref}`)\n\n"
                    f"Kripya ye photo dekh kar text reply karein (e.g. `{sample_captcha_chars}`):"
                )
            )

        # Wait for user input from Telegram text reply or Web dashboard
        done, pending = await asyncio.wait(
            [
                asyncio.create_task(session_state.continue_event.wait()),
                asyncio.create_task(session_state.input_event.wait())
            ],
            return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()

        if session_state.cancel_event.is_set():
            booking.status = "CANCELLED"
            db.commit()
            log_event(db, "INFO", "AUTOMATION", "Mock booking cancelled by user.", ref)
            return

        user_input = session_state.user_input_value or sample_captcha_chars
        log_event(db, "INFO", "AUTOMATION", f"Mock: CAPTCHA verified: '{user_input}'. Continuing...", ref)

        # Step 7: Payment Handoff -> Human-in-the-Loop PAUSE
        session_state.set_stage("PAYMENT_PENDING")
        fare_amt = booking.fare or (1450.00 * max(1, len(passengers)))
        pay_prompt = f"PAYMENT REQUIRED: Fare ₹{fare_amt:.2f}. Please scan UPI QR code or complete payment."
        session_state.pause_for_user(pay_prompt, is_payment=True, input_type="PAYMENT")
        booking.status = "PAYMENT_PENDING"
        db.commit()
        log_event(db, "WARNING", "AUTOMATION", f"Mock: {pay_prompt}", ref)

        qr_png = generate_mock_upi_qr_image(fare_amt, ref)
        if settings.TELEGRAM_ENABLED:
            qr_keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "✅ Payment Ho Gayi (Continue)", "callback_data": "action_continue"},
                        {"text": "❌ Cancel", "callback_data": "action_cancel"}
                    ]
                ]
            }
            await send_telegram_photo(
                photo_bytes=qr_png,
                caption=(
                    f"💳 *IRCTC Payment Gateway — UPI QR*\n\n"
                    f"• *Amount:* ₹{fare_amt:.2f}\n"
                    f"• *Booking Ref:* `{ref}`\n\n"
                    f"Apne kisi bhi UPI app (GPay / PhonePe / Paytm) se scan karke pay karein, phir neeche *'✅ Payment Ho Gayi'* par tap karein."
                ),
                reply_markup=qr_keyboard
            )

        # Wait for user to complete payment
        await session_state.continue_event.wait()
        if session_state.cancel_event.is_set():
            booking.status = "CANCELLED"
            db.commit()
            log_event(db, "INFO", "AUTOMATION", "Mock payment cancelled by user.", ref)
            return

        # Step 8: Confirmation and PNR Generation
        session_state.set_stage("CONFIRMATION_DETECTED")
        mock_pnr = str(random.randint(2000000000, 9999999999))
        mock_txn = f"TXN{random.randint(10000000, 99999999)}"
        booking.pnr = mock_pnr
        booking.transaction_id = mock_txn
        booking.status = "CONFIRMED"
        booking.payment_status = "COMPLETED"
        if not booking.fare:
            booking.fare = 1450.00 * max(1, len(passengers))

        # Assign berths
        coaches = ["B1", "B2", "B3", "A1", "S1", "S2"]
        for idx, p in enumerate(passengers):
            p.allocated_seat = f"{random.choice(coaches)}-{random.randint(1, 72)}"
            p.status = "CNF"
        db.commit()

        log_event(db, "INFO", "AUTOMATION", f"Mock: Confirmation captured! PNR: {mock_pnr}, TXN: {mock_txn}", ref)

        # Step 9: Finalize CRM, Excel, and Notifications
        await finalize_successful_booking(db, booking.id)

        session_state.set_stage("COMPLETED", "CONFIRMED")
        session_state.captured_data = {
            "pnr": mock_pnr,
            "transaction_id": mock_txn,
            "fare": booking.fare,
            "status": "CONFIRMED"
        }
        log_event(db, "INFO", "AUTOMATION", f"Mock booking {ref} successfully finalized in CRM.", ref)

    except Exception as e:
        session_state.set_stage("FAILED", "FAILED")
        session_state.error_message = str(e)
        booking.status = "FAILED"
        db.commit()
        log_event(db, "ERROR", "AUTOMATION", f"Mock booking failed with error: {str(e)}", ref)
