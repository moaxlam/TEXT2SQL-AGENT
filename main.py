"""Text-to-SQL Agent — main entry point."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.config import settings
from src.pipeline.runner import TextToSQLPipeline


def setup_database():
    """Create the SQLite database and load sample data."""
    import sqlite3

    db_path = settings.database_url.replace("sqlite:///", "")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Load schema (ignore if tables exist)
    schema_sql = Path(settings.schema_path).read_text()
    for statement in schema_sql.split(';'):
        statement = statement.strip()
        if statement:
            try:
                cursor.execute(statement)
            except sqlite3.OperationalError:
                pass  # Table already exists

    # Load sample data if table is empty
    sample_path = Path(__file__).parent / "data" / "sample_data.sql"
    if sample_path.exists():
        cursor.execute("SELECT COUNT(*) FROM customers")
        if cursor.fetchone()[0] == 0:
            sample_sql = sample_path.read_text()
            cursor.executescript(sample_sql)
            print("Loaded sample data.")

    conn.commit()
    conn.close()
    print(f"Database ready at: {db_path}")


def interactive_mode():
    """Run the pipeline in interactive mode."""
    print("=" * 60)
    print("  Text-to-SQL Agent")
    print("  Ask questions about your database in natural language")
    print("=" * 60)
    print()

    pipeline = TextToSQLPipeline()

    # Demo questions
    demo_questions = [
        "How many customers are there?",
        "What are the most expensive products?",
        "Which customer has placed the most orders?",
        "What is the average rating for electronics products?",
        "Show me all pending orders with customer names",
    ]

    print("Demo questions:")
    for i, q in enumerate(demo_questions, 1):
        print(f"  {i}. {q}")
    print()

    while True:
        try:
            question = input("Ask a question (or 'quit' to exit): ").strip()
            if not question or question.lower() in ("quit", "exit", "q"):
                break

            # Check if it's a number (select demo question)
            if question.isdigit() and 1 <= int(question) <= len(demo_questions):
                question = demo_questions[int(question) - 1]
                print(f"Selected: {question}")

            print(f"\nProcessing: {question}")
            print("-" * 40)

            result = pipeline.run(question)

            print(f"\nSQL: {result.sql}")
            print(f"\nResult:")
            print(result)

            print(f"\nPipeline steps:")
            for step in result.steps:
                print(f"  - {step['step']}: {step.get('time_ms', 0):.0f}ms")

            print()

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")

    print("\nGoodbye!")


def single_query(question: str):
    """Run a single query and print the result."""
    pipeline = TextToSQLPipeline()
    result = pipeline.run(question)
    print(result)
    print(json.dumps(result.to_dict(), indent=2))


if __name__ == "__main__":
    # Setup database first
    setup_database()

    if len(sys.argv) > 1:
        # Single query mode
        question = " ".join(sys.argv[1:])
        single_query(question)
    else:
        # Interactive mode
        interactive_mode()
