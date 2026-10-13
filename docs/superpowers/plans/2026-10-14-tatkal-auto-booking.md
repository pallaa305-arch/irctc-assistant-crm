# Tatkal Automated Scheduling & Auto-Booking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an automated Tatkal booking scheduler that accepts customer journey details in advance, pre-syncs passengers with IRCTC Master List, warms up browser at T-2 minutes, triggers 'Book Now' at 10:00:00 AM (AC) / 11:00:00 AM (Non-AC) sharp, and provides both UPI QR and e-Wallet payment options.

**Architecture:** A FastAPI background scheduler monitors pending `SCHEDULED_TATKAL` bookings. At T-2 mins (09:58 / 10:58 AM), it launches a browser session, logs into IRCTC, and pre-navigates to the train search page. At T-0, it clicks Book Now, auto-fills or selects passengers from Master List, submits CAPTCHA, and delegates payment via Telegram Mobile UPI QR or IRCTC e-Wallet.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy (SQLite), Playwright Async, Telegram Bot API, Pytest.

---

## Global Constraints
- Target python executable: `C:\Users\Depk\AppData\Local\Programs\Python\Python314\python.exe`
- Obey immutability: create new objects, avoid mutation
- TDD required: Minimum 80% coverage on new code
- No hardcoded secrets or credentials; use `settings`
- No console.log / print debug statements in production files

---

### Task 1: Database Schema Extension (`models.py`)
**Files:**
- Modify: `backend/app/database/models.py`
- Test: `backend/tests/test_tatkal_models.py`

**Interfaces:**
- Produces: `Booking` attributes `is_tatkal: bool`, `tatkal_quota_type: str`, `scheduled_trigger_time: datetime`, `preferred_payment_mode: str`, `master_list_synced: bool`.

- [ ] **Step 1: Write failing test in `backend/tests/test_tatkal_models.py`**
- [ ] **Step 2: Run test to confirm failure**
- [ ] **Step 3: Update `backend/app/database/models.py` with the new columns**
- [ ] **Step 4: Run test to confirm it passes**
- [ ] **Step 5: Commit changes**

---

### Task 2: Tatkal Timing & Scheduler Engine (`tatkal_scheduler.py`)
**Files:**
- Create: `backend/app/automation/tatkal_scheduler.py`
- Test: `backend/tests/test_tatkal_scheduler.py`

**Interfaces:**
- Produces:
  - `compute_tatkal_timings(journey_date: date, journey_class: str) -> dict`
    Returns `{"opening_time": datetime, "warmup_time": datetime, "category": "AC" | "NON_AC"}`
  - `start_tatkal_scheduler_loop() -> asyncio.Task`
  - `trigger_scheduled_booking(booking_id: int)`

- [ ] **Step 1: Write failing tests for `compute_tatkal_timings` and scheduling checks**
- [ ] **Step 2: Run test to confirm failure**
- [ ] **Step 3: Implement `backend/app/automation/tatkal_scheduler.py`**
- [ ] **Step 4: Run test to confirm it passes**
- [ ] **Step 5: Commit changes**

---

### Task 3: IRCTC Master List Synchronization Helper (`master_list_sync.py`)
**Files:**
- Create: `backend/app/automation/master_list_sync.py`
- Test: `backend/tests/test_master_list_sync.py`

**Interfaces:**
- Produces:
  - `async def sync_passengers_to_irctc_master_list(passengers: list, db_session) -> bool`

- [ ] **Step 1: Write failing test with mocked Playwright page for Master List navigation & entry**
- [ ] **Step 2: Run test to confirm failure**
- [ ] **Step 3: Implement `master_list_sync.py`**
- [ ] **Step 4: Run test to confirm it passes**
- [ ] **Step 5: Commit changes**

---

### Task 4: Telegram Bot Interactive Tatkal Workflow
**Files:**
- Modify: `backend/app/notifications/telegram_bot_service.py`
- Test: `backend/tests/test_telegram_tatkal.py`

**Interfaces:**
- Produces:
  - Command `/tatkal` handler
  - Inline callback handlers for Quota (`set_quota_tq`, `set_quota_pt`)
  - Inline callback handlers for Payment Mode (`paymode_upi`, `paymode_ewallet`)
  - Tatkal scheduling summary confirmation card with action buttons

- [ ] **Step 1: Write failing tests in `test_telegram_tatkal.py` for `/tatkal` multi-step dialogue**
- [ ] **Step 2: Run test to confirm failure**
- [ ] **Step 3: Implement Tatkal conversation states and buttons in `telegram_bot_service.py`**
- [ ] **Step 4: Run test to confirm it passes**
- [ ] **Step 5: Commit changes**

---

### Task 5: Precision Tatkal Booking Execution in `irctc_flow.py`
**Files:**
- Modify: `backend/app/automation/irctc_flow.py`
- Test: `backend/tests/test_tatkal_flow.py`

**Interfaces:**
- Consumes: `booking.is_tatkal`, `booking.tatkal_quota_type`, `booking.preferred_payment_mode`
- Produces:
  - T-Zero clock synchronization wait until 10:00:00 / 11:00:00 IST
  - Master List 1-click passenger selection with fallback to direct keystrokes
  - Quota dropdown selection (`TATKAL` or `PREMIUM TATKAL`)
  - Payment routing to selected payment mode

- [ ] **Step 1: Write unit tests verifying Tatkal quota selection and clock sync logic**
- [ ] **Step 2: Implement precision timing and Master list selector in `irctc_flow.py`**
- [ ] **Step 3: Run test to confirm it passes**
- [ ] **Step 4: Commit changes**

---

### Task 6: Full Integration Verification & Server Restart
- [ ] **Step 1: Run complete backend pytest suite (`pytest backend/tests/ -q`)**
- [ ] **Step 2: Run Code Review via `code-reviewer` subagent**
- [ ] **Step 3: Restart FastAPI server and verify health endpoint**
- [ ] **Step 4: Push all commits to `origin/main`**
