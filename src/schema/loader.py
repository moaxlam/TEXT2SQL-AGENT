"""Load database schema from a SQL file or live database."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from dataclasses import dataclass


@dataclass
class Column:
    name: str
    dtype: str
    nullable: bool = True
    pk: bool = False
    description: str = ""


@dataclass
class Table:
    name: str
    columns: list[Column]
    description: str = ""
    sample_rows: list[dict] | None = None


def load_schema_from_sql(path: str | Path) -> str:
    """Read a .sql schema file and return its text."""
    return Path(path).read_text(encoding="utf-8")


def load_schema_from_db(db_path: str) -> list[Table]:
    """Introspect a SQLite database and return Table objects."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    table_names = [row["name"] for row in cursor.fetchall()]

    tables = []
    for tname in table_names:
        cursor.execute(f"PRAGMA table_info({tname})")
        columns = []
        for col in cursor.fetchall():
            columns.append(Column(
                name=col["name"],
                dtype=col["type"],
                nullable=not col["notnull"],
                pk=bool(col["pk"]),
            ))

        # Get sample rows (up to 3)
        try:
            cursor.execute(f"SELECT * FROM {tname} LIMIT 3")
            sample_rows = [dict(row) for row in cursor.fetchall()]
        except Exception:
            sample_rows = None

        tables.append(Table(name=tname, columns=columns, sample_rows=sample_rows))

    conn.close()
    return tables


def parse_create_statements(sql_text: str) -> list[Table]:
    """Parse CREATE TABLE statements from SQL text into Table objects."""
    tables = []
    # Match CREATE TABLE blocks
    pattern = r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"']?(\w+)[`\"']?\s*\((.*?)\);"
    for match in re.finditer(pattern, sql_text, re.IGNORECASE | re.DOTALL):
        tname = match.group(1)
        body = match.group(2)

        columns = []
        for line in body.split("\n"):
            line = line.strip().rstrip(",")
            if not line or line.upper().startswith(("PRIMARY", "FOREIGN", "UNIQUE", "INDEX", "CONSTRAINT")):
                continue
            parts = line.split(None, 2)
            if len(parts) >= 2:
                col_name = parts[0].strip("`\"'")
                col_dtype = parts[1].upper()
                pk = "PRIMARY KEY" in line.upper()
                nullable = "NOT NULL" not in line.upper()
                columns.append(Column(name=col_name, dtype=col_dtype, nullable=nullable, pk=pk))

        tables.append(Table(name=tname, columns=columns))

    return tables
