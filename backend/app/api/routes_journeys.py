from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from app.database.connection import get_db
from app.database.models import SavedJourney
from app.crm.crm_service import log_event

router = APIRouter(prefix="/api/journeys", tags=["Saved Journeys"])

class SavedJourneySchema(BaseModel):
    label: str = Field(..., min_length=2)
    from_station: str = Field(..., min_length=2)
    to_station: str = Field(..., min_length=2)
    boarding_station: Optional[str] = None
    train_preference: Optional[str] = None
    preferred_class: str = "3A"
    preferred_quota: str = "GN"

class SavedJourneyResponse(SavedJourneySchema):
    id: int

@router.get("", response_model=List[SavedJourneyResponse])
async def get_saved_journeys(db: Session = Depends(get_db)):
    """Lists frequently used journey routes."""
    return db.query(SavedJourney).order_by(SavedJourney.label.asc()).all()

@router.post("", response_model=SavedJourneyResponse)
async def create_saved_journey(payload: SavedJourneySchema, db: Session = Depends(get_db)):
    """Saves a route for fast 1-click booking initialization."""
    sj = SavedJourney(
        label=payload.label.strip(),
        from_station=payload.from_station.strip().upper(),
        to_station=payload.to_station.strip().upper(),
        boarding_station=(payload.boarding_station or payload.from_station).strip().upper(),
        train_preference=payload.train_preference,
        preferred_class=payload.preferred_class,
        preferred_quota=payload.preferred_quota
    )
    db.add(sj)
    db.commit()
    db.refresh(sj)
    log_event(db, "INFO", "CRM", f"Added saved journey '{sj.label}' ({sj.from_station} ➔ {sj.to_station})")
    return sj

@router.delete("/{journey_id}")
async def delete_saved_journey(journey_id: int, db: Session = Depends(get_db)):
    """Deletes a saved journey."""
    sj = db.query(SavedJourney).filter(SavedJourney.id == journey_id).first()
    if not sj:
        raise HTTPException(status_code=404, detail="Saved journey not found.")

    label = sj.label
    db.delete(sj)
    db.commit()
    log_event(db, "INFO", "CRM", f"Deleted saved journey '{label}'")
    return {"success": True, "message": f"Saved journey '{label}' deleted."}
