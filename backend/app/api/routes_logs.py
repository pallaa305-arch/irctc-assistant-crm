from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.database.connection import get_db
from app.database.models import SystemLog

router = APIRouter(prefix="/api/logs", tags=["Logs"])

@router.get("")
async def get_system_logs(
    level: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Fetches sanitized structured application logs."""
    q = db.query(SystemLog)
    if level and level != "ALL":
        q = q.filter(SystemLog.level == level)
    if category and category != "ALL":
        q = q.filter(SystemLog.category == category)

    logs = q.order_by(desc(SystemLog.timestamp)).limit(limit).all()

    return [
        {
            "id": log.id,
            "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "level": log.level,
            "category": log.category,
            "booking_ref": log.booking_ref,
            "message": log.message
        }
        for log in logs
    ]
