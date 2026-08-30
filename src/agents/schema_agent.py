"""Schema Agent — understands the database and picks relevant tables."""

from __future__ import annotations

from ..providers.base import LLMProvider


SCHEMA_AGENT_PROMPT = """You are a database schema expert. Given a natural language question and a database schema, identify which tables and columns are relevant to answer the question.

Return a JSON object with this exact structure:
{
  "relevant_tables": ["table_name1", "table_name2"],
  "relevant_columns": {"table_name1": ["col1", "col2"], "table_name2": ["col3"]},
  "join_conditions": ["table1.col = table2.col"],
  "reasoning": "Brief explanation of why these tables/columns are relevant"
}

Only include tables and columns that are actually needed. Be precise."""


class SchemaAgent:
    def __init__(self, provider: LLMProvider):
        self.provider = provider

    def run(self, question: str, schema_text: str) -> dict:
        """Analyze question against schema, return relevant tables/columns."""
        messages = [
            {"role": "system", "content": SCHEMA_AGENT_PROMPT},
            {"role": "user", "content": f"SCHEMA:\n{schema_text}\n\nQUESTION: {question}"},
        ]
        return self.provider.chat_json(messages)
