"""SQLite 会话存储 — 持久化对话历史、项目约定。"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path


class SessionStore:
    """管理 Agent 会话和对话轮次的持久化存储。"""

    def __init__(self, db_path: str = ".myagent/sessions.db"):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._init_db()

    def _init_db(self):
        self._conn.execute("PRAGMA journal_mode=DELETE")
        self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    task_description TEXT NOT NULL,
                    project_path TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'running',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL REFERENCES sessions(id),
                    step_number INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    action_type TEXT,
                    action_result TEXT,
                    feedback_passed BOOLEAN,
                    token_count INTEGER DEFAULT 0,
                    latency_ms INTEGER DEFAULT 0,
                    created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS conventions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT NOT NULL UNIQUE,
                    value TEXT NOT NULL,
                    source TEXT DEFAULT 'user',
                    created_at REAL NOT NULL
                );
            """)

    def create_session(self, session_id: str, task: str, project_path: str) -> None:
        now = time.time()
        self._conn.execute(
            "INSERT INTO sessions (id, task_description, project_path, status, created_at, updated_at) VALUES (?, ?, ?, 'running', ?, ?)",
            (session_id, task, project_path, now, now),
        )
        self._conn.commit()

    def update_session_status(self, session_id: str, status: str) -> None:
        self._conn.execute(
            "UPDATE sessions SET status = ?, updated_at = ? WHERE id = ?",
            (status, time.time(), session_id),
        )
        self._conn.commit()

    def record_turn(
        self,
        session_id: str,
        step_number: int,
        role: str,
        content: str,
        action_type: str = "",
        action_result: str = "",
        feedback_passed: bool | None = None,
        token_count: int = 0,
        latency_ms: int = 0,
    ) -> None:
        self._conn.execute(
            """INSERT INTO turns (session_id, step_number, role, content, action_type,
               action_result, feedback_passed, token_count, latency_ms, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (session_id, step_number, role, content, action_type, action_result, feedback_passed, token_count, latency_ms, time.time()),
        )
        self._conn.commit()

    def get_recent_turns(self, session_id: str, limit: int = 20) -> list[dict]:
        self._conn.row_factory = sqlite3.Row
        rows = self._conn.execute(
            "SELECT * FROM turns WHERE session_id = ? ORDER BY step_number DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
        self._conn.row_factory = None
        return [dict(r) for r in reversed(rows)]

    def set_convention(self, key: str, value: str, source: str = "user") -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO conventions (key, value, source, created_at) VALUES (?, ?, ?, ?)",
            (key, value, source, time.time()),
        )
        self._conn.commit()

    def get_convention(self, key: str) -> str | None:
        row = self._conn.execute(
            "SELECT value FROM conventions WHERE key = ?", (key,)
        ).fetchone()
        return row[0] if row else None

    def get_all_conventions(self) -> dict[str, str]:
        rows = self._conn.execute("SELECT key, value FROM conventions").fetchall()
        return {r[0]: r[1] for r in rows}

    def close(self) -> None:
        self._conn.close()
