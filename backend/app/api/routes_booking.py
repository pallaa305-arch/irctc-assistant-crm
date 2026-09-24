import uuid
import asyncio
from datetime import datetime, date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from app.database.connection import get_db, SessionLocal
from app.database.models import Booking, BookingPassenger
from app.automation.flow_state import get_or_create_session, get_session
from app.automation.irctc_flow import run_real_irctc_booking_flow
from app.crm.crm_service import log_event
from app.services.pdf_service import pdf_service
from app.config import settings

router = APIRouter(prefix="/api/bookings", tags=["Bookings"])

class PassengerInput(BaseModel):
    name: str = Field(..., min_length=2)
    age: int = Field(..., ge=1, le=120)
    gender: str = Field("M", pattern="^(M|F|T)$")
    berth_preference: str = "NONE"
    food_preference: str = "D"

class BookingCreateRequest(BaseModel):
    from_station: str = Field(..., min_length=2)
    to_station: str = Field(..., min_length=2)
    boarding_station: Optional[str] = None
    journey_date: date
    journey_class: str = "3A"
    quota: str = "GN"
    train_preference: Optional[str] = None
    contact_mobile: Optional[str] = None
    contact_email: Optional[str] = None
    passengers: List[PassengerInput] = Field(..., min_length=1)
    allow_duplicate: bool = False

class ActionRequest(BaseModel):
    action: str = Field(..., pattern="^(continue|pause|cancel)$")
    note: Optional[str] = None
    input_value: Optional[str] = None

async def _run_flow_wrapper(flow_fn, booking_id: int, session_state):
    db = SessionLocal()
    try:
        await flow_fn(db, booking_id, session_state)
    finally:
        db.close()

@router.post("/start")
async def start_booking(
    payload: BookingCreateRequest,
    db: Session = Depends(get_db)
):
    """
    Validates input, checks duplicate active bookings, initializes record,
    and initiates the booking automation state machine asynchronously.
    """
    # 1. Smart Passenger-Aware Duplicate Protection
    if not payload.allow_duplicate:
        incoming_names = {p.name.strip().lower() for p in payload.passengers if p.name and p.name.strip()}
        
        # Look for existing active/confirmed bookings on same route and date
        existing_bookings = db.query(Booking).filter(
            Booking.from_station.ilike(payload.from_station.strip()),
            Booking.to_station.ilike(payload.to_station.strip()),
            Booking.journey_date == payload.journey_date,
            Booking.status.in_(["INITIATED", "IN_PROGRESS", "WAITING_MANUAL", "PAYMENT_PENDING", "CONFIRMED"])
        ).all()

        duplicate_found = None
        matched_passenger = None
        for b in existing_bookings:
            for bp in b.passengers:
                if bp.name.strip().lower() in incoming_names:
                    duplicate_found = b
                    matched_passenger = bp.name
                    break
            if duplicate_found:
                break

        if duplicate_found:
            raise HTTPException(
                status_code=409,
                detail=f"Duplicate passenger warning: Passenger '{matched_passenger}' already has a booking ({duplicate_found.booking_ref}) for {payload.from_station} ➔ {payload.to_station} on {payload.journey_date}."
            )

    # 2. Create internal reference & DB record
    ref = f"BK-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    booking = Booking(
        booking_ref=ref,
        from_station=payload.from_station.strip().upper(),
        to_station=payload.to_station.strip().upper(),
        boarding_station=(payload.boarding_station or payload.from_station).strip().upper(),
        journey_date=payload.journey_date,
        journey_class=payload.journey_class,
        quota=payload.quota,
        train_number=payload.train_preference or "",
        train_name="Auto-Selected Train",
        passenger_count=len(payload.passengers),
        contact_mobile=payload.contact_mobile,
        contact_email=payload.contact_email,
        status="INITIATED",
        payment_status="PENDING"
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)

    # 3. Add passengers
    for p in payload.passengers:
        bp = BookingPassenger(
            booking_id=booking.id,
            name=p.name.strip(),
            age=p.age,
            gender=p.gender,
            berth_preference=p.berth_preference,
            food_preference=p.food_preference,
            status="CNF"
        )
        db.add(bp)
    db.commit()

    log_event(db, "INFO", "AUTOMATION", f"Booking session {ref} initiated for {len(payload.passengers)} passenger(s).", ref)

    # 4. Initialize State Machine
    session_state = get_or_create_session(ref)
    session_state.set_stage("PREPARING", "INITIATED")

    # 5. Dispatch Live Official IRCTC Automation
    asyncio.create_task(_run_flow_wrapper(run_real_irctc_booking_flow, booking.id, session_state))

    return {
        "success": True,
        "booking_id": booking.id,
        "booking_ref": ref,
        "mode": "LIVE_IRCTC",
        "message": "Official IRCTC Booking session initialized. Monitor visible browser or dashboard."
    }

