"""
Real-Time Event Bus for Multi-Channel Personal IRCTC Assistant.
Allows decoupled dispatch of automation stages, train search results,
live IRCTC fare details, dynamic UPI QR codes, and CAPTCHA alerts.
"""
import time
import inspect
import logging
from typing import Dict, List, Callable, Any, Set

logger = logging.getLogger(__name__)

class EventBus:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(EventBus, cls).__new__(cls)
            cls._instance._session_subscribers: Dict[str, Set[Callable]] = {}
            cls._global_subscribers: Set[Callable] = set()
        return cls._instance

    def subscribe(self, session_id: str, callback: Callable):
        if session_id not in self._session_subscribers:
            self._session_subscribers[session_id] = set()
        self._session_subscribers[session_id].add(callback)

    def unsubscribe(self, session_id: str, callback: Callable):
        if session_id in self._session_subscribers:
            self._session_subscribers[session_id].discard(callback)
            if not self._session_subscribers[session_id]:
                del self._session_subscribers[session_id]

    def subscribe_global(self, callback: Callable):
        self._global_subscribers.add(callback)

    def unsubscribe_global(self, callback: Callable):
        self._global_subscribers.discard(callback)

    async def publish(self, session_id: str, event_type: str, data: Any):
        event = {
            "session_id": session_id,
            "type": event_type,
            "data": data,
            "timestamp": time.time()
        }

        callbacks = list(self._session_subscribers.get(session_id, set())) + list(self._global_subscribers)
        for cb in callbacks:
            try:
                if inspect.iscoroutinefunction(cb):
                    await cb(event)
                else:
                    cb(event)
            except Exception as e:
                logger.warning(f"Error dispatching event to callback {cb}: {e}")

event_bus = EventBus()
