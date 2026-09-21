# Unified AI Agent Backend & Multi-Channel Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a channel-agnostic AI Backend with an Agent Router, standard tools, shared session manager, and real-time WebSocket event bus, connecting both the Telegram Bot and a redesigned Frontend Conversational Assistant to the exact same IRCTC automation engine.

**Architecture:** A unified `AgentRouter` processes messages from Telegram and Web channels using Gemini Function Calling (with a local regex/lexicon fallback). State is managed via `SessionManager` and streamed in real-time via `EventBus` to both WebSockets and Telegram. The frontend provides a rich conversational UI with interactive inline cards for train selection, live fare breakdown, dynamic UPI QR codes, and CAPTCHA handling.

**Tech Stack:** Python 3.10+, FastAPI, WebSockets, Google Generative AI (Gemini Flash), Playwright, SQLite, React, Vite, Tailwind CSS, Lucide Icons.

**Spec:** `docs/superpowers/specs/2026-09-21-unified-ai-agent-architecture-design.md`

## Global Constraints
- Telegram and Web UI must execute the exact same core backend logic and tools.
- Headful Playwright browser (`headless=False`) must remain intact for IRCTC automation.
- Fares must be calculated dynamically from IRCTC; no hardcoded fares.
- Automatic fallback to deterministic station/date parsing if Gemini API key is unset or unreachable.

---

### Task 1: Persistent Session Manager

**Files:**
- Create: `backend/app/sessions/session_manager.py`
- Test: `backend/tests/test_session_manager.py`

**Interfaces:**
- Produces: `SessionManager`, `SessionState`, `session_manager.get_or_create_session(session_id, channel, user_id)`, `session_manager.update_session(session_id, **kwargs)`, `session_manager.add_message(session_id, role, content)`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_session_manager.py
import pytest
from app.sessions.session_manager import SessionManager, SessionState

def test_session_creation_and_retrieval():
    mgr = SessionManager()
    session = mgr.get_or_create_session("web_test_1", channel="web", user_id="user_1")
    assert session.session_id == "web_test_1"
    assert session.channel == "web"
    assert session.current_step == "IDLE"

def test_session_state_updates():
    mgr = SessionManager()
    mgr.get_or_create_session("tg_123", channel="telegram", user_id="123")
    mgr.update_session("tg_123", current_step="SEARCHING", journey_data={"from_station": "NDLS", "to_station": "JAT"})
    session = mgr.get_session("tg_123")
    assert session.current_step == "SEARCHING"
    assert session.journey_data["from_station"] == "NDLS"

def test_session_message_history():
    mgr = SessionManager()
    mgr.get_or_create_session("s1", "web", "u1")
    mgr.add_message("s1", "user", "Book train from Delhi to Jaipur")
    mgr.add_message("s1", "assistant", "Searching trains...")
    history = mgr.get_history("s1")
    assert len(history) == 2
    assert history[0]["content"] == "Book train from Delhi to Jaipur"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_session_manager.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.sessions'`

- [ ] **Step 3: Implement SessionManager**

Create `backend/app/sessions/session_manager.py` with dataclass `SessionState` and thread-safe `SessionManager` backed by SQLite/memory.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_session_manager.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/sessions/session_manager.py backend/tests/test_session_manager.py
git commit -m "feat(agents): implement persistent multi-channel SessionManager"
```

---

### Task 2: Real-Time Event Bus

**Files:**
- Create: `backend/app/agents/event_bus.py`
- Test: `backend/tests/test_event_bus.py`

**Interfaces:**
- Produces: `EventBus`, `event_bus.subscribe(session_id, callback)`, `event_bus.unsubscribe(session_id, callback)`, `event_bus.publish(session_id, event_type, data)`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_event_bus.py
import pytest
import asyncio
from app.agents.event_bus import EventBus

@pytest.mark.asyncio
async def test_event_bus_publish_subscribe():
    bus = EventBus()
    received = []

    async def sample_listener(event):
        received.append(event)

    bus.subscribe("session_xyz", sample_listener)
    await bus.publish("session_xyz", "STAGE_UPDATE", {"stage": "SEARCHING", "message": "Searching trains..."})

    assert len(received) == 1
    assert received[0]["type"] == "STAGE_UPDATE"
    assert received[0]["data"]["stage"] == "SEARCHING"

    bus.unsubscribe("session_xyz", sample_listener)
    await bus.publish("session_xyz", "STAGE_UPDATE", {"stage": "DONE", "message": "Done"})
    assert len(received) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_event_bus.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.agents.event_bus'`

