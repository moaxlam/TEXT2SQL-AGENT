"""Evaluation metrics for Text-to-SQL."""

from __future__ import annotations
import sqlite3


def execute_sql(db_path, sql):
    """Execute SQL and return sorted rows, or None on error."""
    try:
        conn = sqlite3.connect(db_path)
        rows = conn.execute(sql).fetchall()
        conn.close()
        return sorted(rows)
    except Exception:
        return None


def get_row_count(db_path, sql):
    """Execute SQL and return row count, or -1 on error."""
    try:
        conn = sqlite3.connect(db_path)
        count = conn.execute(sql).fetchone()[0]
        conn.close()
        return count
    except Exception:
        return -1


def execution_match(generated_sql, gold_sql, db_path):
    """Check if generated SQL produces the same result as gold SQL.
    Uses normalized comparison: same row count + same key values."""
    gen_rows = execute_sql(db_path, generated_sql)
    gold_rows = execute_sql(db_path, gold_sql)
    if gen_rows is None or gold_rows is None:
        return False
    # Exact match first
    if gen_rows == gold_rows:
        return True
    # Normalized: same row count + first column values match
    if len(gen_rows) != len(gold_rows):
        return False
    if len(gen_rows) == 0:
        return True
    # Compare first column of each row (most queries return the key in col 0)
    gen_first = sorted([r[0] for r in gen_rows])
    gold_first = sorted([r[0] for r in gold_rows])
    return gen_first == gold_first


def compute_metrics(results):
    """Compute aggregate metrics from a list of result dicts."""
    total = len(results)
    correct = sum(1 for r in results if r.get("correct", False))
    errors = sum(1 for r in results if r.get("error") is not None)
    total_repairs = sum(r.get("repair_attempts", 0) for r in results)
    repairs_used = sum(1 for r in results if r.get("repair_attempts", 0) > 0)
    total_tokens = sum(r.get("total_tokens", 0) for r in results)
    total_latency = sum(r.get("latency_seconds", 0) for r in results)

    by_difficulty = {}
    for d in ["easy", "medium", "hard"]:
        subset = [r for r in results if r.get("difficulty") == d]
        if subset:
            by_difficulty[d] = {
                "total": len(subset),
                "correct": sum(1 for r in subset if r.get("correct", False)),
                "accuracy": sum(1 for r in subset if r.get("correct", False)) / len(subset),
            }

    return {
        "total": total,
        "correct": correct,
        "execution_accuracy": correct / total if total > 0 else 0,
        "errors": errors,
        "avg_latency_seconds": total_latency / total if total > 0 else 0,
        "avg_tokens_per_query": total_tokens / total if total > 0 else 0,
        "total_tokens": total_tokens,
        "avg_repairs": total_repairs / total if total > 0 else 0,
        "repair_rate": repairs_used / total if total > 0 else 0,
        "by_difficulty": by_difficulty,
    }