@router.get("/state/{booking_ref}")
async def get_booking_state(booking_ref: str, db: Session = Depends(get_db)):
    """Retrieves live state machine progress and human-in-the-loop prompts."""
    if booking_ref.isdigit():
        booking = db.query(Booking).filter((Booking.id == int(booking_ref)) | (Booking.booking_ref == booking_ref)).first()
    else:
        booking = db.query(Booking).filter(Booking.booking_ref == booking_ref).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")

    actual_ref = booking.booking_ref
    session_state = get_session(actual_ref)
    
    stage = session_state.stage if session_state else "UNKNOWN"
    status = booking.status
    is_paused = session_state.is_paused if session_state else False
    manual_prompt = session_state.manual_prompt if session_state else None
    error_msg = session_state.error_message if session_state else None
    waiting_input_type = session_state.waiting_input_type if session_state else "NONE"
    suggested_captcha = session_state.suggested_captcha if session_state else None

    timer_remaining = None
    if session_state and session_state.timer_seconds and session_state.timer_started_at:
        elapsed = (datetime.now(session_state.timer_started_at.tzinfo) - session_state.timer_started_at).total_seconds()
        timer_remaining = max(0, int(session_state.timer_seconds - elapsed))

    return {
        "booking_ref": booking.booking_ref,
        "pnr": booking.pnr,
        "transaction_id": booking.transaction_id,
        "status": status,
        "stage": stage,
        "is_paused": is_paused,
        "manual_prompt": manual_prompt,
        "waiting_input_type": waiting_input_type,
        "suggested_captcha": suggested_captcha,
        "timer_seconds": session_state.timer_seconds if session_state else None,
        "timer_remaining_seconds": timer_remaining,
        "error_message": error_msg,
        "from_station": booking.from_station,
        "to_station": booking.to_station,
        "journey_date": booking.journey_date.strftime("%d/%m/%Y"),
        "train": f"{booking.train_number or ''} {booking.train_name or ''}".strip(),
        "fare": booking.fare,
        "passengers": [
            {
                "name": p.name,
                "age": p.age,
                "gender": p.gender,
                "berth": p.berth_preference,
                "seat": p.allocated_seat,
                "status": p.status
            }
            for p in booking.passengers
        ]
    }

@router.get("/screenshot/{booking_ref}")
async def get_booking_screenshot(booking_ref: str):
    """Returns the latest screenshot (CAPTCHA / QR / Login modal) for human-in-the-loop review."""
    session_state = get_session(booking_ref)
    if session_state and session_state.latest_screenshot_bytes:
        return Response(
            content=session_state.latest_screenshot_bytes,
            media_type="image/png",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )

    # Check fallback image on disk
    fallback_path = settings.DATA_DIR / "latest_captcha.png"
    if fallback_path.exists():
        return Response(
            content=fallback_path.read_bytes(),
            media_type="image/png",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )

    raise HTTPException(status_code=404, detail="Screenshot not available.")

