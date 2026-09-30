# Personal IRCTC Booking Assistant

React dashboard, FastAPI backend, SQLite records, Excel export and a Telegram
booking wizard connected to one persistent IRCTC browser session.

## Live Telegram workflow

1. Select Live mode, then New Booking. The bot opens IRCTC and fills the saved
   credentials from the root `.env`. Complete login CAPTCHA yourself, or log in
   in the browser and press Verify Login.
2. Enter the From station and choose an actual IRCTC autocomplete suggestion.
3. Enter and choose the To station. Both fields are verified on the website.
4. Send DD/MM/YYYY (or aaj/kal/parso), then choose quota and comparison class.
5. The bot reads IRCTC train cards, timings and classes. In pages of five trains,
   it queries the website for the chosen class's real seat status and fare.
6. Choose train/class and review the exact-date quote. The bot never substitutes
   another train or class. Complete browser notices/Aadhaar OTP when requested.
7. Send Name Age Gender and optional berth, e.g. Rahul Kumar 28 M LB. Separate
   passengers with ; or send more messages. Every accepted list fills the website.
8. Press Done, then send the actual 10-digit contact mobile number.
9. Check the IRCTC review screenshot and exact total. Confirm explicitly and
   supply the review CAPTCHA if requested.
10. Complete payment in your app/browser. Supported iPay controls select UPI/QR;
    other gateway layouts may need manual selection in the browser. The bot
    forwards the genuine gateway QR when visible. A labeled PNR on the matching
    IRCTC confirmation page updates booking records, Excel and notifications.

Do not send banking OTPs or UPI PINs to the bot. The new Telegram wizard handles
CAPTCHA manually and does not call the legacy OCR module.

## State and data behavior

- One live browser booking at a time, shared with dashboard booking.
- Only the configured TELEGRAM_CHAT_ID can operate the personal account.
- Session/step revisions reject expired or duplicate buttons.
- Idle sessions expire after 15 minutes. Restart ends the in-memory wizard;
  stored records remain and queued old commands are not replayed.
- Verification monitors payment for up to ten minutes. After payment starts,
  timeout/cancel leaves PAYMENT_PENDING because it cannot prove payment failure.
  Check IRCTC Booked Ticket History before paying again.
- Cancel stops automation; it does not cancel an issued railway ticket.
- Missing prices/seats are reported as unavailable. Generated PNR, running-status,
  seat and fare values are restricted to demo mode.
- Local PDFs are booking records/expense summaries. Download official ERS and
  supplier tax invoices from IRCTC.

Website changes, downtime and expired authentication can interrupt the flow.
The adapter stops or asks for browser verification instead of inventing success.
The live public station/date controls were checked; authenticated checkout still
needs a real user-assisted verification run.

## Windows setup

Requires Python 3.10+ and Node.js 18+ for the frontend build.

```powershell
scripts\setup.bat
scripts\start.bat
```

Setup creates .venv, installs backend requirements and Playwright Chromium, and
builds the frontend. Launchers use .venv when available.
Settings load from the project root `.env`, not `backend/.env`.
Required fields: IRCTC_USERNAME, IRCTC_PASSWORD, TELEGRAM_BOT_TOKEN,
TELEGRAM_CHAT_ID, TELEGRAM_ENABLED=true and DEMO_MODE=false.
Use BROWSER_HEADLESS=false for visible browser checkpoints.

Dashboard: http://127.0.0.1:8000. API docs: http://127.0.0.1:8000/docs.
The bot operates without repeatedly bringing the browser to the foreground.

Manual start:

```powershell
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Tests

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest tests -q
```

Tests use a disposable database and exports under .pytest_cache and mock
Telegram. The browser integration fixture uses an isolated Chrome profile and
intercepts every request; it does not perform a real IRCTC purchase.

## Main files

- backend/app/automation/live_irctc.py: UI adapter and genuine response parsing.
- backend/app/notifications/live_booking.py: stepwise Telegram booking and payment monitor.
- backend/app/notifications/telegram_bot_service.py: polling/menu routing.
- backend/app/automation/browser_manager.py: persistent browser and booking ownership.
- backend/app/api/routes_booking.py: dashboard API and browser reservation guards.
- backend/app/crm/crm_service.py: database, Excel and notification finalization.

The dashboard's earlier complete-form flow remains in irctc_flow.py. Standalone
live PNR/running tools need verified data sources; seat/fare queries in the new
Telegram wizard come from the current IRCTC browser session.
