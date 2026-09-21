"""
Session Management Module for Multi-Channel Personal IRCTC Assistant.
Provides in-memory caching with SQLite backing for session persistence across channels.
"""
import time
import json
import sqlite3
import threading
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
from app.config import settings

@dataclass
class SessionState:
    session_id: str
    channel: str = "web"  # "web" | "telegram"
    user_id: str = ""
    intent: str = "GENERAL"
    current_step: str = "IDLE"
    journey_data: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict[str, str]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

class SessionManager:
    _instance = None
    _lock = threading.RLock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(SessionManager, cls).__new__(cls)
                    cls._instance._init_manager()
        return cls._instance

    def _init_manager(self):
        self._sessions: Dict[str, SessionState] = {}
        self._db_path = str(settings.DATA_DIR / "assistant.db")
        self._init_db()

    def _init_db(self):
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS agent_sessions (
                        session_id TEXT PRIMARY KEY,
                        channel TEXT,
                        user_id TEXT,
                        intent TEXT,
                        current_step TEXT,
                        journey_data TEXT,
                        history TEXT,
                        created_at REAL,
                        updated_at REAL
                    )
                """)
                conn.commit()
        except Exception as e:
            # Non-fatal for SQLite init
            pass

    def get_or_create_session(self, session_id: str, channel: str = "web", user_id: str = "") -> SessionState:
        with self._lock:
            if session_id in self._sessions:
                return self._sessions[session_id]

            # Try loading from DB
            session = self._load_from_db(session_id)
            if session:
                self._sessions[session_id] = session
                return session

            # Create fresh
            new_session = SessionState(
                session_id=session_id,
                channel=channel,
                user_id=user_id
            )
            self._sessions[session_id] = new_session
            self._persist_to_db(new_session)
            return new_session

    def get_session(self, session_id: str) -> Optional[SessionState]:
        with self._lock:
            if session_id in self._sessions:
                return self._sessions[session_id]
            session = self._load_from_db(session_id)
            if session:
                self._sessions[session_id] = session
            return session

    def update_session(self, session_id: str, **kwargs) -> Optional[SessionState]:
        with self._lock:
            session = self.get_session(session_id)
            if not session:
                session = self.get_or_create_session(session_id)
            
            for key, val in kwargs.items():
                if hasattr(session, key):
                    setattr(session, key, val)
            session.updated_at = time.time()
            self._persist_to_db(session)
            return session

    def add_message(self, session_id: str, role: str, content: str) -> List[Dict[str, str]]:
        with self._lock:
            session = self.get_session(session_id)
            if not session:
                session = self.get_or_create_session(session_id)
            session.history.append({"role": role, "content": content, "timestamp": time.time()})
            # Bound history to last 30 turns
            if len(session.history) > 30:
                session.history = session.history[-30:]
            session.updated_at = time.time()
            self._persist_to_db(session)
            return session.history

    def get_history(self, session_id: str) -> List[Dict[str, str]]:
        session = self.get_session(session_id)
        if session:
            return session.history
        return []

    def reset_session_step(self, session_id: str):
        with self._lock:
            session = self.get_session(session_id)
            if session:
                session.current_step = "IDLE"
                session.journey_data = {}
                session.updated_at = time.time()
                self._persist_to_db(session)

    def _persist_to_db(self, session: SessionState):
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO agent_sessions 
                    (session_id, channel, user_id, intent, current_step, journey_data, history, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(session_id) DO UPDATE SET
                        channel=excluded.channel,
                        user_id=excluded.user_id,
                        intent=excluded.intent,
                        current_step=excluded.current_step,
                        journey_data=excluded.journey_data,
                        history=excluded.history,
                        updated_at=excluded.updated_at
                """, (
                    session.session_id,
                    session.channel,
                    session.user_id,
                    session.intent,
                    session.current_step,
                    json.dumps(session.journey_data),
                    json.dumps(session.history),
                    session.created_at,
                    session.updated_at
                ))
                conn.commit()
        except Exception:
            pass

    def _load_from_db(self, session_id: str) -> Optional[SessionState]:
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT session_id, channel, user_id, intent, current_step, journey_data, history, created_at, updated_at
                    FROM agent_sessions WHERE session_id = ?
                """, (session_id,))
                row = cursor.fetchone()
                if row:
                    return SessionState(
                        session_id=row[0],
                        channel=row[1] or "web",
                        user_id=row[2] or "",
                        intent=row[3] or "GENERAL",
                        current_step=row[4] or "IDLE",
                        journey_data=json.loads(row[5]) if row[5] else {},
                        history=json.loads(row[6]) if row[6] else [],
                        created_at=row[7] or time.time(),
                        updated_at=row[8] or time.time()
                    )
        except Exception:
            pass
        return None

session_manager = SessionManager()
