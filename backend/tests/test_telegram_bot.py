import pytest
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch
from app.automation.flow_state import get_or_create_session, get_latest_waiting_session, clear_all_waiting_sessions
from app.notifications.telegram_bot_service import telegram_bot_service, user_chat_states, user_languages

@pytest.fixture(autouse=True)
def clean_test_state():
    clear_all_waiting_sessions()
    user_chat_states.clear()
    yield
    clear_all_waiting_sessions()
    user_chat_states.clear()

@pytest.mark.asyncio
async def test_telegram_captcha_reply_routing():
    # 1. Setup a waiting session
    ref = "BK-TEST-TG-001"
    session = get_or_create_session(ref)
    session.pause_for_user("Please solve CAPTCHA", is_payment=False, input_type="CAPTCHA")

    assert session.is_paused is True
    assert session.waiting_input_type == "CAPTCHA"

    # 2. Simulate user sending text message in Telegram
    with patch("app.notifications.telegram_bot_service.send_telegram_message", new_callable=AsyncMock) as mock_send:
        await telegram_bot_service._handle_text_message("12345678", "X9K2L")

        assert session.user_input_value == "X9K2L"
        assert session.is_paused is False
        assert session.input_event.is_set()
        mock_send.assert_called_once()
        assert "CAPTCHA Received" in mock_send.call_args[0][0]

@pytest.mark.asyncio
async def test_telegram_callback_continue_and_cancel():
    ref = "BK-TEST-TG-002"
    session = get_or_create_session(ref)
    session.pause_for_user("Payment required", is_payment=True, input_type="PAYMENT")

    with patch("app.notifications.telegram_bot_service.answer_callback_query", new_callable=AsyncMock), \
         patch("app.notifications.telegram_bot_service.send_telegram_message", new_callable=AsyncMock):

        cb = {
            "id": "cb_1",
            "data": "action_continue",
            "message": {"chat": {"id": 12345678}}
        }
        await telegram_bot_service._handle_callback(cb)

        assert session.is_paused is False
        assert session.status == "IN_PROGRESS"

@pytest.mark.asyncio
async def test_natural_language_and_auto_save():
    from app.notifications.telegram_bot_service import (
        resolve_station,
        parse_date_natural,
        parse_passenger_info,
        auto_save_passenger_to_db
    )
    from app.database.connection import SessionLocal
    from app.database.models import Passenger

    # 1. Station resolution
    assert resolve_station("Delhi") == "NDLS"
    assert resolve_station("Varanasi") == "BSB"
    assert resolve_station("Mumbai") == "MMCT"

    # 2. Date parsing
    assert parse_date_natural("kal") is not None
    assert parse_date_natural("parso") is not None

    # 3. Passenger parsing & auto-save
    pax = parse_passenger_info("Deepak Kataria 28 M")
    assert pax["name"] == "Deepak Kataria"
    assert pax["age"] == 28
    assert pax["gender"] == "M"

    auto_save_passenger_to_db(pax)
    db = SessionLocal()
    try:
        saved = db.query(Passenger).filter(Passenger.name == "Deepak Kataria").first()
        assert saved is not None
        assert saved.age == 28
        # Clean up test pax
        db.delete(saved)
        db.commit()
    finally:
        db.close()

@pytest.mark.asyncio
async def test_validate_and_parse_journey_date():
    from app.notifications.telegram_bot_service import validate_and_parse_journey_date

    today = date.today()
    past_date_explicit = (today - timedelta(days=2)).strftime("%d/%m/%Y")
    past_date_no_year = (today - timedelta(days=2)).strftime("%d/%m")
    future_date = (today + timedelta(days=5)).strftime("%d/%m/%Y")
    too_far_date = (today + timedelta(days=150)).strftime("%d/%m/%Y")

    # 1. Valid future dates
    d, status, _ = validate_and_parse_journey_date("kal")
    assert status == "OK"
    assert d == (today + timedelta(days=1)).strftime("%d/%m/%Y")

    d, status, _ = validate_and_parse_journey_date("parso")
    assert status == "OK"
    assert d == (today + timedelta(days=2)).strftime("%d/%m/%Y")

    d, status, _ = validate_and_parse_journey_date(future_date)
    assert status == "OK"
    assert d == future_date

    # 2. Past dates must be rejected
    d, status, detail = validate_and_parse_journey_date(past_date_explicit)
    assert status == "PAST_DATE"
    assert d is None
    assert detail == (today - timedelta(days=2)).strftime("%d/%m/%Y")

    d, status, detail = validate_and_parse_journey_date(past_date_no_year)
    assert status == "PAST_DATE"
    assert d is None

    d, status, _ = validate_and_parse_journey_date("yesterday")
    assert status == "PAST_DATE"
    assert d is None

    # 3. Beyond 120-day ARP limit
    d, status, _ = validate_and_parse_journey_date(too_far_date)
    assert status == "TOO_FAR"
    assert d is None

    # 4. Invalid input
    d, status, _ = validate_and_parse_journey_date("random text")
    assert status == "INVALID_FORMAT"
    assert d is None

