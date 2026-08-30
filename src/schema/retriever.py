"""Rank and retrieve the most relevant tables/columns for a question."""

from __future__ import annotations

from .loader import Table


class SchemaRetriever:
    """Simple keyword-based retriever. Upgrade to embeddings for production."""

    def __init__(self, tables: list[Table]):
        self.tables = {t.name.lower(): t for t in tables}

    def get_relevant(self, question: str, top_k: int = 5) -> list[Table]:
        """Return the most relevant tables for a natural language question."""
        q_words = set(question.lower().split())
        scores: dict[str, float] = {}

        for lname, table in self.tables.items():
            score = 0.0

            # Table name matches question words
            tname_words = set(lname.replace("_", " ").replace("-", " ").split())
            overlap = q_words & tname_words
            score += len(overlap) * 3.0

            # Column names match question words
            for col in table.columns:
                col_words = set(col.name.lower().replace("_", " ").split())
                col_overlap = q_words & col_words
                score += len(col_overlap) * 1.0

            # Exact substring match on table name
            if lname in question.lower():
                score += 5.0

            scores[lname] = score

        ranked = sorted(scores, key=scores.get, reverse=True)[:top_k]
        return [self.tables[name] for name in ranked if scores[name] > 0]

    def get_all(self) -> list[Table]:
        """Return all tables (fallback when retriever confidence is low)."""
        return list(self.tables.values())
