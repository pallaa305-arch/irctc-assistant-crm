import pytest
from app.agents.tools.train_tools import (
    tool_search_trains, 
    tool_check_availability,
    tool_calculate_fare,
    tool_check_pnr_status,
    resolve_station_code
)
from app.agents.tools.doc_tools import tool_export_crm_summary

def test_resolve_station_code():
    assert resolve_station_code("Delhi") == "NDLS"
    assert resolve_station_code("NDLS") == "NDLS"
    assert resolve_station_code("Mumbai") == "MMCT"
    assert resolve_station_code("Jammu") == "JAT"
    assert resolve_station_code("Varanasi") == "BSB"

@pytest.mark.asyncio
async def test_tool_search_trains():
    res = await tool_search_trains(origin="Delhi", destination="Mumbai", travel_date="2026-09-25")
    assert res.get("success") is True
    assert "trains" in res
    assert len(res["trains"]) > 0
    first_train = res["trains"][0]
    assert "train_number" in first_train
    assert "train_name" in first_train
    assert "classes" in first_train

@pytest.mark.asyncio
async def test_tool_check_availability():
    res = await tool_check_availability(train_number="12952", travel_date="2026-09-25", travel_class="3A")
    assert res.get("success") is True
    assert "status" in res
    assert "AVAILABLE" in res["status"] or "WL" in res["status"]

@pytest.mark.asyncio
async def test_tool_calculate_fare():
    res = await tool_calculate_fare(train_number="12952", travel_class="3A", passengers_count=2)
    assert res.get("success") is True
    assert res["total_fare"] > 0
    assert "breakdown" in res
    assert res["passengers_count"] == 2

@pytest.mark.asyncio
async def test_tool_check_pnr_status():
    res = await tool_check_pnr_status("2451234567")
    assert res.get("success") is True
    assert res["pnr"] == "2451234567"

@pytest.mark.asyncio
async def test_tool_export_crm():
    res = await tool_export_crm_summary()
    assert res.get("success") is True