- [ ] **Step 3: Implement EventBus**

Create `backend/app/agents/event_bus.py` with async subscriber dispatching and error shielding.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_event_bus.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/event_bus.py backend/tests/test_event_bus.py
git commit -m "feat(agents): implement real-time EventBus for WebSocket and Telegram dispatch"
```

---

### Task 3: Standardized Agent Tools

**Files:**
- Create: `backend/app/agents/tools/train_tools.py`
- Create: `backend/app/agents/tools/doc_tools.py`
- Test: `backend/tests/test_agent_tools.py`

**Interfaces:**
- Produces: `tool_search_trains(origin, destination, date)`, `tool_check_availability(train_no, date, cls, quota)`, `tool_calculate_fare(train_no, cls, count)`, `tool_initiate_booking(train_no, cls, date, passengers)`, `tool_check_pnr_status(pnr)`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_agent_tools.py
import pytest
from app.agents.tools.train_tools import tool_search_trains, tool_check_pnr_status

@pytest.mark.asyncio
async def test_tool_search_trains_validation():
    # Validates station resolution and search payload structure
    res = await tool_search_trains("Delhi", "Jammu", "2026-09-25")
    assert "trains" in res or "error" in res

@pytest.mark.asyncio
async def test_tool_check_pnr_format():
    res = await tool_check_pnr_status("1234567890")
    assert "pnr" in res
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_agent_tools.py -v`
Expected: FAIL

- [ ] **Step 3: Implement train_tools and doc_tools**

Create `backend/app/agents/tools/train_tools.py` and `backend/app/agents/tools/doc_tools.py` wiring directly to `RailwayService`, `irctc_flow`, and `pdf_service`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_agent_tools.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/tools/ backend/tests/test_agent_tools.py
git commit -m "feat(agents): implement standardized train and document tools"
```

---

### Task 4: Unified Agent Router with Gemini Function Calling & Fallback

**Files:**
- Create: `backend/app/agents/router.py`
- Test: `backend/tests/test_agent_router.py`

**Interfaces:**
- Produces: `AgentRouter`, `agent_router.handle_message(session_id, user_message, channel)` returning `AgentResponse`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_agent_router.py
import pytest
from app.agents.router import AgentRouter

@pytest.mark.asyncio
async def test_router_handles_train_intent():
    router = AgentRouter()
    resp = await router.handle_message(
        session_id="test_sess_1",
        user_message="Delhi se Jammu 25 September ki train check karo",
        channel="web"
    )
    assert resp is not None
    assert resp.text != ""
    assert resp.action_type in ("TRAIN_LIST", "STAGE_UPDATE", "NONE")

@pytest.mark.asyncio
async def test_router_handles_pnr_intent():
    router = AgentRouter()
    resp = await router.handle_message(
        session_id="test_sess_2",
        user_message="Check PNR 2451234567",
        channel="web"
    )
    assert resp is not None
    assert "2451234567" in resp.text or resp.payload.get("pnr") == "2451234567"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_agent_router.py -v`
Expected: FAIL

- [ ] **Step 3: Implement AgentRouter**

Create `backend/app/agents/router.py`:
- Gemini Tool Calling definitions (`GEMINI_API_KEY` from settings or fallback).
- Local deterministic regex/lexicon fallback when API key is not present.
- Session updates and EventBus event emitting.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_agent_router.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/router.py backend/tests/test_agent_router.py
git commit -m "feat(agents): implement AgentRouter with Gemini function calling and fallback parser"
```

---

### Task 5: Web API & WebSocket Endpoints

**Files:**
- Create: `backend/app/api/routes_chat.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_routes_chat.py`

**Interfaces:**
- Produces: `POST /api/chat`, `GET /api/chat/history/{session_id}`, `WebSocket /ws/chat/{session_id}`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_routes_chat.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_chat_endpoint_responds():
    res = client.post("/api/chat", json={
        "session_id": "web_unit_test",
        "message": "Hello",
        "channel": "web"
    })
    assert res.status_code == 200
    data = res.json()
    assert "text" in data
    assert "action_type" in data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_routes_chat.py -v`
