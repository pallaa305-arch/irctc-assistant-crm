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

@pytest.mark.asyncio
async def test_event_bus_global_subscribe():
    bus = EventBus()
    received = []

    async def global_listener(event):
        received.append(event)

    bus.subscribe_global(global_listener)
    await bus.publish("session_123", "ALERT", {"msg": "System online"})
    assert len(received) == 1
    assert received[0]["session_id"] == "session_123"

    bus.unsubscribe_global(global_listener)
    await bus.publish("session_123", "ALERT", {"msg": "System offline"})
    assert len(received) == 1
