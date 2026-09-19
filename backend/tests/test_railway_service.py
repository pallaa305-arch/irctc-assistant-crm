import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.railway_service import railway_service

@pytest.mark.asyncio
async def test_railway_service_pnr():
    # Test valid 10-digit PNR
    pnr_res = await railway_service.get_pnr_status("2451234567")
    assert pnr_res["success"] is True
    assert pnr_res["pnr"] == "2451234567"
    assert len(pnr_res["passengers"]) >= 1
    assert pnr_res["passengers"][0]["current_status"] == "CNF"

    # Test formatters for all 3 languages
    msg_hi = railway_service.format_pnr_message(pnr_res, lang="hi")
    assert "भारतीय रेल PNR स्थिति रिपोर्ट" in msg_hi
    assert "2451234567" in msg_hi

    msg_en = railway_service.format_pnr_message(pnr_res, lang="en")
    assert "Indian Railways PNR Status Report" in msg_en

    msg_hinglish = railway_service.format_pnr_message(pnr_res, lang="hinglish")
    assert "Indian Railways Live PNR Status" in msg_hinglish

    # Test invalid PNR
    invalid_pnr = await railway_service.get_pnr_status("12345")
    assert invalid_pnr["success"] is False

@pytest.mark.asyncio
async def test_railway_service_live_train():
    # Test known train (12952)
    train_res = await railway_service.get_live_train_status("12952")
    assert train_res["success"] is True
    assert train_res["train_number"] == "12952"
    assert "TEJAS RAJDHANI" in train_res["train_name"]

    # Test live train message formatters
    msg_hi = railway_service.format_live_train_message(train_res, lang="hi")
    assert "लाइव ट्रेन रनिंग स्थिति" in msg_hi

    msg_en = railway_service.format_live_train_message(train_res, lang="en")
    assert "Live Train Running Status" in msg_en

    msg_hinglish = railway_service.format_live_train_message(train_res, lang="hinglish")
    assert "Live Train Running Status" in msg_hinglish

@pytest.mark.asyncio
async def test_railway_service_search_trains():
    trains = await railway_service.search_trains("NDLS", "MMCT")
    assert len(trains) >= 1
    assert any(t["train_number"] == "12952" for t in trains)

@pytest.mark.asyncio
async def test_railway_api_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # PNR endpoint
        r_pnr = await ac.get("/api/railway/pnr/2451234567")
        assert r_pnr.status_code == 200
        assert r_pnr.json()["pnr"] == "2451234567"

        # Live train endpoint
        r_live = await ac.get("/api/railway/live/12952")
        assert r_live.status_code == 200
        assert r_live.json()["train_number"] == "12952"

        # Search trains endpoint
        r_search = await ac.get("/api/railway/search?from_station=NDLS&to_station=MMCT")
        assert r_search.status_code == 200
        assert len(r_search.json()["trains"]) >= 1
