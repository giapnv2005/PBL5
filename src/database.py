from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List


class DetectionDatabase:
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._lock:
            with self._connect() as connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS detections (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        accessory TEXT NOT NULL,
                        confident REAL NOT NULL,
                        timestamp TEXT NOT NULL,
                        image_path TEXT NOT NULL
                    )
                    """
                )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_detections_timestamp ON detections(timestamp DESC)"
                )
                connection.commit()

    def add_detection(
        self,
        accessory: str,
        confident: float,
        timestamp: str,
        image_path: str,
    ) -> int:
        with self._lock:
            with self._connect() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO detections (accessory, confident, timestamp, image_path)
                    VALUES (?, ?, ?, ?)
                    """,
                    (accessory, float(confident), timestamp, image_path),
                )
                connection.commit()
                return int(cursor.lastrowid)

    def get_recent_detections(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            with self._connect() as connection:
                cursor = connection.execute(
                    """
                    SELECT id, accessory, confident, timestamp, image_path
                    FROM detections
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (int(limit),),
                )
                rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def get_history_page(
        self,
        query: str = "",
        page: int = 1,
        page_size: int = 10,
    ) -> Dict[str, Any]:
        page = max(1, int(page))
        page_size = max(1, int(page_size))
        offset = (page - 1) * page_size
        normalized_query = (query or "").strip()
        where_clause = ""
        parameters: list[Any] = []

        if normalized_query:
            where_clause = "WHERE LOWER(accessory) LIKE LOWER(?)"
            parameters.append(f"%{normalized_query}%")

        with self._lock:
            with self._connect() as connection:
                total_cursor = connection.execute(
                    f"SELECT COUNT(*) AS total FROM detections {where_clause}",
                    tuple(parameters),
                )
                total = int(total_cursor.fetchone()["total"])

                page_cursor = connection.execute(
                    f"""
                    SELECT id, accessory, confident, timestamp, image_path
                    FROM detections
                    {where_clause}
                    ORDER BY id DESC
                    LIMIT ? OFFSET ?
                    """,
                    tuple(parameters + [page_size, offset]),
                )
                rows = [dict(row) for row in page_cursor.fetchall()]

        return {
            "rows": rows,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size) if total else 1,
            "query": normalized_query,
        }

    def delete_all_detections(self) -> List[str]:
        with self._lock:
            with self._connect() as connection:
                cursor = connection.execute("SELECT image_path FROM detections")
                image_paths = [row["image_path"] for row in cursor.fetchall()]
                connection.execute("DELETE FROM detections")
                connection.execute("DELETE FROM sqlite_sequence WHERE name = 'detections'")
                connection.commit()
        return image_paths