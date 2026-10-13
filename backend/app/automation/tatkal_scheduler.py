import asyncio
import inspect
import logging
from datetime import date, datetime, time, timedelta
from typing import Any, Callable, Dict, List, Optional
from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.database.models import Booking
from app.notifications.telegram import send_telegram_message

logger = logging.getLogger("tatkal_scheduler")

AC_CLASSES = {"1A", "2A", "3A", "3E", "CC", "EC", "EA", "EV"}


def compute_tatkal_timings(journey_date: date, journey_class: str) -> Dict[str, Any]:
    """
    Computes exact Tatkal opening and warmup timings for IRCTC.
    - AC Classes (1A, 2A, 3A, 3E, CC, EC, EA, EV): opens 10:00:00 AM IST on T-1 day.
    - Non-AC Classes (SL, 2S, etc.): opens 11:00:00 AM IST on T-1 day.
    - Warmup trigger is set to T-2 minutes (09:58 AM or 10:58 AM) to initialize browser,
      login, solve CAPTCHA, and pre-select train/quota before exact opening.
    """
    cls = (journey_class or "").strip().upper()
    is_ac = cls in AC_CLASSES
    category = "AC" if is_ac else "NON_AC"
    booking_date = journey_date - timedelta(days=1)
    opening_hour = 10 if is_ac else 11
    opening_time = datetime.combine(booking_date, time(opening_hour, 0, 0))
    warmup_time = opening_time - timedelta(minutes=2)

    return {
        "category": category,
        "booking_date": booking_date,
        "opening_time": opening_time,
        "warmup_time": warmup_time,
    }


def get_due_tatkal_bookings(db: Session, as_of: Optional[datetime] = None) -> List[Booking]:
    """
    Fetches all Tatkal bookings whose warmup time is due (<= as_of) and status is SCHEDULED_TATKAL.
    """
    now = as_of or datetime.now()
    return db.query(Booking).filter(
        Booking.is_tatkal == True,
        Booking.status == "SCHEDULED_TATKAL",
        Booking.scheduled_trigger_time <= now
    ).all()


async def check_and_trigger_due_tatkal_bookings(
    db: Session,
    as_of: Optional[datetime] = None,
    trigger_func: Optional[Callable] = None
) -> List[Booking]:
    """
    Finds due Tatkal bookings, transitions their status to IN_PROGRESS,
    sends a Telegram alert, and executes the booking automation.
    """
    due_bookings = get_due_tatkal_bookings(db, as_of=as_of)
    triggered: List[Booking] = []

    for booking in due_bookings:
        booking.status = "IN_PROGRESS"
        db.commit()
        db.refresh(booking)

        msg = (
            f"⚡ *Tatkal Warmup Triggered!*\n\n"
            f"🎫 Ref: `{booking.booking_ref}`\n"
            f"🚂 Train: `{booking.train_number or 'Auto'}` | Class: `{booking.journey_class}`\n"
            f"📅 Date: `{booking.journey_date}`\n"
            f"🎯 Quota: `{booking.tatkal_quota_type or 'TQ'}`\n"
            f"⚙️ Status: Browser warming up, precision countdown initiated!"
        )
        try:
            await send_telegram_message(msg)
        except Exception as exc:
            logger.error(f"Failed to send telegram notification for {booking.booking_ref}: {exc}")

        if trigger_func:
            try:
                if inspect.iscoroutinefunction(trigger_func):
                    await trigger_func(booking)
                else:
                    trigger_func(booking)
            except Exception as exc:
                logger.error(f"Custom trigger_func failed for {booking.booking_ref}: {exc}")
        else:
            try:
                from app.automation.irctc_flow import execute_booking_flow
                asyncio.create_task(execute_booking_flow(booking.booking_ref))
            except Exception as exc:
                logger.error(f"Failed to launch execute_booking_flow for {booking.booking_ref}: {exc}")

        triggered.append(booking)

    return triggered


async def start_tatkal_scheduler_loop(poll_interval: int = 5, stop_event: Optional[asyncio.Event] = None):
    """
    Continuous background loop polling database every poll_interval seconds
    to trigger Tatkal bookings at their scheduled warmup time.
    """
    logger.info(f"⚡ Tatkal Scheduler Loop started (polling every {poll_interval}s)")
    while stop_event is None or not stop_event.is_set():
        db = SessionLocal()
        try:
            await check_and_trigger_due_tatkal_bookings(db)
        except Exception as e:
            logger.error(f"Error in Tatkal Scheduler poll iteration: {e}", exc_info=True)
        finally:
            db.close()

        try:
            await asyncio.sleep(poll_interval)
        except asyncio.CancelledError:
            logger.info("Tatkal Scheduler Loop cancelled.")
            break
