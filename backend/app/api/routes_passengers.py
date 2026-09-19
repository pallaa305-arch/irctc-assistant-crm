from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from app.database.connection import get_db
from app.database.models import Passenger
from app.crm.crm_service import log_event

router = APIRouter(prefix="/api/passengers", tags=["Passengers"])

class PassengerSchema(BaseModel):
    name: str = Field(..., min_length=2)
    age: int = Field(..., ge=1, le=120)
    gender: str = Field(..., pattern="^(M|F|T)$")
    berth_preference: str = "NONE"
    food_preference: str = "D"
    senior_citizen: bool = False
    is_default: bool = False

class PassengerResponse(PassengerSchema):
    id: int

@router.get("", response_model=List[PassengerResponse])
async def get_saved_passengers(db: Session = Depends(get_db)):
    """Fetches list of all saved passenger profiles."""
    return db.query(Passenger).order_by(Passenger.name.asc()).all()

@router.post("", response_model=PassengerResponse)
async def create_saved_passenger(payload: PassengerSchema, db: Session = Depends(get_db)):
    """Creates a new saved passenger profile."""
    p = Passenger(
        name=payload.name.strip(),
        age=payload.age,
        gender=payload.gender,
        berth_preference=payload.berth_preference,
        food_preference=payload.food_preference,
        senior_citizen=payload.senior_citizen,
        is_default=payload.is_default
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    log_event(db, "INFO", "CRM", f"Added saved passenger {p.name}")
    return p

@router.put("/{passenger_id}", response_model=PassengerResponse)
async def update_saved_passenger(passenger_id: int, payload: PassengerSchema, db: Session = Depends(get_db)):
    """Updates an existing passenger profile."""
    p = db.query(Passenger).filter(Passenger.id == passenger_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Passenger not found.")

    p.name = payload.name.strip()
    p.age = payload.age
    p.gender = payload.gender
    p.berth_preference = payload.berth_preference
    p.food_preference = payload.food_preference
    p.senior_citizen = payload.senior_citizen
    p.is_default = payload.is_default

    db.commit()
    db.refresh(p)
    log_event(db, "INFO", "CRM", f"Updated saved passenger {p.name}")
    return p

@router.delete("/{passenger_id}")
async def delete_saved_passenger(passenger_id: int, db: Session = Depends(get_db)):
    """Deletes a passenger profile."""
    p = db.query(Passenger).filter(Passenger.id == passenger_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Passenger not found.")

    name = p.name
    db.delete(p)
    db.commit()
    log_event(db, "INFO", "CRM", f"Deleted saved passenger {name}")
    return {"success": True, "message": f"Passenger {name} deleted."}
