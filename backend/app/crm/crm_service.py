from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc
from app.database.models import Booking, BookingPassenger, SystemLog
from app.security.sanitizer import sanitize_log_message
from app.crm.excel_exporter import append_booking_to_excel
from app.notifications.telegram import send_telegram_message, send_telegram_document, format_booking_confirmation_telegram
from app.notifications.whatsapp import send_whatsapp_message, format_booking_confirmation_whatsapp
from app.services.pdf_service import pdf_service
from app.config import settings

def log_event(db: Session, level: str, category: str, message: str, booking_ref: Optional[str] = None):
    """Safely logs an event after sanitizing credentials/cards."""
    safe_msg = sanitize_log_message(message)
    entry = SystemLog(
        level=level,
        category=category,
        booking_ref=booking_ref,
        message=safe_msg
    )
    db.add(entry)
    db.commit()

def get_dashboard_stats(db: Session, date_filter: Optional[str] = None) -> Dict[str, Any]:
    """Calculates all key stats for the dashboard."""
    query = db.query(Booking).filter(Booking.is_archived == False)
    today = date.today()

    if date_filter == "today":
        query = query.filter(Booking.created_at >= datetime.combine(today, datetime.min.time()))
    elif date_filter == "this_week":
        start_week = today - timedelta(days=today.weekday())
        query = query.filter(Booking.created_at >= datetime.combine(start_week, datetime.min.time()))
    elif date_filter == "this_month":
        start_month = today.replace(day=1)
        query = query.filter(Booking.created_at >= datetime.combine(start_month, datetime.min.time()))

    all_bookings = query.all()

    total = len(all_bookings)
    successful = sum(1 for b in all_bookings if b.status == "CONFIRMED")
    failed = sum(1 for b in all_bookings if b.status == "FAILED")
    pending = sum(1 for b in all_bookings if b.status in ["INITIATED", "IN_PROGRESS", "WAITING_MANUAL", "PAYMENT_PENDING"])
    cancelled = sum(1 for b in all_bookings if b.status == "CANCELLED")
    
    upcoming_journeys = db.query(Booking).filter(
        Booking.status == "CONFIRMED",
        Booking.journey_date >= today,
        Booking.is_archived == False
    ).order_by(Booking.journey_date.asc()).limit(5).all()

    recent_bookings = db.query(Booking).filter(
        Booking.is_archived == False
    ).order_by(desc(Booking.created_at)).limit(5).all()

    total_spend = sum(b.fare or 0.0 for b in all_bookings if b.status == "CONFIRMED")

    return {
        "total_bookings": total,
        "successful_bookings": successful,
        "failed_bookings": failed,
        "pending_bookings": pending,
        "cancelled_bookings": cancelled,
        "total_spend": total_spend,
        "upcoming_count": len(upcoming_journeys),
        "upcoming_journeys": [
            {
                "id": b.id,
                "booking_ref": b.booking_ref,
                "pnr": b.pnr,
                "train": f"{b.train_number or ''} {b.train_name or ''}".strip(),
                "route": f"{b.from_station} ➔ {b.to_station}",
                "journey_date": b.journey_date.strftime("%d %b %Y"),
                "passengers": b.passenger_count,
                "status": b.status
            }
            for b in upcoming_journeys
        ],
        "recent_bookings": [
            {
                "id": b.id,
                "booking_ref": b.booking_ref,
                "pnr": b.pnr,
                "train": f"{b.train_number or ''} {b.train_name or ''}".strip(),
                "route": f"{b.from_station} ➔ {b.to_station}",
                "journey_date": b.journey_date.strftime("%d/%m/%Y"),
                "passengers": b.passenger_count,
                "fare": b.fare,
                "status": b.status,
                "created_at": b.created_at.strftime("%d/%m %H:%M")
            }
            for b in recent_bookings
        ]
    }

