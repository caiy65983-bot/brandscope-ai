"""SQLite cache for validated text annotations and sanitized run errors."""

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional


class AnalysisStorage:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS annotation_cache (cache_key TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS analysis_errors (created_at TEXT DEFAULT CURRENT_TIMESTAMP, record_id TEXT, message TEXT NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS strategy_reports (dataset_id TEXT PRIMARY KEY, updated_at TEXT DEFAULT CURRENT_TIMESTAMP, payload TEXT NOT NULL, html TEXT NOT NULL)")

    def _connect(self):
        return sqlite3.connect(str(self.path), timeout=10)

    @staticmethod
    def cache_key(model: str, content: str, base_url: str = "") -> str:
        # Provider endpoints can map the same model name to different model versions.
        raw = "brandscope-annotation-v1\0{}\0{}\0{}".format(base_url.rstrip("/"), model, content)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        with self._connect() as connection:
            row = connection.execute("SELECT payload FROM annotation_cache WHERE cache_key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, key: str, payload: Dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute("INSERT OR REPLACE INTO annotation_cache(cache_key,payload) VALUES(?,?)", (key, json.dumps(payload, ensure_ascii=False)))

    def log_error(self, record_id: str, message: str) -> None:
        with self._connect() as connection:
            connection.execute("INSERT INTO analysis_errors(record_id,message) VALUES(?,?)", (record_id, message[:500]))

    def save_report(self, dataset_id: str, payload: Dict[str, Any], html: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO strategy_reports(dataset_id,updated_at,payload,html) VALUES(?,CURRENT_TIMESTAMP,?,?) "
                "ON CONFLICT(dataset_id) DO UPDATE SET updated_at=CURRENT_TIMESTAMP,payload=excluded.payload,html=excluded.html",
                (dataset_id, json.dumps(payload, ensure_ascii=False, allow_nan=False), html),
            )

    def get_report(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload,html,updated_at FROM strategy_reports WHERE dataset_id=?", (dataset_id,)
            ).fetchone()
        if not row:
            return None
        return {"payload": json.loads(row[0]), "html": row[1], "updated_at": row[2]}
