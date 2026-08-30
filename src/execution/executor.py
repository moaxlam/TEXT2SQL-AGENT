"""SQL execution with safety checks and result formatting."""

from __future__ import annotations

import re
import time

from .connection import DatabaseConnection


# Block dangerous operations
BLOCKED_PATTERNS = [
    r"\b(DROP|DELETE|TRUNCATE|ALTER|INSERT|UPDATE|CREATE)\b",
]


class ExecutionResult:
    """Result of a SQL execution."""

    def __init__(self, success: bool, rows: list[dict] | None = None,
                 columns: list[str] | None = None, error: str | None = None,
                 execution_time_ms: float = 0, row_count: int = 0):
        self.success = success
        self.rows = rows or []
        self.columns = columns or []
        self.error = error
        self.execution_time_ms = execution_time_ms
        self.row_count = row_count

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "columns": self.columns,
            "rows": self.rows[:50],  # Limit output
            "row_count": self.row_count,
            "execution_time_ms": round(self.execution_time_ms, 2),
            "error": self.error,
        }

    def __str__(self) -> str:
        if self.error:
            return f"ERROR: {self.error}"
        if not self.rows:
            return "Query returned 0 rows."
        header = " | ".join(self.columns)
        lines = [header, "-" * len(header)]
        for row in self.rows[:10]:
            lines.append(" | ".join(str(v) for v in row.values()))
        if self.row_count > 10:
            lines.append(f"... ({self.row_count - 10} more rows)")
        return "\n".join(lines)


class SQLExecutor:
    """Execute SQL queries safely."""

    def __init__(self, db: DatabaseConnection, read_only: bool = True):
        self.db = db
        self.read_only = read_only

    def validate_sql(self, sql: str) -> str | None:
        """Check if SQL is safe to execute. Returns error message or None."""
        sql_upper = sql.upper().strip()

        # Only allow SELECT queries in read-only mode
        if self.read_only and not sql_upper.startswith("SELECT"):
            return f"Only SELECT queries are allowed in read-only mode. Got: {sql_upper[:50]}..."

        # Check for blocked patterns
        for pattern in BLOCKED_PATTERNS:
            if re.search(pattern, sql_upper):
                return f"Blocked operation: {pattern}"

        return None

    def execute(self, sql: str) -> ExecutionResult:
        """Execute SQL and return a formatted result."""
        # Validate
        error = self.validate_sql(sql)
        if error:
            return ExecutionResult(success=False, error=error)

        # Execute with timing
        start = time.time()
        try:
            rows, columns = self.db.execute(sql)
            elapsed = (time.time() - start) * 1000
            return ExecutionResult(
                success=True,
                rows=rows,
                columns=columns,
                execution_time_ms=elapsed,
                row_count=len(rows),
            )
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            return ExecutionResult(
                success=False,
                error=str(e),
                execution_time_ms=elapsed,
            )
