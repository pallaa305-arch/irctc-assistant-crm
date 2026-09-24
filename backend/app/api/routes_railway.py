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

@router.get("/stations")
async def search_stations(q: str = Query(..., min_length=1), limit: int = Query(35, le=100)):
    from app.services.station_cache import station_cache
    results = station_cache.search_stations(q, limit=limit)
    return {
        "success": True,
        "query": q,
        "count": len(results),
        "stations": results
    }

@router.get("/availability")
async def get_seat_availability(
    train_number: str = Query(..., min_length=3),
    from_station: str = Query(..., min_length=2),
    to_station: str = Query(..., min_length=2),
    journey_date: str = Query(...),
    quota: str = Query("GN")
):
    """Returns live coach-wise seat availability (Available/RAC/Waiting List) and fare breakdown."""
    res = railway_service.get_seat_availability(
        train_number=train_number,
        from_code=from_station,
        to_code=to_station,
        journey_date=journey_date,
        quota=quota
    )
    return res

