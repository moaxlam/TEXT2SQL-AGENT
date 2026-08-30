"""Database connection management."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from contextlib import contextmanager


class DatabaseConnection:
    """Simple database connection wrapper. Supports SQLite for MVP."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        # Extract path from sqlite:///path
        if database_url.startswith("sqlite:///"):
            self.db_path = database_url.replace("sqlite:///", "")
        else:
            self.db_path = database_url

    @contextmanager
    def connect(self):
        """Context manager that yields a connection and auto-closes."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def execute(self, sql: str) -> tuple[list[dict], list[str]]:
        """Execute SQL and return (rows, column_names)."""
        with self.connect() as conn:
            cursor = conn.execute(sql)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = [dict(row) for row in cursor.fetchall()]
            return rows, columns

    def test_connection(self) -> bool:
        """Test if the database is accessible."""
        try:
            with self.connect() as conn:
                conn.execute("SELECT 1")
            return True
        except Exception:
            return False
