import pytest
from app.services.station_cache import station_cache
from app.services.railway_service import railway_service


def test_station_cache_loaded():
    """Verify master offline stations dataset is loaded."""
    stations = station_cache.stations_by_code
    assert len(stations) >= 50
    assert "NDLS" in stations
    assert "MMCT" in stations
    assert "CNB" in stations
    assert "BSB" in stations
    assert "LKO" in stations


def test_primary_hubs_precedence():
    """Verify major Indian city names resolve directly to primary railway hubs."""
    assert station_cache.resolve_station_code("Delhi") == "NDLS"
    assert station_cache.resolve_station_code("New Delhi") == "NDLS"
    assert station_cache.resolve_station_code("Mumbai") == "MMCT"
    assert station_cache.resolve_station_code("Bombay") == "MMCT"
    assert station_cache.resolve_station_code("Lucknow") == "LKO"
    assert station_cache.resolve_station_code("Varanasi") == "BSB"
    assert station_cache.resolve_station_code("Banaras") == "BSB"
    assert station_cache.resolve_station_code("Kanpur") == "CNB"
    assert station_cache.resolve_station_code("Gorakhpur") == "GKP"
    assert station_cache.resolve_station_code("Patna") == "PNBE"
    assert station_cache.resolve_station_code("Bengaluru") == "SBC"
    assert station_cache.resolve_station_code("Bangalore") == "SBC"


def test_station_autocomplete_search():
    """Verify fuzzy autocomplete station searching."""
    results = station_cache.search_stations("delhi", limit=5)
    assert len(results) > 0
    codes = [r["code"] for r in results]
    assert "NDLS" in codes


@pytest.mark.asyncio
async def test_intermediate_stop_train_search():
    """Verify train search matches trains with intermediate stops."""
    # Kanpur to New Delhi should match Rajdhani / Vande Bharat passing through CNB
    trains = await railway_service.search_trains("CNB", "NDLS")
    assert len(trains) > 0
    train_nums = [t["train_number"] for t in trains]
    assert any(num in ["22435", "12301", "12555", "12419"] for num in train_nums)
