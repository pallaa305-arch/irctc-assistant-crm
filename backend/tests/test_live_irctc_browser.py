"""Offline browser integration tests using the real adapter, never the user's profile.

Fixture markup covers the observed PrimeNG search controls and the supported train
card/availability contract. It does not certify the external IRCTC checkout layout.
"""
from datetime import date, timedelta
import json

import pytest
from playwright.async_api import async_playwright

from app.automation.browser_manager import browser_manager
from app.automation.live_irctc import LiveIRCTC, HOME


@pytest.mark.asyncio
async def test_real_browser_adapter_search_availability_and_exact_train_selection(monkeypatch):
    day = date.today() + timedelta(days=7)
    day_text = day.strftime("%d/%m/%Y")
    html = """<html><body>
    <p-autocomplete id="origin" formcontrolname="origin"><input value="NEW DELHI - NDLS"></p-autocomplete>
    <p-autocomplete id="destination" formcontrolname="destination"><input value="JAMMU TAWI - JAT"></p-autocomplete>
    <p-calendar id="jDate"><input></p-calendar>
    <button onclick="document.querySelector('#results').hidden=false">Search Trains</button>
    <section id="results" hidden>
      <app-train-avl-enq id="wrong"><div class="train-heading">OTHER TRAIN (99999)</div>10:00 15:00
        <div class="pre-avl">AC 3 Tier (3A)</div><button onclick="window.wrongTrain=true">Book Now</button>
      </app-train-avl-enq>
      <app-train-avl-enq id="right"><div class="train-heading">JAMMU TRAIN (12425)</div>20:40 05:00
        <div class="pre-avl" onclick="loadAvailability()">AC 3 Tier (3A)</div>
        <div class="pre-avl" id="slot" onclick="window.daySelected=true">DATE_HERE AVAILABLE-99</div>
        <button onclick="if(window.daySelected) document.querySelector('#passengers').hidden=false">Book Now</button>
      </app-train-avl-enq>
    </section>
    <div id="passengers" hidden><input placeholder="Passenger Name"></div>
    <script>
      async function loadAvailability() {
        const r = await fetch('/eticketing/protected/mapps1/avlFareEnq/12425/DATE_QUERY/NDLS/JAT/3A/GN/N');
        const q = await r.json();
        document.querySelector('#slot').innerText = 'DATE_HERE ' + q.avlDayList[0].availablityStatus;
      }
    </script></body></html>""".replace("DATE_HERE", day_text).replace("DATE_QUERY", day.strftime("%Y%m%d"))
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, channel="chrome")
        try:
            context = await browser.new_context()
            async def route(request):
                if "avlFareEnq" in request.request.url:
                    await request.fulfill(content_type="application/json", body=json.dumps({"trainNo": "12425", "enqClass": "3A", "totalFare": "1830.40", "avlDayList": [{"availablityDate": day.strftime("%d-%m-%Y"), "availablityStatus": "AVAILABLE-12"}]}))
                else:
                    await request.fulfill(content_type="text/html", body=html)
            # Intercept every URL. These tests cannot contact IRCTC or another server.
            await context.route("**/*", route)
            page = await context.new_page()
            await page.goto(HOME)
            monkeypatch.setattr(browser_manager, "owner", "offline-test")
            driver = LiveIRCTC("offline-test")
            driver.page = page
            driver.station_labels = {"from": "NEW DELHI - NDLS", "to": "JAMMU TAWI - JAT"}
            await driver.set_date(day_text)
            trains = await driver.search()
            assert [t["train_number"] for t in trains] == ["99999", "12425"]
            assert trains[1]["departure_time"] == "20:40"
            quote = await driver.availability("12425", "3A")
            assert quote["fare"] == 1830.40
            assert quote["status"] == "AVAILABLE-12"  # Never the stale 99 seats.
            await driver.book_selected()
            assert await page.locator("input[placeholder='Passenger Name']").is_visible()
            assert not await page.evaluate("Boolean(window.wrongTrain)")
        finally:
            await browser.close()
