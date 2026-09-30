import asyncio
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.automation.browser_manager import BrowserManager, browser_manager
from app.automation.live_irctc import LivePageError, LiveIRCTC, parse_train_cards, parse_availability, parse_confirmation, parse_availability_response
from app.notifications.live_booking import Conversation, LiveBookingWizard, parse_passengers
from app.config import settings
from app.database.connection import SessionLocal
from app.database.models import Booking


class FakeIRCTC:
    def __init__(self, owner):
        self.owner = owner
        self.open = AsyncMock(return_value=False)
        self.login = AsyncMock(return_value=True)
        self.challenge_image = AsyncMock(return_value=b"captcha")
        self.stations = AsyncMock(return_value=["NEW DELHI - NDLS (NEW DELHI)"])
        self.select_station = AsyncMock(side_effect=["NDLS", "JAT"])
        self.set_date = AsyncMock()
        self.set_quota = AsyncMock()
        self.search = AsyncMock(return_value=[{"train_number": "12425", "train_name": "JAMMU RAJDHANI (12425)", "classes": ["3A", "2A"], "departure_time": "20:40", "arrival_time": "05:00"}])
        self.availability = AsyncMock(return_value={"class_code": "3A", "status": "AVAILABLE-12", "fare": 1750.0, "checked_at": "2026-09-29T12:00Z"})
        self.book_selected = AsyncMock(return_value=True)
        self.fill_passengers = AsyncMock()
        self.fill_contact = AsyncMock()
        self.review = AsyncMock(return_value={"total_fare": 1830.40, "screenshot": b"review"})
        self.proceed_payment = AsyncMock(return_value=b"payment")
        self.payment_snapshot = AsyncMock(return_value=None)
        self.confirmation = AsyncMock(return_value=None)
        self.released = False

    def release(self):
        self.released = True


