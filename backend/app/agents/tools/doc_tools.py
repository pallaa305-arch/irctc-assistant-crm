"""
Document and CRM Tools for AI Agent.
Interfaces with CRM service, PDF service, and Excel exporter.
"""
from typing import Dict, Any
from app.database.connection import SessionLocal
from app.crm.crm_service import get_dashboard_stats

async def tool_export_crm_summary() -> Dict[str, Any]:
    """
    Fetch quick CRM summary statistics (total bookings, spent amount, passenger count).
    """
    db = SessionLocal()
    try:
        stats = get_dashboard_stats(db)
        recent = []
        for b in stats.get("recent_bookings", []):
            if isinstance(b, dict):
                recent.append(b.get("booking_reference", str(b.get("id", ""))))
            elif hasattr(b, "booking_reference"):
                recent.append(b.booking_reference)
        return {
            "success": True,
            "total_bookings": stats.get("total_bookings", 0),
            "total_spent": stats.get("total_spend", 0.0),
            "recent_bookings": recent[:5]
        }
    finally:
        db.close()
