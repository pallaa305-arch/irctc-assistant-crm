from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.services.railway_service import railway_service

router = APIRouter(prefix="/api/railway", tags=["Railway Live Services"])

@router.get("/pnr/{pnr}")
async def get_pnr(pnr: str):
    result = await railway_service.get_pnr_status(pnr)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "PNR status lookup failed"))
    return result

@router.get("/live/{train_no}")
async def get_live_train(train_no: str):
    result = await railway_service.get_live_train_status(train_no)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Live train lookup failed"))
    return result

@router.get("/search")
async def search_trains(from_station: str = Query(..., min_length=2), to_station: str = Query(..., min_length=2)):
    trains = await railway_service.search_trains(from_station, to_station)
    return {
        "success": True,
        "from_station": from_station.upper(),
        "to_station": to_station.upper(),
        "count": len(trains),
        "trains": trains
    }
