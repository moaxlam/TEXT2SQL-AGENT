"""Gradio web UI for the Text-to-SQL CrewAI system.

Run with:
    python app.py

Or:
    uv run python app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import gradio as gr
from src.pipeline.runner import TextToSQLPipeline

# Global pipeline instance (initialized once)
_pipeline: TextToSQLPipeline | None = None

def get_pipeline() -> TextToSQLPipeline:
    """Get or create the pipeline singleton."""
    global _pipeline
    if _pipeline is None:
        _pipeline = TextToSQLPipeline()
    return _pipeline


def format_result_table(result: dict) -> str:
    """Format execution result as a readable markdown table."""
    if not result.get("success"):
        return f"**Error:** {result.get('error', 'Unknown error')}"

    rows = result.get("rows", [])
    columns = result.get("columns", [])

    if not rows:
        return "_No results returned._"

    header = " | ".join(columns)
    separator = " | ".join(["---"] * len(columns))
    data_rows = []
    for row in rows:
        vals = [str(row.get(col, "")) for col in columns]
        data_rows.append(" | ".join(vals))

    table = f"| {header} |\n| {separator} |\n" + "\n".join(
        f"| {r} |" for r in data_rows
    )
    return table


def format_steps(steps: list) -> str:
    """Format pipeline steps as a concise timeline."""
    parts = []
    for s in steps:
        step_name = s.get("step", "")
        ms = s.get("time_ms", 0)

        if step_name == "cache_hit":
            parts.append("Cache hit (instant)")
        elif step_name == "schema_retrieval":
            parts.append(f"Schema retrieval ({ms:.0f}ms)")
        elif step_name == "sql_generation":
            parts.append(f"SQL generation ({ms:.0f}ms)")
        elif step_name == "execution":
            status = "OK" if s.get("success") else "FAIL"
            parts.append(f"Execution {status} ({ms:.0f}ms)")
        elif step_name == "validation_diagnostic":
            parts.append(f"Validation diagnostic ({ms:.0f}ms)")
        elif step_name.startswith("repair_attempt"):
            parts.append(f"Repair attempt ({ms:.0f}ms)")
        elif step_name.startswith("re_execution"):
            status = "OK" if s.get("success") else "FAIL"
            parts.append(f"Re-execution {status} ({ms:.0f}ms)")
        else:
            parts.append(f"{step_name} ({ms:.0f}ms)")

    return " -> ".join(parts)


def run_query(question: str):
    """Run a natural language question through the pipeline.

    Returns:
        (sql_display, result_display, status_display, meta_display, steps_display)
    """
    if not question.strip():
        return (
            "",
            "Please enter a question.",
            "**Status:** No question provided",
            "",
            "",
        )

    try:
        pipeline = get_pipeline()
        result = pipeline.run(question)

        sql_display = f"```sql\n{result.sql}\n```" if result.sql else "_No SQL generated._"
        result_display = format_result_table(result.result)

        if result.status == "success":
            status = "**Status:** Success"
        else:
            error = result.result.get("error", "Unknown error")
            status = f"**Status:** Error - {error}"

        latency = result.total_time_ms / 1000
        repairs = result.repair_attempts
        cache = "Yes" if result.cache_hit else "No"
        meta_parts = [
            f"**Latency:** {latency:.2f}s",
            f"**Repairs:** {repairs}",
            f"**Cache hit:** {cache}",
            f"**Model:** {result.model}",
        ]
        meta_display = "  ·  ".join(meta_parts)
        steps_display = format_steps(result.steps)

        return sql_display, result_display, status, meta_display, steps_display

    except Exception as e:
        return (
            "",
            f"An unexpected error occurred:\n\n```\n{e}\n```",
            "**Status:** Pipeline error",
            "",
            "",
        )# ── Theme & Layout ──────────────────────────────────────────
def build_ui() -> gr.Blocks:
    """Build the Gradio interface."""
    with gr.Blocks(title="Text-to-SQL AI") as demo:
        gr.Markdown(
            """
            # Text-to-SQL AI
            Ask questions about your database in natural language.
            Powered by CrewAI agents with self-repair.
            """
        )

        with gr.Row():
            with gr.Column(scale=1):
                question_input = gr.Textbox(
                    label="Your question",
                    placeholder="e.g. Which customer has placed the most orders?",
                    lines=2,
                    max_lines=5,
                )
                run_button = gr.Button(
                    "Generate SQL",
                    variant="primary",
                    size="lg",
                )

        with gr.Row():
            with gr.Column(scale=1):
                status_display = gr.Markdown(
                    label="Status",
                    value="*Ready - enter a question above*",
                )

        with gr.Row():
            with gr.Column(scale=1):
                sql_display = gr.Markdown(
                    label="Generated SQL",
                    value="",
                )

        with gr.Row():
            with gr.Column(scale=1):
                result_display = gr.Markdown(
                    label="Query Result",
                    value="",
                )

        with gr.Row():
            with gr.Column(scale=1):
                meta_display = gr.Markdown(
                    label="Metadata",
                    value="",
                )
                steps_display = gr.Markdown(
                    label="Pipeline Steps",
                    value="",
                )

        gr.Examples(
            examples=[
                "How many customers are there?",
                "What is the cheapest product?",
                "Which customer has placed the most orders?",
                "Show me all pending orders with customer names",
                "What is the average rating for electronics products?",
                "Which customers have not placed any orders?",
                "List all products with price above 100",
                "How many orders were placed this month?",
            ],
            inputs=question_input,
            label="Example questions",
        )

        run_button.click(
            fn=run_query,
            inputs=[question_input],
            outputs=[sql_display, result_display, status_display, meta_display, steps_display],
        )

        question_input.submit(
            fn=run_query,
            inputs=[question_input],
            outputs=[sql_display, result_display, status_display, meta_display, steps_display],
        )

    return demo


# ── Entry point ──────────────────────────────────────────────

if __name__ == "__main__":
    # Ensure database is set up
    from main import setup_database
    try:
        setup_database()
    except Exception:
        pass  # DB already exists

    # Pre-initialize pipeline
    print("Initializing pipeline...")
    get_pipeline()
    print("Pipeline ready.")

    # Launch UI
    demo = build_ui()
    import socket
    def find_free_port(start=7860):
        for port in range(start, start + 100):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(("127.0.0.1", port)) != 0:
                    return port
        return start

    port = find_free_port()
    print(f"\n  URL: http://127.0.0.1:{port}\n")
    demo.launch(
        server_name="0.0.0.0",
        server_port=port,
        share=False,
        show_error=True,
        theme=gr.themes.Soft(primary_hue="blue", secondary_hue="slate"),
    )
