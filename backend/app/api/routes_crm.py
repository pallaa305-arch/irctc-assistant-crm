import os
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database.connection import get_db
from app.database.models import Booking
from app.crm.crm_service import get_dashboard_stats, filter_bookings, log_event
from app.crm.excel_exporter import export_bookings_csv, backup_database, init_excel_workbook
from app.config import settings

router = APIRouter(prefix="/api/crm", tags=["CRM"])

class BookingUpdateRequest(BaseModel):
    notes: Optional[str] = None
    status: Optional[str] = None
    is_archived: Optional[bool] = None

@router.get("/stats")
async def fetch_dashboard_stats(filter_by: Optional[str] = Query(None, alias="filter"), db: Session = Depends(get_db)):
    """Provides instant counters and charts data for the dashboard."""
    return get_dashboard_stats(db, filter_by)

@router.get("/bookings")
async def list_bookings(
    q: Optional[str] = None,
    status: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    journey_class: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Deep search and filtering for booking records."""
    res = filter_bookings(
        db,
        query_str=q,
        status=status,
        from_date=from_date,
        to_date=to_date,
        journey_class=journey_class,
        limit=limit,
        offset=offset
    )

    items = []
    for b in res["items"]:
        items.append({
            "id": b.id,
            "booking_ref": b.booking_ref,
            "pnr": b.pnr,
            "transaction_id": b.transaction_id,
            "created_at": b.created_at.strftime("%d/%m/%Y %H:%M"),
            "journey_date": b.journey_date.strftime("%d/%m/%Y"),
            "from_station": b.from_station,
            "to_station": b.to_station,
            "boarding_station": b.boarding_station,
            "train_number": b.train_number,
            "train_name": b.train_name,
            "journey_class": b.journey_class,
            "quota": b.quota,
            "passenger_count": b.passenger_count,
            "fare": b.fare,
            "status": b.status,
            "payment_status": b.payment_status,
            "telegram_status": b.telegram_status,
            "whatsapp_status": b.whatsapp_status,
            "notes": b.notes,
            "passengers": [
                {
                    "id": p.id,
                    "name": p.name,
                    "age": p.age,
                    "gender": p.gender,
                    "berth": p.berth_preference,
                    "seat": p.allocated_seat,
                    "status": p.status
                }
                for p in b.passengers
            ]
        })

    return {
        "total": res["total"],
        "items": items
    }

@router.patch("/bookings/{booking_id}")
async def update_booking_crm(booking_id: int, payload: BookingUpdateRequest, db: Session = Depends(get_db)):
    """Updates permitted notes, status, or archive flags."""
    b = db.query(Booking).filter(Booking.id == booking_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="Booking not found.")

    if payload.notes is not None:
        b.notes = payload.notes
    if payload.status is not None:
        b.status = payload.status
    if payload.is_archived is not None:
        b.is_archived = payload.is_archived

    db.commit()
    log_event(db, "INFO", "CRM", f"Updated CRM notes/status for {b.booking_ref}", b.booking_ref)
    return {"success": True, "message": "Record updated."}

@router.delete("/bookings/{booking_id}")
async def delete_booking_crm(booking_id: int, db: Session = Depends(get_db)):
    """Deletes a booking record."""
    b = db.query(Booking).filter(Booking.id == booking_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="Booking not found.")

    ref = b.booking_ref
    db.delete(b)
    db.commit()
    log_event(db, "INFO", "CRM", f"Deleted booking record {ref}", ref)
    return {"success": True, "message": "Booking deleted."}

@router.get("/export/excel")
async def download_excel_crm():
    """Generates and serves the master bookings.xlsx file."""
    path = settings.EXCEL_FILE_PATH
    if not os.path.exists(path):
        init_excel_workbook(path)

    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="irctc_bookings.xlsx"
    )

@router.get("/export/csv")
async def download_csv_crm(db: Session = Depends(get_db)):
    """Exports all active bookings to CSV."""
    bookings = db.query(Booking).filter(Booking.is_archived == False).all()
    data = []
    for b in bookings:
        p_names = ", ".join([p.name for p in b.passengers])
        data.append({
            "Booking ID": b.booking_ref,
            "PNR": b.pnr or "N/A",
            "Transaction ID": b.transaction_id or "N/A",
            "Booking Date": b.created_at.strftime("%d/%m/%Y %H:%M"),
            "Journey Date": b.journey_date.strftime("%d/%m/%Y"),
            "From": b.from_station,
            "To": b.to_station,
            "Train Number": b.train_number or "N/A",
            "Train Name": b.train_name or "N/A",
            "Class": b.journey_class,
            "Quota": b.quota,
            "Passenger Count": b.passenger_count,
            "Passengers": p_names,
            "Status": b.status,
            "Fare": b.fare or 0.0,
            "Notes": b.notes or ""
        })

    csv_path = export_bookings_csv(data)
    return FileResponse(
        csv_path,
        media_type="text/csv",
        filename=os.path.basename(csv_path)
    )

@router.post("/backup")
async def trigger_database_backup(db: Session = Depends(get_db)):
    """Triggers an on-demand database backup snapshot."""
    try:
        backup_path = backup_database()
        log_event(db, "INFO", "SYSTEM", f"Database backed up to {backup_path}")
        return {"success": True, "backup_path": backup_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
