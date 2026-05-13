"""
VestaCode Project Store
=======================
SQLite-backed persistence for BIMProjectState.
No external dependencies — uses Python's built-in sqlite3.
"""

import sqlite3
import json
import os
from datetime import datetime, timezone
from typing import List, Optional

DB_PATH = os.environ.get("VESTA_DB_PATH", "backend/data/projects.db")


class ProjectStore:
    def __init__(self):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    project_id  TEXT PRIMARY KEY,
                    name        TEXT NOT NULL,
                    updated_at  TEXT NOT NULL,
                    data        TEXT NOT NULL
                )
            """)

    def save(self, project) -> None:
        """Persist a BIMProjectState (upsert by project_id)."""
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO projects (project_id, name, updated_at, data)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                    name       = excluded.name,
                    updated_at = excluded.updated_at,
                    data       = excluded.data
                """,
                (project.project_id, project.name, now, project.model_dump_json()),
            )

    def load(self, project_id: str):
        """Return a BIMProjectState or None."""
        from backend.core.bim_state import BIMProjectState
        with self._conn() as conn:
            row = conn.execute(
                "SELECT data FROM projects WHERE project_id = ?", (project_id,)
            ).fetchone()
        if not row:
            return None
        return BIMProjectState.model_validate_json(row["data"])

    def list_projects(self) -> List[dict]:
        """Return lightweight project summaries (no full BIM data)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT project_id, name, updated_at FROM projects ORDER BY updated_at DESC"
            ).fetchall()
        return [
            {"project_id": r["project_id"], "name": r["name"], "updated_at": r["updated_at"]}
            for r in rows
        ]

    def delete(self, project_id: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))
        return cur.rowcount > 0
