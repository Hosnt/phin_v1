"""
Persistent memory for Phin.

Two layers:
1. `conversations` — rolling log of recent turns (for short-term context window).
2. `facts` — durable key/value facts about the user ("favorite_editor" -> "VS Code"),
   set explicitly via the `remember` tool so memory doesn't bloat with junk.
"""
import sqlite3
import time
from core.config import Config


class Memory:
    def __init__(self):
        self.conn = sqlite3.connect(Config.MEMORY_DB, check_same_thread=False)
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                ts REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS facts (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                ts REAL NOT NULL
            );
        """)
        self.conn.commit()

    # --- conversation log ---
    def add_turn(self, role: str, content: str):
        self.conn.execute(
            "INSERT INTO conversations (role, content, ts) VALUES (?, ?, ?)",
            (role, content, time.time()),
        )
        self.conn.commit()

    def recent_turns(self, limit: int = 20) -> list[dict]:
        rows = self.conn.execute(
            "SELECT role, content FROM conversations ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [{"role": r, "content": c} for r, c in reversed(rows)]

    # --- durable facts ---
    def remember(self, key: str, value: str):
        self.conn.execute(
            "INSERT INTO facts (key, value, ts) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, ts=excluded.ts",
            (key, value, time.time()),
        )
        self.conn.commit()

    def recall(self, key: str) -> str | None:
        row = self.conn.execute("SELECT value FROM facts WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def all_facts(self) -> dict:
        rows = self.conn.execute("SELECT key, value FROM facts").fetchall()
        return {k: v for k, v in rows}

    def facts_as_context(self) -> str:
        facts = self.all_facts()
        if not facts:
            return "No stored facts about the user yet."
        return "\n".join(f"- {k}: {v}" for k, v in facts.items())
