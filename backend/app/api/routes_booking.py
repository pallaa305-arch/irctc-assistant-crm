import uuid
import asyncio
from datetime import datetime, date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from app.database.connection import get_db, SessionLocal
from app.database.models import Booking, BookingPassenger
from app.automation.flow_state import get_or_create_session, get_session
from app.automation.mock_flow import run_mock_booking_flow
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
    demo_mode: Optional[bool] = None
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
        train_number=payload.train_preference or "12002",
        train_name="Selected Train",
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

    # 5. Dispatch Automation in independent task
    use_demo = payload.demo_mode if payload.demo_mode is not None else settings.DEMO_MODE

    target_flow = run_mock_booking_flow if use_demo else run_real_irctc_booking_flow
    asyncio.create_task(_run_flow_wrapper(target_flow, booking.id, session_state))

    return {
        "success": True,
        "booking_id": booking.id,
        "booking_ref": ref,
        "mode": "DEMO" if use_demo else "LIVE_IRCTC",
        "message": "Booking session initialized. Monitor visible browser or dashboard."
    }

@router.get("/state/{booking_ref}")
async def get_booking_state(booking_ref: str, db: Session = Depends(get_db)):
    """Retrieves live state machine progress and human-in-the-loop prompts."""
    booking = db.query(Booking).filter(Booking.booking_ref == booking_ref).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")

    session_state = get_session(booking_ref)
    
    stage = session_state.stage if session_state else "UNKNOWN"
    status = booking.status
    is_paused = session_state.is_paused if session_state else False
    manual_prompt = session_state.manual_prompt if session_state else None
    error_msg = session_state.error_message if session_state else None
    waiting_input_type = session_state.waiting_input_type if session_state else "NONE"

    return {
        "booking_ref": booking.booking_ref,
        "pnr": booking.pnr,
        "transaction_id": booking.transaction_id,
        "status": status,
        "stage": stage,
        "is_paused": is_paused,
        "manual_prompt": manual_prompt,
        "waiting_input_type": waiting_input_type,
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

@router.post("/action/{booking_ref}")
async def handle_user_action(booking_ref: str, payload: ActionRequest, db: Session = Depends(get_db)):
    """Handles manual user intervention: Continue, Pause, or Cancel."""
    session_state = get_session(booking_ref)
    if not session_state:
        raise HTTPException(status_code=404, detail="Active booking session not found.")

    booking = db.query(Booking).filter(Booking.booking_ref == booking_ref).first()

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
        "fare": booking.fare or 1450.0,
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
        "fare": booking.fare or 1450.0,
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