def filter_bookings(
    db: Session,
    query_str: Optional[str] = None,
    status: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    journey_class: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> Dict[str, Any]:
    """Search and filter bookings with high performance."""
    q = db.query(Booking).filter(Booking.is_archived == False)

    if status and status != "ALL":
        q = q.filter(Booking.status == status)
    
    if journey_class and journey_class != "ALL":
        q = q.filter(Booking.journey_class == journey_class)

    if from_date:
        q = q.filter(Booking.journey_date >= from_date)
    if to_date:
        q = q.filter(Booking.journey_date <= to_date)

    if query_str:
        s = f"%{query_str}%"
        q = q.filter(
            or_(
                Booking.booking_ref.ilike(s),
                Booking.pnr.ilike(s),
                Booking.from_station.ilike(s),
                Booking.to_station.ilike(s),
                Booking.train_number.ilike(s),
                Booking.train_name.ilike(s),
                Booking.transaction_id.ilike(s)
            )
        )

    total_count = q.count()
    items = q.order_by(desc(Booking.created_at)).offset(offset).limit(limit).all()

    return {
        "total": total_count,
        "items": items
    }

async def finalize_successful_booking(db: Session, booking_id: int):
    """
    Called after confirmation is detected: updates CRM, appends to Excel, and fires notifications.
    """
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        return

    passengers = db.query(BookingPassenger).filter(BookingPassenger.booking_id == booking.id).all()

    # 1. Update Excel
    try:
        append_booking_to_excel(booking, passengers)
        log_event(db, "INFO", "CRM", f"Booking {booking.booking_ref} appended to Excel", booking.booking_ref)
    except Exception as e:
        log_event(db, "ERROR", "CRM", f"Failed appending to Excel: {str(e)}", booking.booking_ref)

    # 2. Telegram Notification & PDF Documents Dispatch
    if settings.TELEGRAM_ENABLED:
        try:
            tg_msg = format_booking_confirmation_telegram(booking, passengers)
            sent = await send_telegram_message(tg_msg)
            booking.telegram_status = "SENT" if sent else "FAILED"
            db.commit()
            log_event(db, "INFO", "NOTIFY", f"Telegram notification: {'Success' if sent else 'Failed'}", booking.booking_ref)

            # Generate and Send ERS Train Ticket PDF and Tax Invoice/Bill PDF
            try:
                b_dict = {
                    "pnr": booking.pnr or "2451234567",
                    "train_number": booking.train_number or "12952",
                    "train_name": booking.train_name or "Express",
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
                    for p in passengers
                ]

                # 1. Send ERS Ticket PDF
                ticket_pdf_bytes = pdf_service.generate_ticket_pdf(b_dict, pax_list, save_to_disk=True)
                pnr_display = booking.pnr or booking.booking_ref
                await send_telegram_document(
                    document_bytes=ticket_pdf_bytes,
                    filename=f"IRCTC_Ticket_{pnr_display}.pdf",
                    caption=f"🎫 *Official IRCTC Train Ticket (ERS Slip) PDF*\nAttached for your journey. Have a safe & comfortable trip! 🚆"
                )

                # 2. Send Travel Agency Tax Invoice / Bill PDF
                invoice_pdf_bytes = pdf_service.generate_invoice_pdf(b_dict, pax_list, save_to_disk=True)
                await send_telegram_document(
                    document_bytes=invoice_pdf_bytes,
                    filename=f"Invoice_Bill_{booking.booking_ref}.pdf",
                    caption=f"🧾 *Tax Invoice & Booking Bill PDF*\nAttached for your records and expense claims. Thank you! 🙏"
                )
                log_event(db, "INFO", "NOTIFY", f"Ticket PDF & Invoice Bill PDF dispatched to Telegram", booking.booking_ref)
            except Exception as pdf_err:
                log_event(db, "ERROR", "NOTIFY", f"PDF ticket/invoice dispatch error: {str(pdf_err)}", booking.booking_ref)

        except Exception as e:
            booking.telegram_status = "FAILED"
            db.commit()
            log_event(db, "ERROR", "NOTIFY", f"Telegram dispatch error: {str(e)}", booking.booking_ref)

    # 3. WhatsApp Notification
    if settings.WHATSAPP_ENABLED:
        try:
            wa_msg = format_booking_confirmation_whatsapp(booking)
            sent = await send_whatsapp_message(wa_msg)
            booking.whatsapp_status = "SENT" if sent else "FAILED"
            db.commit()
            log_event(db, "INFO", "NOTIFY", f"WhatsApp notification: {'Success' if sent else 'Failed'}", booking.booking_ref)
        except Exception as e:
            booking.whatsapp_status = "FAILED"
            db.commit()
            log_event(db, "ERROR", "NOTIFY", f"WhatsApp dispatch error: {str(e)}", booking.booking_ref)