@pytest.mark.asyncio
async def test_validate_and_parse_journey_date_extended_formats():
    from app.notifications.telegram_bot_service import validate_and_parse_journey_date

    today = date.today()

    # Exact 120-day ARP boundary
    d_120 = today + timedelta(days=120)
    d_121 = today + timedelta(days=121)

    d, status, _ = validate_and_parse_journey_date(d_120.strftime("%d/%m/%Y"))
    assert status == "OK"
    assert d == d_120.strftime("%d/%m/%Y")

    d, status, _ = validate_and_parse_journey_date(d_121.strftime("%d/%m/%Y"))
    assert status == "TOO_FAR"
    assert d is None

    # ISO Format (YYYY-MM-DD)
    iso_date = today + timedelta(days=10)
    d, status, _ = validate_and_parse_journey_date(iso_date.strftime("%Y-%m-%d"))
    assert status == "OK"
    assert d == iso_date.strftime("%d/%m/%Y")

    # Ordinals e.g. "15th Oct"
    target_d = today + timedelta(days=5)
    ordinal_day = f"{target_d.day}th" if target_d.day not in [1, 2, 3, 21, 22, 23, 31] else f"{target_d.day}st"
    month_name = target_d.strftime("%b")
    text_input = f"{ordinal_day} {month_name}"
    d, status, _ = validate_and_parse_journey_date(text_input)
    assert status == "OK"
    assert d == target_d.strftime("%d/%m/%Y")

@pytest.mark.asyncio
async def test_telegram_ask_date_rejects_past_date():
    chat_id = "888888"
    user_languages[chat_id] = "hinglish"
    user_chat_states[chat_id] = {
        "step": "ASK_DATE",
        "data": {"from_station": "NDLS", "to_station": "BCT"}
    }
    today = date.today()
    past_d = (today - timedelta(days=2)).strftime("%d/%m")

    with patch("app.notifications.telegram_bot_service.send_telegram_message", new_callable=AsyncMock) as mock_send, \
         patch.object(telegram_bot_service, "_ask_date", new_callable=AsyncMock):
        await telegram_bot_service._handle_text_message(chat_id, past_d)

        # State should still be ASK_DATE
        assert user_chat_states[chat_id]["step"] == "ASK_DATE"
        assert "journey_date" not in user_chat_states[chat_id]["data"]

        # Alert message sent to user
        mock_send.assert_called()
        sent_text = mock_send.call_args_list[0][0][0]
        assert "beet chuki hai" in sent_text or "passed" in sent_text

@pytest.mark.asyncio
async def test_unauthorized_credentials_command_blocked():
    from app.config import settings
    attacker_chat_id = "999888777"  # Different from settings.TELEGRAM_CHAT_ID

    with patch("app.notifications.telegram_bot_service.send_telegram_message", new_callable=AsyncMock) as mock_send:
        await telegram_bot_service._handle_text_message(attacker_chat_id, "/credentials hacked_user hacked_pass")
        mock_send.assert_called_once()
        assert "Unauthorized" in mock_send.call_args[0][0] or "administrator" in mock_send.call_args[0][0]

@pytest.mark.asyncio
async def test_telegram_greeting_does_not_consume_captcha():
    user_languages["999999"] = "hinglish"
    ref = "BK-TEST-TG-003"
    session = get_or_create_session(ref)
    session.pause_for_user("Please solve visual CAPTCHA", is_payment=False, input_type="CAPTCHA")

    with patch("app.notifications.telegram_bot_service.send_telegram_message", new_callable=AsyncMock) as mock_send:
        # Send "hii" while waiting for CAPTCHA
        await telegram_bot_service._handle_text_message("999999", "hii")

        # Session must NOT treat "hii" as CAPTCHA, and instead clears session and sends friendly welcome menu
        assert session.user_input_value != "hii"
        assert session.status == "CANCELLED"
        mock_send.assert_called_once()
        # Verifies that a clean IRCTC welcome menu is sent without nagging about active bookings
        assert "IRCTC" in mock_send.call_args[0][0] or "Welcome" in mock_send.call_args[0][0]

@pytest.mark.asyncio
async def test_telegram_cancellation():
    ref = "BK-TEST-TG-004"
    session = get_or_create_session(ref)
    session.pause_for_user("Please solve visual CAPTCHA", is_payment=False, input_type="CAPTCHA")

    with patch("app.notifications.telegram_bot_service.send_telegram_message", new_callable=AsyncMock) as mock_send:
        await telegram_bot_service._handle_text_message("999999", "cancel")
        assert session.status == "CANCELLED"
        mock_send.assert_called_once()
