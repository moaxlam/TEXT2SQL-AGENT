"""Repair Agent"""
from __future__ import annotations
from ..providers.base import LLMProvider

REPAIR_PROMPT = """You are a SQL debugging expert.
A SQL query failed with an error. Fix the query.

Return a JSON object:
{
  "fixed_sql": "the corrected SQL query",
  "root_cause": "what was wrong",
  "changes_made": ["list of changes"]
}"""


class RepairAgent:
    def __init__(self, provider):
        self.provider = provider

    def run(self, question, schema_text, sql, error):
        user_content = "SCHEMA:\\n" + schema_text + "\\n\\nQUESTION: " + question + "\\n\\nBROKEN SQL:\\n" + sql + "\\n\\nERROR:\\n" + error
        messages = [
            {"role": "system", "content": REPAIR_PROMPT},
            {"role": "user", "content": user_content},
        ]
        result, response = self.provider.chat_json(messages)
        return result, response
