"""CrewAI runner for Text-to-SQL pipeline.

Uses CrewAI agents for SQL generation, validation, and repair.
Python controls execution and the bounded repair loop.
"""
from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path

from crewai import Agent, Crew, Process, Task, LLM

from .config import settings
from .crewai_factory import create_crewai_llm
from .crewai_tools import retrieve_schema
from .schema.loader import load_schema_from_sql, parse_create_statements
from .schema.retriever import SchemaRetriever
from .schema.formatter import format_tables

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema setup (deterministic, loaded once)
# ---------------------------------------------------------------------------
_schema_text = load_schema_from_sql(settings.schema_path)
_tables = parse_create_statements(_schema_text)
_retriever = SchemaRetriever(_tables)


def _get_schema(question: str) -> str:
    """Get relevant schema for a question (deterministic, no LLM)."""
    relevant = _retriever.get_relevant(question, top_k=5)
    if not relevant:
        relevant = _retriever.get_all()
    return format_tables(relevant)


def _extract_sql(text: str) -> str:
    """Extract SQL from LLM response. Handles markdown fences, explanations."""
    if not text:
        return ""
    # Strip markdown code fences
    cleaned = re.sub(r"```(?:sql)?\s*", "", text).strip().rstrip("`")
    # If it's already clean SQL, return it
    if cleaned.upper().startswith("SELECT"):
        # Take just the first statement
        lines = cleaned.split("\n")
        sql_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("--"):
                sql_lines.append(stripped)
            if stripped.endswith(";"):
                break
        return " ".join(sql_lines).rstrip(";")
    # Try to find SQL in the response
    match = re.search(r"(SELECT\s+.+)", cleaned, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).split("\n")[0].rstrip(";")
    return cleaned


