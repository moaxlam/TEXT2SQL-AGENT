"""SQL Agent"""
from __future__ import annotations
from ..providers.base import LLMProvider

SQL_AGENT_PROMPT = """You are an expert SQL engineer.
Given a natural language question and a database schema,
write a correct SQL query to answer the question.

Return a JSON object:
{
  "sql": "SELECT ...",
  "explanation": "Brief explanation",
  "assumptions": ["Any assumptions"]
}"""


class SQLAgent:
    def __init__(self, provider):
        self.provider = provider

    def run(self, question, schema_text, context=None):
        user_content = "SCHEMA:\\n" + schema_text + "\\n\\nQUESTION: " + question
        if context:
            user_content += "\\n\\nADDITIONAL CONTEXT:\\n" + str(context)
        messages = [
            {"role": "system", "content": SQL_AGENT_PROMPT},
            {"role": "user", "content": user_content},
        ]
        result, response = self.provider.chat_json(messages)
        return result, response
