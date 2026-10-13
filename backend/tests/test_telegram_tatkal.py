import asyncio
import pytest
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from app.notifications.telegram_bot_service import TelegramBotService, user_chat_states
from app.database.connection import SessionLocal
from app.database.models import Booking

@pytest.fixture
def bot_service():
    return TelegramBotService()

@pytest.mark.asyncio
async def test_tatkal_command_initializes_state(bot_service):
    chat_id = "test_chat_tatkal_1"
    user_chat_states.pop(chat_id, None)

    with patch.object(bot_service, "_ask_route", new_callable=AsyncMock) as mock_ask_route, \
         patch("app.notifications.telegram_bot_service.send_telegram_message", new_callable=AsyncMock):
        
        await bot_service._handle_text_message(chat_id, "/tatkal")
        assert chat_id in user_chat_states
        state = user_chat_states[chat_id]
        assert state["data"].get("is_tatkal") is True
        assert mock_ask_route.called

@pytest.mark.asyncio
async def test_tatkal_quota_and_payment_selection(bot_service):
    chat_id = "test_chat_tatkal_2"
    user_chat_states[chat_id] = {
        "step": "ASK_TATKAL_QUOTA",
        "data": {
            "is_tatkal": True,
            "from_station": "NDLS",
            "to_station": "MMCT",
            "journey_date": "20/10/2026",
            "journey_class": "3A"
        }
    }

    with patch.object(bot_service, "_ask_passenger", new_callable=AsyncMock) as mock_ask_pax, \
         patch("app.notifications.telegram_bot_service.answer_callback_query", new_callable=AsyncMock):
        
        cb_quota = {"id": "cb1", "data": "tatkal_quota_PT", "message": {"chat": {"id": chat_id}}}
        await bot_service._handle_callback(cb_quota)

        state = user_chat_states[chat_id]
        assert state["data"]["tatkal_quota"] == "PT"

    # Now test payment selection callback
    user_chat_states[chat_id]["step"] = "ASK_TATKAL_PAYMENT"
    with patch.object(bot_service, "_show_summary_and_confirm", new_callable=AsyncMock) as mock_summary, \
         patch("app.notifications.telegram_bot_service.answer_callback_query", new_callable=AsyncMock):
        
        cb_pay = {"id": "cb2", "data": "tatkal_pay_UPI_QR", "message": {"chat": {"id": chat_id}}}
        await bot_service._handle_callback(cb_pay)

        state = user_chat_states[chat_id]
        assert state["data"]["preferred_payment_mode"] == "UPI_QR"

@pytest.mark.asyncio
async def test_execute_telegram_tatkal_booking(bot_service):
    chat_id = "test_chat_tatkal_3"
    future_date = (date.today() + timedelta(days=2)).strftime("%d/%m/%Y")
    data = {
        "is_tatkal": True,
        "from_station": "NDLS",
        "to_station": "CNB",
        "journey_date": future_date,
        "journey_class": "3A",
        "tatkal_quota": "TQ",
        "preferred_payment_mode": "UPI_QR",
        "passengers": [
            {"name": "Anil Verma", "age": 34, "gender": "M", "berth_preference": "LB"}
        ]
    }

    db = SessionLocal()
    created_ref = None

    try:
        with patch("app.notifications.telegram_bot_service.send_telegram_message", new_callable=AsyncMock) as mock_send_tg, \
             patch("app.notifications.telegram_bot_service.sync_passengers_to_irctc_master_list", new_callable=AsyncMock) as mock_sync:
            
            mock_sync.return_value = {"success": True, "synced_count": 1}
            await bot_service._execute_telegram_tatkal_booking(chat_id, data)
            # Allow background asyncio.create_task to run
            await asyncio.sleep(0.05)

            assert mock_send_tg.called
            # Verify DB record
            booking = db.query(Booking).filter(
                Booking.is_tatkal == True,
                Booking.from_station == "NDLS",
                Booking.to_station == "CNB"
            ).order_by(Booking.id.desc()).first()

            assert booking is not None
            created_ref = booking.booking_ref
            assert booking.status == "SCHEDULED_TATKAL"
            assert booking.tatkal_quota_type == "TQ"
            assert booking.preferred_payment_mode == "UPI_QR"
            assert booking.scheduled_trigger_time is not None
            # Master list sync should have been triggered
            assert mock_sync.called
    finally:
        if created_ref:
            b_clean = db.query(Booking).filter(Booking.booking_ref == created_ref).first()
            if b_clean:
                db.delete(b_clean)
                db.commit()
        db.close()