class CrewAIRunner:
    """CrewAI-based runner for SQL generation, validation, and repair.

    Python controls execution and the bounded repair loop.
    CrewAI agents handle the LLM-powered reasoning.
    """

    def __init__(self, llm: LLM | None = None):
        self.llm = llm or create_crewai_llm()
        self._build_agents()

    def _build_agents(self):
        """Create CrewAI agents from YAML configs + LLM."""
        config_dir = Path(__file__).parent / "config"

        # Load agent configs
        import yaml
        with open(config_dir / "agents.yaml") as f:
            agents_config = yaml.safe_load(f)

        self.sql_generator = Agent(
            config=agents_config["sql_generator"],
            llm=self.llm,
            tools=[retrieve_schema],
            verbose=False,
        )

        self.sql_validator = Agent(
            config=agents_config["sql_validator"],
            llm=self.llm,
            tools=[],
            verbose=False,
        )

        self.sql_repair = Agent(
            config=agents_config["sql_repair"],
            llm=self.llm,
            tools=[],
            verbose=False,
        )

    def generate_sql(self, question: str, schema_text: str) -> tuple[str, dict]:
        """Generate SQL using CrewAI SQL Generator agent.

        Returns (sql_string, metadata_dict).
        """
        t0 = time.time()

        task = Task(
            description=f"""You are an expert SQL engineer. Given a question and database schema, write SQL.

STEP 1 - SCHEMA LINKING: Map question concepts to exact tables and columns.
STEP 2 - SQL GENERATION: Write the query using linked tables/columns and the few-shot patterns below.

RULES:
1. SELECT only needed columns. No SELECT *.
2. Use exact column names from the schema provided.
3. Use correct JOIN foreign keys.
4. Return ONLY the SQL query. No explanation.

SCHEMA LINKING EXAMPLES:
Q: "How many customers from New York?"
Link: customers -> customers, New York -> customers.city
SQL: SELECT COUNT(*) FROM customers WHERE city = 'New York'

Q: "Orders by Alice Johnson?"
Link: orders -> orders, Alice Johnson -> customers.name, join via customer_id
SQL: SELECT o.order_id, o.order_date, o.total_amount FROM orders o JOIN customers c ON o.customer_id = c.customer_id WHERE c.name = 'Alice Johnson'

FEW-SHOT PATTERNS:
Q: "How many customers?"
SQL: SELECT COUNT(*) FROM customers

Q: "Products costing more than 100?"
SQL: SELECT name, price FROM products WHERE price > 100

Q: "Customer with most orders?"
SQL: SELECT c.name, COUNT(o.order_id) as cnt FROM customers c JOIN orders o ON c.customer_id = o.customer_id GROUP BY c.name ORDER BY cnt DESC LIMIT 1

Q: "Each customer with order count?"
SQL: SELECT c.name, COUNT(o.order_id) FROM customers c LEFT JOIN orders o ON c.customer_id = o.customer_id GROUP BY c.name

Q: "Total revenue?"
SQL: SELECT SUM(total_amount) FROM orders

SCHEMA:
{schema_text}

QUESTION: {question}

Write ONLY the SQL query.""",
            expected_output="A single SQL query string that answers the question.",
            agent=self.sql_generator,
        )

        crew = Crew(
            agents=[self.sql_generator],
            tasks=[task],
            process=Process.sequential,
            verbose=False,
        )

        result = crew.kickoff()
        raw_output = str(result)
        sql = _extract_sql(raw_output)

        metadata = {
            "raw_output": raw_output,
            "extracted_sql": sql,
            "latency_seconds": round(time.time() - t0, 2),
        }
        return sql, metadata

    def validate_sql(self, question: str, schema_text: str, sql: str) -> dict:
        """Validate SQL using CrewAI Validator agent.

        Returns diagnostic dict: {is_valid, issues, confidence}.
        Does NOT modify the SQL — Python decides what to do with diagnostics.
        """
        t0 = time.time()

        task = Task(
            description=f"""Analyze the following SQL query for correctness.

SCHEMA:
{schema_text}

QUESTION: {question}

GENERATED SQL:
{sql}

Check for:
1. Correct table and column names from the schema
2. Proper JOIN syntax and conditions
3. Correct aggregation (GROUP BY, HAVING)
4. Proper filtering (WHERE clause)
5. Logical correctness — does this answer the question?

Report your analysis as JSON:
{{"is_valid": true/false, "issues": [...], "confidence": "high/medium/low"}}
Do NOT modify the SQL.""",
            expected_output='A JSON diagnostic: {{"is_valid": bool, "issues": list, "confidence": str}}',
            agent=self.sql_validator,
        )

        crew = Crew(
            agents=[self.sql_validator],
            tasks=[task],
            process=Process.sequential,
            verbose=False,
        )

        result = crew.kickoff()
        raw = str(result)

        # Try to parse JSON from response
        try:
            # Find JSON in response
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                return json.loads(match.group())
        except json.JSONDecodeError:
            pass

        # Fallback: assume valid if we can't parse
        return {"is_valid": True, "issues": [], "confidence": "low", "raw": raw}

    def repair_sql(self, question: str, schema_text: str, broken_sql: str, error: str) -> tuple[str, dict]:
        """Repair broken SQL using CrewAI Repair agent.

        Returns (fixed_sql, metadata_dict).
        """
        t0 = time.time()

        task = Task(
            description=f"""The following SQL query failed with an error. Fix it.

SCHEMA:
{schema_text}

QUESTION: {question}

BROKEN SQL:
{broken_sql}

ERROR:
{error}

Fix the SQL query to resolve the error while preserving the original intent.
Return ONLY the corrected SQL query. No explanation.""",
            expected_output="A corrected SQL query string that resolves the error.",
            agent=self.sql_repair,
        )

        crew = Crew(
            agents=[self.sql_repair],
            tasks=[task],
            process=Process.sequential,
            verbose=False,
        )

        result = crew.kickoff()
        raw_output = str(result)
        sql = _extract_sql(raw_output)

        metadata = {
            "raw_output": raw_output,
            "extracted_sql": sql,
            "latency_seconds": round(time.time() - t0, 2),
        }
        return sql, metadata
