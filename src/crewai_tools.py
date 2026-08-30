"""CrewAI tool wrappers for Text-to-SQL pipeline.

These tools wrap existing deterministic functions for use by CrewAI agents.
No LLM calls — pure Python logic.
"""
from crewai.tools import tool
from .schema.loader import load_schema_from_sql, parse_create_statements
from .schema.retriever import SchemaRetriever
from .schema.formatter import format_tables
from .config import settings

# Module-level singletons (initialized once)
_schema_loaded = False
_tables = None
_retriever = None


def _ensure_schema():
    global _schema_loaded, _tables, __retriever
    if not _schema_loaded:
        schema_text = load_schema_from_sql(settings.schema_path)
        _tables = parse_create_statements(schema_text)
        _retriever = SchemaRetriever(_tables)
        _schema_loaded = True


@tool("retrieve_schema")
def retrieve_schema(question: str) -> str:
    """Retrieve the relevant database schema for a natural language question.

    Args:
        question: The natural language question to find relevant tables for.

    Returns:
        Formatted schema text containing relevant table definitions.
    """
    _ensure_schema()
    relevant = _retriever.get_relevant(question, top_k=5)
    if not relevant:
        relevant = _retriever.get_all()
    return format_tables(relevant)


@tool("get_full_schema")
def get_full_schema() -> str:
    """Retrieve the complete database schema with all tables and columns.

    Returns:
        Formatted schema text containing all table definitions.
    """
    _ensure_schema()
    return format_tables(_tables)


# Convenience list for passing to CrewAI agents
crewai_tools = [retrieve_schema, get_full_schema]
