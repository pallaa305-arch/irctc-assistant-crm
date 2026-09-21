# Technical Design Specification: Unified AI Backend, Agent Router & Multi-Channel Integration

- **Date**: 2026-09-21
- **Status**: Approved by User
- **Authors**: AI Engineering Assistant & User

---

## 1. Executive Summary & Problem Statement

The Personal IRCTC Booking Assistant currently maintains fragmented conversational logic. The Telegram bot (`telegram_bot_service.py`) manages internal multi-turn booking states separately from the Web UI (`routes_booking.py`), resulting in duplicated code, out-of-sync booking progress, and brittle conversational flow.

This design establishes a **single, channel-agnostic AI Backend & Agent Router**. Both the Telegram Bot and the Web Frontend connect to the exact same core AI agent loop. The Agent Router parses natural language (Hinglish/Hindi/English) via Gemini function calling (with an offline regex/lexicon fallback), manages sessions via a persistent `SessionManager`, executes standardized tools on the IRCTC Automation Engine, and streams live events (progress stages, train cards, official IRCTC calculated fares, dynamic UPI QR codes) in real-time over WebSockets and Telegram push notifications.

---

## 2. System Architecture & Component Design

```
┌──────────────────┐               ┌──────────────────┐
│   Telegram Bot   │               │   Web Frontend   │
│  (python-tele..) │               │  (React / Vite)  │
└────────┬─────────┘               └────────┬─────────┘
         │ (Push / Webhook)                 │ (REST & WebSocket)
         ▼                                  ▼
┌─────────────────────────────────────────────────────┐
│               Channel Adapters Layer                │
│   - TelegramChannelAdapter                          │
│   - WebChannelAdapter                               │
└──────────────────────────┬──────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────┐
│                 Unified Agent Router                │
│  - Session Manager (SQLite + In-Memory)             │
│  - Intent Classifier & Slot Extractor               │
│  - Google Gemini 1.5/2.5 Flash Tool Calling Loop   │
│  - Fallback Deterministic Natural Language Matcher  │
└──────────┬───────────────────────┬──────────────────┘
           │                       │
           ▼                       ▼
┌──────────────────────┐  ┌───────────────────────────┐
│ Train Booking Agent  │  │ General FAQ / CRM / Docs  │
│  - search_trains     │  │  - get_pnr_status         │
│  - check_avail       │  │  - download_ticket_pdf    │
│  - calculate_fare    │  │  - export_bookings_excel  │
│  - initiate_booking  │  │  - general_chat_reply     │
└──────────┬───────────┘  └───────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────┐
│        Playwright IRCTC Automation Engine           │
│  - Headful Browser / Anti-Detection Chrome Profile  │
│  - Popup Dismissal (Language, Alerts, Banners)      │
│  - Live Real-Time IRCTC Fare & Quota Extraction     │
│  - Passenger Autofill & Live Dynamic UPI QR         │
└──────────────────────────┬──────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────┐
│                Real-Time Event Bus                  │
│  - Broadcasts STAGE_UPDATE, TRAIN_RESULTS, FARE,    │
│    CAPTCHA_REQUIRED, QR_READY, BOOKING_CONFIRMED    │
│  - Web UI: WebSocket `/ws/chat/{session_id}`        │
│  - Telegram: Live editMessageText & sendPhoto       │
└─────────────────────────────────────────────────────┘
```

---

## 3. Detailed Subsystem Specifications

### 3.1. Unified Agent Router (`backend/app/agents/router.py`)
- **Input Contract**:
  - `session_id: str`: Unique session identifier (e.g. `web_abc123` or `tg_7875481582`).
  - `channel: str`: `"web"` or `"telegram"`.
  - `user_message: str`: User text input or structured callback identifier.
- **Workflow**:
  1. Retrieve active session context from `SessionManager`.
  2. Append user message to conversation history.
  3. Invoke LLM Function Calling loop (`gemini-1.5-flash`) providing tool schemas for `train_search`, `check_availability`, `calculate_fare`, `initiate_booking`, `check_pnr_status`, and `general_chat_reply`.
  4. If LLM encounters an API quota/connectivity error, route immediately through internal deterministic parser (`StationLexicon` + Date regex + Passenger pattern).
  5. Execute chosen tool asynchronously, emitting real-time stage updates to the `EventBus`.
  6. Return standardized `AgentResponse(text, action_type, payload, session_state)`.

### 3.2. Standardized Agent Tools (`backend/app/agents/tools/`)
- **`train_search(origin: str, destination: str, travel_date: str)`**:
  - Validates station names against IRCTC station code dictionary (e.g., "Delhi" ➔ `NDLS`, "Jaipur" ➔ `JP`).
  - Calls automation engine to search trains or uses railway cache.
  - Returns list of train items: `[{train_number, train_name, from_time, to_time, duration, classes}]`.
- **`check_availability(train_number: str, travel_date: str, travel_class: str, quota: str = "GN")`**:
  - Queries live availability for the selected train and class.
  - Returns status: `{"status": "AVAILABLE-0042", "fare": 1120.0, "last_updated": "..."}`.
