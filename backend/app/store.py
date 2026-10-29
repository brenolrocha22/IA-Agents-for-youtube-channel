"""Persistência SQLite: documentos Pydantic, logs resumidos e cache HTTP."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from .config import data_dir
from .models import now

M = TypeVar("M", bound=BaseModel)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
  kind TEXT NOT NULL, id TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  data TEXT NOT NULL, PRIMARY KEY (kind, id));
CREATE INDEX IF NOT EXISTS idx_records_kind ON records(kind, created_at);
CREATE TABLE IF NOT EXISTS logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, level TEXT NOT NULL, source TEXT NOT NULL,
  task_id TEXT, message TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS http_cache (
  key TEXT PRIMARY KEY, fetched_at REAL NOT NULL, ttl_s INTEGER NOT NULL, body TEXT NOT NULL);
"""


class Store:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        with self._conn() as c:
            c.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    # --- documentos ---
    def put(self, kind: str, doc: BaseModel) -> None:
        doc_id = getattr(doc, "id")
        data = doc.model_dump_json()
        ts = now().isoformat()
        with self._lock, self._conn() as c:
            c.execute(
                "INSERT INTO records(kind,id,created_at,updated_at,data) VALUES(?,?,?,?,?) "
                "ON CONFLICT(kind,id) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at",
                (kind, doc_id, ts, ts, data),
            )

    def get(self, kind: str, doc_id: str, cls: type[M]) -> M | None:
        with self._conn() as c:
            row = c.execute("SELECT data FROM records WHERE kind=? AND id=?", (kind, doc_id)).fetchone()
        return cls.model_validate_json(row["data"]) if row else None

    def list(self, kind: str, cls: type[M], limit: int | None = None) -> list[M]:
        sql = "SELECT data FROM records WHERE kind=? ORDER BY created_at DESC, rowid DESC"
        params: tuple[Any, ...] = (kind,)
        if limit:
            sql += " LIMIT ?"
            params += (limit,)
        with self._conn() as c:
            rows = c.execute(sql, params).fetchall()
        return [cls.model_validate_json(r["data"]) for r in rows]

    def delete(self, kind: str, doc_id: str) -> None:
        with self._lock, self._conn() as c:
            c.execute("DELETE FROM records WHERE kind=? AND id=?", (kind, doc_id))

    def count(self, kind: str) -> int:
        with self._conn() as c:
            return c.execute("SELECT COUNT(*) FROM records WHERE kind=?", (kind,)).fetchone()[0]

    # --- logs ---
    def log(self, level: str, source: str, message: str, task_id: str | None = None) -> None:
        with self._lock, self._conn() as c:
            c.execute(
                "INSERT INTO logs(ts,level,source,task_id,message) VALUES(?,?,?,?,?)",
                (now().isoformat(), level, source, task_id, message[:1000]),
            )

    def logs(self, limit: int = 100, task_id: str | None = None, level: str | None = None) -> list[dict]:
        sql, params = "SELECT ts,level,source,task_id,message FROM logs WHERE 1=1", []
        if task_id:
            sql += " AND task_id=?"
            params.append(task_id)
        if level:
            sql += " AND level=?"
            params.append(level)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self._conn() as c:
            return [dict(r) for r in c.execute(sql, params).fetchall()]

    # --- cache ---
    def cache_get(self, key: str) -> Any | None:
        with self._conn() as c:
            row = c.execute("SELECT fetched_at,ttl_s,body FROM http_cache WHERE key=?", (key,)).fetchone()
        if row and time.time() - row["fetched_at"] < row["ttl_s"]:
            return json.loads(row["body"])
        return None

    def cache_set(self, key: str, body: Any, ttl_s: int) -> None:
        with self._lock, self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO http_cache(key,fetched_at,ttl_s,body) VALUES(?,?,?,?)",
                (key, time.time(), ttl_s, json.dumps(body)),
            )


_store: Store | None = None


def get_store() -> Store:
    global _store
    if _store is None or not _store.path.parent.exists():
        _store = Store(data_dir() / "cios.db")
    return _store


def reset_store() -> None:
    """Usado em testes após trocar CIOS_DATA_DIR."""
    global _store
    _store = None