@pytest.fixture
def wizard(monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_CHAT_ID", "123")
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    w = LiveBookingWizard(FakeIRCTC)
    with patch("app.notifications.live_booking.send_telegram_message", new_callable=AsyncMock) as send, patch("app.notifications.live_booking.send_telegram_photo", new_callable=AsyncMock):
        w.send = send
        yield w
    for s in w.sessions.values():
        if s.monitor:
            s.monitor.cancel()


async def click(w, action, value=""):
    return await w.handle("123", callback=w.sessions["123"].callback(action, value))


@pytest.mark.asyncio
async def test_every_telegram_step_updates_same_browser_and_persists_real_review(wizard):
    w = wizard
    await w.handle("123", callback="cmd_book")
    s = w.sessions["123"]
    driver = s.driver
    assert s.step == "LOGIN"
    driver.open.assert_awaited_once()
    await w.handle("123", text="aB12x")
    driver.login.assert_awaited_once_with("aB12x")
    await w.handle("123", text="Delhi")
    await click(w, "station", "0")
    assert s.step == "TO"
    await w.handle("123", text="Jammu")
    await click(w, "station", "0")
    dt = date.today() + timedelta(days=10)
    await w.handle("123", text=dt.strftime("%d/%m/%Y"))
    driver.set_date.assert_awaited_once_with(dt.strftime("%d/%m/%Y"))
    await click(w, "quota", "GN")
    await click(w, "compare", "3A")
    driver.search.assert_awaited_once()
    await click(w, "train", "12425")
    await click(w, "class", "3A")
    assert s.data["quote"]["fare"] == 1750.0
    await click(w, "select")
    driver.book_selected.assert_awaited_once()
    await w.handle("123", text="Example Passenger 28 M LB; Second Passenger 25 F UB")
    driver.fill_passengers.assert_awaited_once()
    await click(w, "paxdone")
    await w.handle("123", text="9000000001")
    assert s.step == "REVIEW"
    assert s.data["total_fare"] == 1830.40
    await click(w, "confirm")
    assert s.step == "REVIEW_CAPTCHA"
    # Exact server-side snapshot persisted; no guessed seat or fare.
    with SessionLocal() as db:
        b = db.get(Booking, s.booking_id)
        assert b.fare == 1830.40
        assert b.pnr is None
        assert b.train_number == "12425"
        assert len(b.passengers) == 2
        assert all(p.status == "PENDING" and p.allocated_seat is None for p in b.passengers)
    await w.handle("123", text="xY34z")
    driver.proceed_payment.assert_awaited_once_with("xY34z")
    assert s.step == "PAYMENT"
    assert s.driver is driver
    await click(w, "cancel")
    assert driver.released
    with SessionLocal() as db:
        assert db.get(Booking, s.booking_id).status == "PAYMENT_PENDING"


@pytest.mark.asyncio
async def test_old_buttons_and_duplicate_start_cannot_reset_or_mutate_session(wizard):
    await wizard.handle("123", callback="cmd_book")
    s = wizard.sessions["123"]
    old = s.callback("station", "0")
    await wizard.handle("123", callback="cmd_book")
    assert wizard.sessions["123"] is s
    await wizard.handle("123", text="captcha")
    await wizard.handle("123", callback=old)
    s.driver.select_station.assert_not_awaited()
    assert "purana" in wizard.send.call_args.args[0]


@pytest.mark.asyncio
async def test_unauthorized_chat_cannot_start_or_cancel_owner(wizard):
    await wizard.handle("999", callback="cmd_book")
    assert "999" not in wizard.sessions
    await wizard.handle("123", callback="cmd_book")
    s = wizard.sessions["123"]
    await wizard.handle("999", callback=s.callback("cancel"))
    assert not s.driver.released


@pytest.mark.asyncio
async def test_failed_site_write_does_not_advance_or_claim_success(wizard):
    await wizard.handle("123", callback="cmd_book")
    s = wizard.sessions["123"]
    wizard.stage(s, "DATE")
    s.driver.set_date.side_effect = LivePageError("Date was rejected")
    await wizard.handle("123", text="01/10/2027")
    assert s.step == "DATE"
    assert "journey_date" not in s.data
    s.driver.search.assert_not_awaited()


@pytest.mark.asyncio
async def test_parallel_duplicate_selection_is_rejected_after_revision_change(wizard):
    await wizard.handle("123", callback="cmd_book")
    s = wizard.sessions["123"]
    wizard.stage(s, "FROM_CHOICE")
    s.choices = ["NEW DELHI - NDLS"]
    callback = s.callback("station", "0")
    await asyncio.gather(wizard.handle("123", callback=callback), wizard.handle("123", callback=callback))
    s.driver.select_station.assert_awaited_once()
    assert s.step == "TO"


@pytest.mark.asyncio
async def test_missing_fare_is_displayed_as_unknown(wizard):
    await wizard.handle("123", callback="cmd_book")
    s = wizard.sessions["123"]
    wizard.stage(s, "CLASS")
    s.data.update(train={"train_number": "12425"}, journey_date=date.today())
    s.driver.availability.return_value["fare"] = None
    await click(wizard, "class", "3A")
    assert "visible nahi" in wizard.send.call_args.args[0]
    assert "₹0" not in wizard.send.call_args.args[0]


def test_browser_ownership_blocks_another_flow_and_wrong_release():
    manager = BrowserManager()
    manager.claim("one")
    with pytest.raises(RuntimeError):
        manager.claim("two")
    manager.release("two")
    assert manager.owner == "one"
    manager.release("one")
    manager.claim("two")
    assert manager.owner == "two"


@pytest.mark.parametrize("text", ["Phone: 9876543210", "Payment successful TXN 2451234567", "PNR: 12345", "Total 2000"])
def test_confirmation_never_treats_phone_or_transaction_as_pnr(text):
    assert parse_confirmation(text) is None


def test_labeled_confirmation_and_availability_exact_date():
    assert parse_confirmation("PNR No.: 2451234567 Transaction ID: 123456789012") == {"pnr": "2451234567", "transaction_id": "123456789012"}
    q = parse_availability("Sun, 04 Oct\nAVAILABLE-0012", date(2026, 10, 4), "3A")
    assert q["status"] == "AVAILABLE-0012"
    with pytest.raises(LivePageError):
        parse_availability("05/10/2026 AVAILABLE-99", date(2026, 10, 4), "3A")
    with pytest.raises(LivePageError):
        parse_availability("04/10/2026 Loading…", date(2026, 10, 4), "3A")


def test_unknown_train_card_fields_remain_unknown():
    trains = parse_train_cards([{"heading": "TRAIN (12425)", "text": "AC 3 Tier (3A)"}, {"heading": "Loading…"}])
    assert len(trains) == 1
    assert trains[0]["arrival_time"] is None
    assert "fare" not in trains[0]


@pytest.mark.parametrize("text", ["A 28 M", "Someone 0 M", "Someone 150 F", "Someone 28 X", "Someone", "Someone 28 M; malformed"])
def test_passenger_validation(text):
    with pytest.raises(LivePageError):
        parse_passengers(text)


@pytest.mark.asyncio
async def test_gateway_navigation_is_pending_not_failed(monkeypatch):
    d = LiveIRCTC("test")
    from unittest.mock import MagicMock
    d.page = MagicMock()
    d.page.is_closed.return_value = False
    d.page.url = "https://payments.example.test/upi"
    monkeypatch.setattr(browser_manager, "owner", "test")
    assert await d.confirmation() is None


@pytest.mark.asyncio
async def test_cancel_interrupts_slow_site_request(wizard):
    started = asyncio.Event()
    async def slow_open():
        started.set()
        await asyncio.Event().wait()
    def factory(owner):
        driver = FakeIRCTC(owner)
        driver.open = slow_open
        return driver
    wizard.driver_factory = factory
    task = asyncio.create_task(wizard.handle("123", callback="cmd_book"))
    await started.wait()
    s = wizard.sessions["123"]
    await asyncio.wait_for(wizard.handle("123", callback=s.callback("cancel")), timeout=2)
    assert task.cancelled()
    assert s.step == "CANCELLED"
    assert s.driver.released


@pytest.mark.asyncio
async def test_demo_mode_never_opens_real_browser(wizard, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    await wizard.handle("123", callback="cmd_book")
    assert not wizard.sessions
    assert "Demo mode" in wizard.send.call_args.args[0]


def test_response_data_requires_exact_date_and_train_class():
    raw = {"trainNo": "12425", "enqClass": "3A", "totalFare": "1,830.40", "avlDayList": [{"availablityDate": "04-10-2026", "availablityStatus": "GNWL12/WL8"}]}
    q = parse_availability_response(raw, date(2026, 10, 4), "12425", "3A")
    assert q["fare"] == 1830.40
    assert q["status"] == "GNWL12/WL8"
    for day, train, cls in [(date(2026, 10, 5), "12425", "3A"), (date(2026, 10, 4), "99999", "3A"), (date(2026, 10, 4), "12425", "SL")]:
        with pytest.raises(LivePageError):
            parse_availability_response(raw, day, train, cls)


@pytest.mark.asyncio
async def test_browser_otp_checkpoint_resumes_without_second_book_now(wizard):
    await wizard.handle("123", callback="cmd_book")
    s = wizard.sessions["123"]
    wizard.stage(s, "QUOTE")
    s.driver.book_selected.return_value = False
    s.driver.passenger_ready = AsyncMock(return_value=True)
    await click(wizard, "select")
    assert s.step == "TRAIN_CHECKPOINT"
    await click(wizard, "passenger_ready")
    assert s.step == "PASSENGERS"
    s.driver.book_selected.assert_awaited_once()


@pytest.mark.asyncio
async def test_live_mode_disables_generated_fares_and_status(monkeypatch):
    from app.agents.tools.train_tools import tool_calculate_fare, tool_check_availability
    from app.services.railway_service import RailwayService
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    service = RailwayService()
    service.rapidapi_key = ""
    for result in [await tool_calculate_fare("12425", "3A"), await tool_check_availability("12425", "04/10/2026", "3A"), await service.get_pnr_status("2345678901"), await service.get_live_train_status("12425"), service.get_seat_availability("12425", "NDLS", "JAT", "04/10/2026")]:
        assert result["success"] is False
        assert result.get("error")


@pytest.mark.asyncio
async def test_confirmed_pnr_updates_db_and_exports_once(wizard):
    from app.database.models import BookingPassenger
    s = Conversation("123")
    s.driver = FakeIRCTC(s.ref)
    s.data["payment_started"] = True
    with SessionLocal() as db:
        b = Booking(booking_ref=s.ref, from_station="NDLS", to_station="JAT", journey_date=date.today(), status="PAYMENT_PENDING")
        db.add(b)
        db.commit()
        s.booking_id = b.id
    wizard.sessions["123"] = s
    wizard.stage(s, "PAYMENT")
    s.driver.confirmation.return_value = {"pnr": "2345678901", "transaction_id": "123456789012", "screenshot": b"real-confirmation"}
    with patch("app.notifications.live_booking.asyncio.sleep", new_callable=AsyncMock), patch("app.crm.crm_service.finalize_successful_booking", new_callable=AsyncMock) as finalize:
        await wizard.monitor(s)
    with SessionLocal() as db:
        b = db.get(Booking, s.booking_id)
        assert b.pnr == "2345678901" and b.payment_status == "COMPLETED"
    finalize.assert_awaited_once()
    assert s.step == "DONE" and s.driver.released