@router.get("/pay-redirect/{booking_ref}", response_class=HTMLResponse)
async def pay_redirect(booking_ref: str, db: Session = Depends(get_db)):
    """
    Mobile UPI Deep-Link Bridge:
    Instantly launches native UPI Apps (GPay, PhonePe, Paytm, BHIM, Cred)
    with the pre-filled IRCTC payment amount.
    """
    booking = None
    if booking_ref.isdigit():
        booking = db.query(Booking).filter((Booking.id == int(booking_ref)) | (Booking.booking_ref == booking_ref)).first()
    else:
        booking = db.query(Booking).filter(Booking.booking_ref == booking_ref).first()

    actual_ref = booking.booking_ref if booking else booking_ref
    session_state = get_session(actual_ref)

    upi_intent_url = ""
    if session_state and session_state.captured_data.get("upi_intent_url"):
        upi_intent_url = session_state.captured_data.get("upi_intent_url")
    elif booking and booking.payment_upi_url:
        upi_intent_url = booking.payment_upi_url

    fare = booking.fare if (booking and booking.fare) else 0.0
    fare_str = f"{fare:,.2f}" if fare else "Total Amount"

    has_screenshot = bool(session_state and session_state.latest_screenshot_bytes) or (settings.DATA_DIR / "latest_captcha.png").exists()
    qr_img_html = f'<img src="/api/bookings/screenshot/{actual_ref}" class="qr-img" alt="IRCTC QR Code" />' if has_screenshot else ''

    auto_pay_block = f"""<a id='autoPayLink' href="{upi_intent_url}" class='btn-main'>⚡ Open Any UPI App & Pay</a>""" if upi_intent_url else """<div class='btn-main' style='background:#475569;'>⏳ Generating Payment QR...</div>"""

    app_grid_block = f"""
        <div class='app-grid'>
            <a href="{upi_intent_url}" class='app-btn btn-gpay'>Google Pay</a>
            <a href="{upi_intent_url}" class='app-btn btn-phonepe'>PhonePe</a>
            <a href="{upi_intent_url}" class='app-btn btn-paytm'>Paytm</a>
            <a href="{upi_intent_url}" class='app-btn btn-bhim'>BHIM / CRED</a>
        </div>
    """ if upi_intent_url else ""

    upi_display_block = f"""<div class='upi-box'><code>{upi_intent_url}</code></div>""" if upi_intent_url else ""

    js_redirect = f"""
        window.addEventListener('DOMContentLoaded', () => {{
            setTimeout(() => {{
                try {{
                    window.location.href = "{upi_intent_url}";
                }} catch (e) {{}}
            }}, 300);
        }});
    """ if upi_intent_url else """
        setTimeout(() => { window.location.reload(); }, 3000);
    """

    html_content = f"""<!DOCTYPE html>
<html lang="hi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚡ IRCTC Fast Pay - {actual_ref}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }}
        body {{ background: #090d16; color: #f8fafc; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; padding: 16px; }}
        .card {{ background: #131b2e; border: 1px solid #1e293b; border-radius: 24px; padding: 24px 20px; max-width: 420px; width: 100%; box-shadow: 0 20px 30px -10px rgba(0, 0, 0, 0.6); text-align: center; }}
        .badge {{ display: inline-block; background: #0284c7; color: #fff; font-size: 11px; font-weight: 700; text-transform: uppercase; padding: 4px 12px; border-radius: 999px; margin-bottom: 12px; letter-spacing: 0.05em; }}
        .title {{ font-size: 20px; font-weight: 800; margin-bottom: 4px; }}
        .subtitle {{ font-size: 12px; color: #94a3b8; margin-bottom: 20px; }}
        .amount-box {{ background: linear-gradient(135deg, #064e3b, #065f46); border: 1px solid #10b981; border-radius: 16px; padding: 16px; margin-bottom: 20px; box-shadow: 0 4px 14px rgba(16, 185, 129, 0.2); }}
        .amount-lbl {{ font-size: 12px; color: #a7f3d0; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px; font-weight: 600; }}
        .amount {{ font-size: 34px; font-weight: 900; color: #ffffff; }}
        .btn-main {{ display: flex; align-items: center; justify-content: center; gap: 8px; width: 100%; background: linear-gradient(135deg, #2563eb, #7c3aed); color: #fff; padding: 16px; border-radius: 14px; font-size: 17px; font-weight: 800; text-decoration: none; margin-bottom: 14px; box-shadow: 0 4px 16px rgba(37, 99, 235, 0.4); border: none; cursor: pointer; transition: transform 0.1s; }}
        .btn-main:active {{ transform: scale(0.98); }}
        .app-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 16px; }}
        .app-btn {{ display: flex; align-items: center; justify-content: center; gap: 6px; padding: 12px; border-radius: 12px; text-decoration: none; font-size: 13px; font-weight: 700; border: 1px solid #334155; transition: transform 0.1s; }}
        .app-btn:active {{ transform: scale(0.97); }}
        .btn-gpay {{ background: #ffffff; color: #1e293b; }}
        .btn-phonepe {{ background: #5f259f; color: #ffffff; }}
        .btn-paytm {{ background: #002970; color: #ffffff; }}
        .btn-bhim {{ background: #00796b; color: #ffffff; }}
        .qr-section {{ margin-top: 16px; padding-top: 16px; border-top: 1px solid #1e293b; }}
        .qr-img {{ width: 220px; height: 220px; border-radius: 14px; background: white; padding: 10px; margin: 10px auto; display: block; box-shadow: 0 4px 12px rgba(0,0,0,0.3); }}
        .note {{ font-size: 12px; color: #94a3b8; margin-top: 14px; line-height: 1.5; }}
        .upi-box {{ background: #0f172a; padding: 8px 12px; border-radius: 8px; font-size: 11px; color: #38bdf8; word-break: break-all; margin-top: 10px; border: 1px dashed #334155; }}
    </style>
</head>
<body>
    <div class="card">
        <span class="badge">Official IRCTC Gateway</span>
        <h2 class="title">⚡ One-Click Payment</h2>
        <p class="subtitle">Booking Ref: {actual_ref}</p>

        <div class="amount-box">
            <div class="amount-lbl">Total Fare to Pay</div>
            <div class="amount">₹{fare_str}</div>
        </div>

        {auto_pay_block}

        {app_grid_block}

        <div class="qr-section">
            <div style="font-size:12px; color:#cbd5e1; font-weight:600;">Or Scan QR Directly</div>
            {qr_img_html}
        </div>

        {upi_display_block}

        <p class="note">
            Tapping opens your chosen payment app with the exact amount pre-filled.<br>
            After entering your PIN, your ticket PNR will confirm automatically!
        </p>
    </div>

    <script>
        {js_redirect}
    </script>
</body>
</html>"""
    return HTMLResponse(content=html_content)

