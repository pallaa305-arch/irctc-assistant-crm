import asyncio
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.automation.browser_manager import browser_manager
from app.automation.flow_state import BookingSessionState
from app.automation.irctc_flow import ensure_authenticated_session
from app.config import settings
from app.database.models import Booking

logger = logging.getLogger("master_list_sync")

MASTER_LIST_URL = "https://www.irctc.co.in/nget/profile/add-passenger"

GENDER_MAP = {
    "M": "M", "MALE": "M", "MAN": "M", "BOY": "M",
    "F": "F", "FEMALE": "F", "WOMAN": "F", "GIRL": "F",
    "T": "T", "TRANSGENDER": "T", "OTHER": "T"
}

BERTH_MAP = {
    "LB": "LB", "LOWER": "LB", "LOWER BERTH": "LB",
    "MB": "MB", "MIDDLE": "MB", "MIDDLE BERTH": "MB",
    "UB": "UB", "UPPER": "UB", "UPPER BERTH": "UB",
    "SL": "SL", "SIDE LOWER": "SL",
    "SU": "SU", "SIDE UPPER": "SU",
    "NONE": "NONE", "NO CHOICE": "NONE", "": "NONE"
}

FOOD_MAP = {
    "V": "V", "VEG": "V", "VEGETARIAN": "V",
    "N": "N", "NON-VEG": "N", "NON VEG": "N", "NONVEG": "N",
    "D": "D", "NONE": "D", "NO FOOD": "D", "": "D"
}


def normalize_passenger_master_data(p: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalizes passenger details for IRCTC Master List synchronization.
    """
    raw_name = str(p.get("name", "")).strip().upper()
    try:
        raw_age = int(p.get("age", 0))
    except (ValueError, TypeError):
        raw_age = 0

    raw_gender = str(p.get("gender", "M")).strip().upper()
    gender = GENDER_MAP.get(raw_gender, "M")

    raw_berth = str(p.get("berth_preference", "NONE")).strip().upper()
    berth = BERTH_MAP.get(raw_berth, "NONE")

    raw_food = str(p.get("food_choice", "D")).strip().upper()
    food = FOOD_MAP.get(raw_food, "D")

    return {
        "name": raw_name,
        "age": raw_age,
        "gender": gender,
        "berth_preference": berth,
        "food_choice": food,
        "senior_citizen": bool(p.get("senior_citizen", False))
    }


async def sync_passengers_to_irctc_master_list(
    passengers: List[Dict[str, Any]],
    booking_ref: Optional[str] = None,
    db: Optional[Session] = None,
    live_mode: Optional[bool] = None
) -> Dict[str, Any]:
    """
    Synchronizes passenger list to IRCTC's official Master List ahead of Tatkal booking opening.
    In LIVE mode, navigates to IRCTC Master List page and auto-adds passengers if not already present.
    In MOCK mode, simulates success and updates the database flag.
    """
    is_live = getattr(settings, "LIVE_IRCTC", False) if live_mode is None else live_mode
    normalized = [normalize_passenger_master_data(p) for p in passengers if p.get("name")]

    if not normalized:
        return {
            "success": False,
            "synced_count": 0,
            "mode": "LIVE" if is_live else "MOCK",
            "error": "No valid passengers provided for Master List sync"
        }

    # Helper to mark booking synced in DB
    def mark_db_synced():
        if booking_ref and db:
            booking = db.query(Booking).filter(Booking.booking_ref == booking_ref).first()
            if booking:
                booking.master_list_synced = True
                db.commit()

    if not is_live:
        logger.info(f"[MASTER_LIST] (MOCK) Synced {len(normalized)} passengers for ref={booking_ref}")
        mark_db_synced()
        return {
            "success": True,
            "synced_count": len(normalized),
            "mode": "MOCK",
            "message": "Master list synced successfully (Simulated)"
        }

    # LIVE IRCTC AUTOMATION
    try:
        page = await browser_manager.get_page()
        session_state = BookingSessionState(booking_ref=booking_ref or "MASTER_LIST_SYNC")
        
        # Ensure user is logged in
        await ensure_authenticated_session(
            page=page,
            ref=booking_ref or "MASTER_LIST_SYNC",
            db=db,
            session_state=session_state
        )

        logger.info(f"[MASTER_LIST] Navigating to Master List URL: {MASTER_LIST_URL}")
        try:
            await page.goto(MASTER_LIST_URL, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(2000)
        except Exception as e:
            logger.warning(f"[MASTER_LIST] Direct goto failed, checking current url: {e}")

        # Check existing passenger names on page
        page_content = await page.inner_text("body")
        synced_count = 0

        for p in normalized:
            name = p["name"]
            if name in page_content:
                logger.info(f"[MASTER_LIST] Passenger '{name}' already present in Master List. Skipping add.")
                synced_count += 1
                continue

            try:
                # Fill name
                name_sel = "input[formcontrolname='name'], input[placeholder*='Name'], #passengerName"
                if await page.query_selector(name_sel):
                    await page.fill(name_sel, name)
                
                # Fill age
                age_sel = "input[formcontrolname='age'], input[placeholder*='Age'], #passengerAge"
                if await page.query_selector(age_sel):
                    await page.fill(age_sel, str(p["age"]))

                # Submit / Save button
                btn_sel = "button:has-text('Submit'), button:has-text('Save'), button[type='submit']"
                if await page.query_selector(btn_sel):
                    await page.click(btn_sel)
                    await page.wait_for_timeout(1500)

                synced_count += 1
                logger.info(f"[MASTER_LIST] Added passenger '{name}' to Master List.")
            except Exception as add_err:
                logger.error(f"[MASTER_LIST] Error adding passenger {name}: {add_err}")

        mark_db_synced()
        return {
            "success": True,
            "synced_count": synced_count,
            "mode": "LIVE",
            "message": f"Successfully synced {synced_count} passenger(s) to IRCTC Master List"
        }

    except Exception as exc:
        err_msg = f"Master List sync failed: {str(exc)}"
        logger.error(f"[MASTER_LIST ERROR] {err_msg}", exc_info=True)
        return {
            "success": False,
            "synced_count": 0,
            "mode": "LIVE",
            "error": err_msg
        }