- **`calculate_fare(train_number: str, travel_class: str, passengers_count: int)`**:
  - Scrapes the exact live fare container from IRCTC DOM (Base Fare, Reservation Charge, Superfast Surcharge, IRCTC Convenience Fee, GST).
  - Returns accurate breakdown.
- **`initiate_booking(train_number: str, travel_class: str, date: str, passengers: list[dict])`**:
  - Triggers Playwright automation to enter passengers, select preferences, and proceed to payment review.
  - Emits `CAPTCHA_REQUIRED` event if CAPTCHA appears, or proceeds directly to Payment QR.
  - Captures UPI QR screenshot from IRCTC and emits `PAYMENT_QR_READY` with countdown timer.
- **`check_pnr_status(pnr: str)`**:
  - Queries live PNR status and returns passenger chart status, coach, and berth numbers.

### 3.3. Multi-Channel Session Manager (`backend/app/sessions/session_manager.py`)
- **State Model**:
  ```python
  class SessionState:
      session_id: str
      channel: str  # "web" | "telegram"
      user_id: str
      current_step: str  # IDLE, SEARCHING, SELECTING_TRAIN, PASSENGER_INPUT, AWAITING_QR, CONFIRMED
      journey_data: dict  # from_station, to_station, date, quota, selected_train, fare, passengers
      history: list[dict]  # [{role: "user"|"assistant", content: str}]
      updated_at: float
  ```
- **Storage**:
  - In-memory fast cache with SQLite table `agent_sessions` write-through on every transition.
  - Channels maintain independent conversation threads while querying the same underlying automation state and database.

### 3.4. Real-Time Event Bus (`backend/app/agents/event_bus.py`)
- Async pub/sub router.
- Channels register listeners:
  - Web registers WebSocket client connection at `/ws/chat/{session_id}`.
  - Telegram registers chat callback handler for `chat_id`.
- Emits events:
  - `STAGE_UPDATE`: automation stage and progress message.
  - `TRAIN_RESULTS`: list of trains for interactive card rendering.
  - `FARE_DETAILS`: live fare breakdown.
  - `CAPTCHA_REQUIRED`: base64 image + challenge id.
  - `PAYMENT_QR_READY`: base64 QR code image, amount, expiry countdown.
  - `BOOKING_CONFIRMED`: PNR, status, and PDF download link.

### 3.5. Channel Adapters
- **`TelegramChannelAdapter`**:
  - Converts incoming Telegram messages and button callbacks into `AgentRouter.handle_message(...)`.
  - Converts outgoing `AgentResponse` and `EventBus` payloads into Telegram markdown, inline button keyboards, and photo messages (for QR code & CAPTCHA).
- **`WebChannelAdapter`**:
  - Exposes REST endpoint `POST /api/chat` for synchronous request-response.
  - Exposes WebSocket endpoint `WS /ws/chat/{session_id}` for bi-directional real-time event streaming.

### 3.6. Frontend Conversational UI (`frontend/src/pages/AIAssistant.jsx`)
- **Theme & Aesthetics**:
  - High-polish dark developer aesthetic (Linear/Raycast palette: `#090d16` background, `#111827` cards, emerald `#10b981` status pulses, cyan `#06b6d4` AI badges).
- **Interactive Widgets**:
  - `<TrainResultsCard />`: Clean train list with quick-select class badges (`1A`, `2A`, `3A`, `SL`) and live availability indicators.
  - `<FareBreakdownCard />`: Transparent official IRCTC fee itemization.
  - `<LivePaymentQRModal />`: Dynamic QR display with 5-minute countdown ring, copy UPI button, and auto-polling payment confirmation.
  - `<CaptchaFallbackDrawer />`: Instant popover for manual CAPTCHA/OTP resolution if IRCTC triggers verification.
  - `<LiveAutomationTimeline />`: Real-time visual radar on the right drawer showing browser automation steps.

---

## 4. Error Handling & Recovery Strategies

1. **LLM Connectivity Failure**: Seamless automatic fallback to deterministic regex & station lexicon parser. Zero crash, zero user-facing timeout.
2. **IRCTC Popups & Overlays**: Auto-dismissal of language prompts, COVID/general advisories, and login prompts.
3. **Session Resumption**: Persistent session storage allows users to refresh the browser or re-open Telegram without losing active booking progress.
4. **Duplicate Booking Prevention**: Locking mechanism prevents concurrent browser automation executions on the same session.

---

## 5. Testing & Verification Plan

1. **Unit & Functional Tests (`backend/tests/test_agent_system.py`)**:
   - `test_session_manager_persistence`: Verify state transitions and SQLite persistence.
   - `test_agent_router_tool_calling`: Verify Gemini function schemas and fallback parser on Hinglish/English queries.
   - `test_train_tools_interface`: Test train search, availability, and fare calculation output contracts.
   - `test_event_bus_broadcast`: Verify WebSocket and Telegram event delivery.
2. **Channel Parity Test**:
   - Verify that sending `"Delhi to Jammu tomorrow 3A"` via Telegram adapter and via `/api/chat` triggers identical tool execution and returns identical train lists.
3. **Live Automation Verification**:
   - Launch search on official IRCTC portal.
   - Verify dynamic fare extraction and QR code rendering.