@router.post("/action/{booking_ref}")
async def handle_user_action(booking_ref: str, payload: ActionRequest, db: Session = Depends(get_db)):
    """Handles manual user intervention: Continue, Pause, or Cancel."""
    if booking_ref.isdigit():
        booking = db.query(Booking).filter((Booking.id == int(booking_ref)) | (Booking.booking_ref == booking_ref)).first()
    else:
        booking = db.query(Booking).filter(Booking.booking_ref == booking_ref).first()

    actual_ref = booking.booking_ref if booking else booking_ref
    session_state = get_session(actual_ref)
    if not session_state:
        raise HTTPException(status_code=404, detail="Active booking session not found.")

    if payload.action == "continue":
        if payload.input_value:
            session_state.provide_user_input(payload.input_value)
        else:
            session_state.user_resumed()
        if booking:
            booking.status = "IN_PROGRESS"
            db.commit()
        log_event(db, "INFO", "AUTOMATION", f"User manually confirmed/resumed booking {booking_ref}.", booking_ref)
        return {"success": True, "message": "Resumed automation."}

    elif payload.action == "pause":
        session_state.pause_for_user(payload.note or "Paused by user")
        if booking:
            booking.status = "WAITING_MANUAL"
            db.commit()
        log_event(db, "INFO", "AUTOMATION", f"User manually paused booking {booking_ref}.", booking_ref)
        return {"success": True, "message": "Automation paused."}

    elif payload.action == "cancel":
        session_state.user_cancelled(payload.note or "Cancelled by user")
        if booking:
            booking.status = "CANCELLED"
            db.commit()
        log_event(db, "WARNING", "AUTOMATION", f"User cancelled booking {booking_ref}.", booking_ref)
        return {"success": True, "message": "Automation cancelled."}

@router.get("/{booking_id}/ticket-pdf")
async def download_ticket_pdf(booking_id: int, db: Session = Depends(get_db)):
    """Generates and downloads the Official IRCTC Electronic Reservation Slip (Ticket) PDF."""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    b_dict = {
        "pnr": booking.pnr or "2451234567",
        "train_number": booking.train_number or "12952",
        "train_name": booking.train_name or "Rajdhani Express",
        "from_station": booking.from_station,
        "to_station": booking.to_station,
        "journey_date": booking.journey_date.strftime("%d/%m/%Y") if booking.journey_date else "",
        "journey_class": booking.journey_class,
        "quota": booking.quota or "GENERAL (GN)",
        "fare": booking.fare or 0.0,
        "booking_ref": booking.booking_ref,
        "booking_time": booking.created_at.strftime("%d-%b-%Y %H:%M:%S") if booking.created_at else ""
    }
    pax_list = [
        {
            "name": p.name,
            "age": p.age,
            "gender": p.gender,
            "allocated_seat": p.allocated_seat or "B4-45 [MB]",
            "status": p.status or "CNF"
        }
        for p in booking.passengers
    ]
    pdf_bytes = pdf_service.generate_ticket_pdf(b_dict, pax_list, save_to_disk=True)
    filename = f"IRCTC_Ticket_{booking.pnr or booking.booking_ref}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/{booking_id}/invoice-pdf")
async def download_invoice_pdf(booking_id: int, db: Session = Depends(get_db)):
    """Generates and downloads the Travel Agency Tax Invoice & Booking Bill PDF."""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    b_dict = {
        "pnr": booking.pnr or "2451234567",
        "train_number": booking.train_number or "12952",
        "train_name": booking.train_name or "Rajdhani Express",
        "from_station": booking.from_station,
        "to_station": booking.to_station,
        "journey_date": booking.journey_date.strftime("%d/%m/%Y") if booking.journey_date else "",
        "journey_class": booking.journey_class,
        "quota": booking.quota or "GENERAL (GN)",
        "fare": booking.fare or 0.0,
        "booking_ref": booking.booking_ref,
        "booking_time": booking.created_at.strftime("%d-%b-%Y %H:%M:%S") if booking.created_at else ""
    }
    pax_list = [
        {
            "name": p.name,
            "age": p.age,
            "gender": p.gender,
            "allocated_seat": p.allocated_seat or "B4-45 [MB]",
            "status": p.status or "CNF"
        }
        for p in booking.passengers
    ]
    pdf_bytes = pdf_service.generate_invoice_pdf(b_dict, pax_list, save_to_disk=True)
    filename = f"Invoice_Bill_{booking.booking_ref}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
