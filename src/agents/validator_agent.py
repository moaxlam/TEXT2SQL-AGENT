"""Validator Agent"""
from __future__ import annotations
from ..providers.base import LLMProvider

VALIDATOR_PROMPT = """You are a SQL validator.
Check if the SQL is syntactically correct and answers the question.

Return a JSON object:
{
  "is_valid": true/false,
  "issues": ["issues found"],
  "corrected_sql": "corrected SQL if invalid, null if valid"
}"""


class ValidatorAgent:
    def __init__(self, provider):
        self.provider = provider

    def run(self, question, schema_text, sql):
        user_content = "SCHEMA:\\n" + schema_text + "\\n\\nQUESTION: " + question + "\\n\\nGENERATED SQL:\\n" + sql
        messages = [
            {"role": "system", "content": VALIDATOR_PROMPT},
            {"role": "user", "content": user_content},
        ]
        result, response = self.provider.chat_json(messages)
        return result, response
