import os
import json
import asyncio
from typing import Any, Dict, Optional
import aiosqlite

DB_PATH = os.getenv("DB_PATH", "/app/data/db.sqlite")

SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    payload TEXT NOT NULL
);
"""

class HealthDatabase:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DB_PATH
        # ensure db dir exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    async def init(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(SCHEMA)
            await db.commit()

    async def save_report(self, data: Dict[str, Any]) -> int:
        """Persist a report dict and return its id."""
        await self.init()
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "INSERT INTO reports (payload) VALUES (?)",
                (json.dumps(data),),
            )
            await db.commit()
            return cur.lastrowid

    async def get_report(self, report_id: int) -> Optional[Dict[str, Any]]:
        await self.init()
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("SELECT payload FROM reports WHERE id = ?", (report_id,))
            row = await cur.fetchone()
            if not row:
                return None
            return json.loads(row[0])
