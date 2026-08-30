"""Format Table objects into LLM-friendly text."""

from __future__ import annotations

from .loader import Table


def format_tables(tables: list[Table], include_samples: bool = True) -> str:
    """Format a list of tables into a schema string for the LLM."""
    parts = []
    for table in tables:
        lines = [f"TABLE: {table.name}"]
        if table.description:
            lines.append(f"  -- {table.description}")

        for col in table.columns:
            pk_tag = " [PRIMARY KEY]" if col.pk else ""
            null_tag = "" if col.nullable else " NOT NULL"
            lines.append(f"  {col.name} {col.dtype}{pk_tag}{null_tag}")

        if include_samples and table.sample_rows:
            lines.append("  -- Sample data:")
            for row in table.sample_rows[:2]:
                lines.append(f"  -- {row}")

        parts.append("\n".join(lines))

    return "\n\n".join(parts)


def format_full_schema(tables: list[Table]) -> str:
    """Format ALL tables into a complete schema dump."""
    return format_tables(tables, include_samples=False)