Expected: FAIL with 404 Not Found

- [ ] **Step 3: Implement routes_chat.py and mount in main.py**

Create `backend/app/api/routes_chat.py` supporting REST and WebSocket with live EventBus subscription.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_routes_chat.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/routes_chat.py backend/app/main.py backend/tests/test_routes_chat.py
git commit -m "feat(api): add /api/chat and /ws/chat endpoints wired to AgentRouter"
```

---

### Task 6: Rewire Telegram Bot to Unified AgentRouter

**Files:**
- Create: `backend/app/notifications/telegram_channel_adapter.py`
- Modify: `backend/app/notifications/telegram_bot_service.py`
- Test: `backend/tests/test_telegram_adapter.py`

**Interfaces:**
- Routes all incoming Telegram text messages and button callback queries directly into `AgentRouter.handle_message(...)`.
- Subscribes Telegram chat to `EventBus` to push real-time automation stage updates and QR photo messages.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_telegram_adapter.py
import pytest
from app.notifications.telegram_channel_adapter import TelegramChannelAdapter

@pytest.mark.asyncio
async def test_telegram_adapter_translates_message():
    adapter = TelegramChannelAdapter()
    resp = await adapter.process_user_text(chat_id=7875481582, text="Search train Delhi to Jaipur")
    assert resp is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_telegram_adapter.py -v`
Expected: FAIL

- [ ] **Step 3: Implement TelegramChannelAdapter & wire into telegram_bot_service.py**

Implement adapter and delegate message handling from `telegram_bot_service.py` to `TelegramChannelAdapter`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_telegram_adapter.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/notifications/telegram_channel_adapter.py backend/app/notifications/telegram_bot_service.py backend/tests/test_telegram_adapter.py
git commit -m "refactor(telegram): rewire bot to channel-agnostic AgentRouter and EventBus"
```

---

### Task 7: Frontend Conversational UI & Interactive Components

**Files:**
- Create: `frontend/src/pages/AIAssistant.jsx`
- Create: `frontend/src/components/chat/TrainResultsCard.jsx`
- Create: `frontend/src/components/chat/FareBreakdownCard.jsx`
- Create: `frontend/src/components/chat/LivePaymentQRModal.jsx`
- Create: `frontend/src/components/chat/CaptchaFallbackDrawer.jsx`
- Create: `frontend/src/components/chat/LiveAutomationTimeline.jsx`
- Modify: `frontend/src/components/Sidebar.jsx`
- Modify: `frontend/src/App.jsx`

**Interfaces:**
- Connects to `/api/chat` and `/ws/chat/{session_id}`.
- Renders conversational messages, live typing indicator, and interactive micro-cards.

- [ ] **Step 1: Create interactive widgets**

Implement `<TrainResultsCard />`, `<FareBreakdownCard />`, `<LivePaymentQRModal />`, `<CaptchaFallbackDrawer />`, `<LiveAutomationTimeline />` following the Linear/Raycast design system.

- [ ] **Step 2: Create AIAssistant.jsx page**

Implement responsive 2-column layout with message stream on the left and live automation radar on the right.

- [ ] **Step 3: Integrate AIAssistant into Sidebar and App.jsx routing**

Add "AI Assistant" navigation item with Sparkles icon.

- [ ] **Step 4: Verify frontend build**

Run: `npm --prefix frontend run build`
Expected: Build succeeds with 0 errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): build Conversational AI Assistant with real-time WebSocket widgets"
```

---

### Task 8: End-to-End System Verification & Regression Tests

**Files:**
- Modify: `backend/tests/test_e2e_unified_agent.py`

- [ ] **Step 1: Run comprehensive backend test suite**

Run: `pytest backend/tests -v`
Expected: All tests pass.

- [ ] **Step 2: Manual End-to-End Verification**
- Send search request from Web UI Chat (`/api/chat`). Verify train cards render with live availability.
- Verify live WebSocket stages stream to `LiveAutomationTimeline`.
- Send message from Telegram. Verify parity in response.
- Verify CAPTCHA / UPI QR code generation and modal popup.

- [ ] **Step 3: Commit final integration verification**

```bash
git add backend/tests/
git commit -m "test(e2e): add end-to-end verification tests for unified AI agent system"
```
