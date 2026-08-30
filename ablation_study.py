"""Ablation study for Text-to-SQL configurations.

Usage:
    python ablation_study.py                        # run all configs on pilot dataset
    python ablation_study.py --config A             # run only Config A
    python ablation_study.py --config A B           # run Configs A and B
    python ablation_study.py --dataset local_ecommerce.json  # use full dataset
    python ablation_study.py --resume               # skip completed questions (default)

Environment variables:
    LLM_PROVIDER  = groq | openrouter | nvidia     (default: groq)
    GROQ_MODEL    = model name for Groq
    NVIDIA_MODEL  = model name for NVIDIA NIM
"""
import json
import time
import sys
import argparse
from pathlib import Path

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root / "src"))
sys.path.insert(0, str(root / "evaluation"))

from src.config import settings
from src.providers.factory import create_provider
from src.schema.loader import load_schema_from_sql, parse_create_statements
from src.schema.retriever import SchemaRetriever
from src.schema.formatter import format_tables
from metrics import execute_sql, execution_match

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

BASELINE_PROMPT = """You are an expert SQL engineer.
Given a natural language question and a database schema,
write a correct SQL query to answer the question.

Return a JSON object:
{
  "sql": "SELECT ...",
  "explanation": "Brief explanation",
  "assumptions": ["Any assumptions"]
}"""

FEW_SHOT_PROMPT = """You are an expert SQL engineer. Given a question and schema, write SQL.

RULES:
1. SELECT only needed columns. No SELECT *.
2. Use exact column names from schema.
3. Return JSON: {"sql": "SELECT ...", "explanation": "...", "assumptions": [...]}

EXAMPLES:

Q: "How many customers?"
Schema: customers(customer_id, name, email, city, signup_date)
A: {"sql": "SELECT COUNT(*) FROM customers", "explanation": "Count all", "assumptions": []}

Q: "Products costing more than 100?"
Schema: products(product_id, name, category, price, stock_quantity)
A: {"sql": "SELECT name, price FROM products WHERE price > 100", "explanation": "Filter by price", "assumptions": []}

Q: "Customer with most orders?"
Schema: customers(customer_id, name), orders(order_id, customer_id)
A: {"sql": "SELECT c.name, COUNT(o.order_id) as cnt FROM customers c JOIN orders o ON c.customer_id = o.customer_id GROUP BY c.name ORDER BY cnt DESC LIMIT 1", "explanation": "Count and sort", "assumptions": []}

Q: "Total revenue?"
Schema: orders(order_id, total_amount)
A: {"sql": "SELECT SUM(total_amount) FROM orders", "explanation": "Sum amounts", "assumptions": []}

Q: "Each customer with order count?"
Schema: customers(customer_id, name), orders(order_id, customer_id, total_amount)
A: {"sql": "SELECT c.name, COUNT(o.order_id) FROM customers c LEFT JOIN orders o ON c.customer_id = o.customer_id GROUP BY c.name", "explanation": "Join and count", "assumptions": []}"""

SCHEMA_LINK_PROMPT = """You are an expert SQL engineer. Given a question and database schema, write SQL.

STEP 1 - SCHEMA LINKING: Identify which tables and columns map to the question.
STEP 2 - SQL GENERATION: Write the query using only the linked tables/columns.

RULES:
1. SELECT only needed columns. No SELECT *.
2. Use exact column names from schema.
3. Use correct JOIN foreign keys.
4. Return JSON: {"sql": "...", "explanation": "...", "schema_links": {"concept": "table.column"}, "assumptions": [...]}

EXAMPLES:
Q: "How many customers from New York?"
Link: customers -> customers table, New York -> customers.city
SQL: SELECT COUNT(*) FROM customers WHERE city = 'New York'

Q: "Orders by Alice Johnson?"
Link: orders -> orders, Alice Johnson -> customers.name, join via customer_id
SQL: SELECT o.order_id, o.order_date, o.total_amount FROM orders o JOIN customers c ON o.customer_id = c.customer_id WHERE c.name = 'Alice Johnson'

Q: "Highest revenue product?"
Link: product -> products, revenue -> quantity * unit_price, order items -> order_items
SQL: SELECT p.name, SUM(oi.quantity * oi.unit_price) as revenue FROM products p JOIN order_items oi ON p.product_id = oi.product_id GROUP BY p.name ORDER BY revenue DESC LIMIT 1"""

FEW_SHOT_SCHEMA_LINK_PROMPT = """You are an expert SQL engineer. Given a question and database schema, write SQL.

STEP 1 - SCHEMA LINKING: Map question concepts to exact tables and columns.
STEP 2 - SQL GENERATION: Write the query using linked tables/columns and the few-shot patterns below.

RULES:
1. SELECT only needed columns. No SELECT *.
2. Use exact column names from the schema provided.
3. Use correct JOIN foreign keys.
4. Return JSON: {"sql": "...", "explanation": "...", "schema_links": {"concept": "table.column"}, "assumptions": [...]}

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
SQL: SELECT SUM(total_amount) FROM orders"""

CONFIGS = {
    "A": ("Baseline", BASELINE_PROMPT),
    "B": ("Few-Shot + Column Selection", FEW_SHOT_PROMPT),
    "C": ("Schema Linking", SCHEMA_LINK_PROMPT),
    "D": ("Few-Shot + Schema Linking", FEW_SHOT_SCHEMA_LINK_PROMPT),
}

# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_single_question(provider, retriever, prompt, question, gold_sql, difficulty):
    """Run one question through one config. Returns a result dict."""
    t0 = time.time()
    try:
        relevant_tables = retriever.get_relevant(question, top_k=5)
        if not relevant_tables:
            relevant_tables = retriever.get_all()
        filtered = format_tables(relevant_tables)
        user_content = "SCHEMA:\n" + filtered + "\n\nQUESTION: " + question
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_content},
        ]
        result, response = provider.chat_json(messages)
        sql = result.get("sql", "")
        latency = time.time() - t0
        correct = execution_match(sql, gold_sql, db_path)
        result_rows = execute_sql(db_path, sql)
        return {
            "question": question, "gold_sql": gold_sql, "generated_sql": sql,
            "difficulty": difficulty, "correct": correct, "error": None,
            "latency_seconds": round(latency, 2),
            "input_tokens": getattr(response, "input_tokens", 0) if response else 0,
            "output_tokens": getattr(response, "output_tokens", 0) if response else 0,
            "total_tokens": getattr(response, "total_tokens", 0) if response else 0,
            "status": "success" if result_rows is not None else "error",
        }
    except Exception as e:
        return {
            "question": question, "gold_sql": gold_sql, "generated_sql": "",
            "difficulty": difficulty, "correct": False, "error": str(e)[:200],
            "latency_seconds": round(time.time() - t0, 2),
            "input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
            "status": "exception",
        }


def run_config(config_key, dataset, provider, retriever, resume_dir, resume=True):
    """Run one configuration. Supports resume from cached partial results."""
    label, prompt = CONFIGS[config_key]
    cache_file = resume_dir / f"config_{config_key}.json"

    # Load existing results for resume
    existing = {}
    if resume and cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            for r in cached:
                existing[r["question"]] = r
            print(f"  [resume] loaded {len(existing)} cached results from {cache_file.name}")
        except Exception:
            existing = {}

    results = []
    skipped = 0
    for i, item in enumerate(dataset):
        question = item["question"]
        gold_sql = item["gold_sql"]
        difficulty = item["difficulty"]

        if question in existing and existing[question].get("status") == "success":
            results.append(existing[question])
            skipped += 1
            continue

        print(f"  {i+1}/{len(dataset)} [{difficulty}] {question[:50]}...")
        r = run_single_question(provider, retriever, prompt, question, gold_sql, difficulty)
        results.append(r)

        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(results, indent=2), encoding="utf-8")

        if r["status"] == "exception" and "429" in str(r.get("error", "")):
            print("    [rate limited] pausing 5s...")
            time.sleep(5)

    if skipped:
        print(f"  [resume] skipped {skipped} already-completed questions")
    return results


def compute_metrics(results):
    total = len(results)
    correct = sum(1 for r in results if r["correct"])
    latencies = [r["latency_seconds"] for r in results if r["latency_seconds"] > 0]
    tokens = [r["total_tokens"] for r in results if r["total_tokens"] > 0]
    by_diff = {}
    for r in results:
        d = r["difficulty"]
        if d not in by_diff:
            by_diff[d] = {"total": 0, "correct": 0}
        by_diff[d]["total"] += 1
        if r["correct"]:
            by_diff[d]["correct"] += 1
    for d in by_diff:
        by_diff[d]["accuracy"] = by_diff[d]["correct"] / by_diff[d]["total"]
    failures = [r for r in results if not r["correct"]]
    fail_cats = {}
    for f in failures:
        if f.get("error"):
            cat = "exception"
        elif not f["generated_sql"]:
            cat = "empty_result"
        else:
            gen = f["generated_sql"].upper()
            gold = f["gold_sql"].upper()
            if "JOIN" in gold and "JOIN" not in gen:
                cat = "missing_join"
            elif "GROUP BY" in gold and "GROUP BY" not in gen:
                cat = "missing_group_by"
            elif "HAVING" in gold and "HAVING" not in gen:
                cat = "missing_having"
            elif "(SELECT" in gold:
                cat = "wrong_subquery"
            else:
                cat = "wrong_result"
        fail_cats[cat] = fail_cats.get(cat, 0) + 1
    return {
        "total": total, "correct": correct,
        "execution_accuracy": correct / total if total else 0,
        "avg_latency": sum(latencies) / len(latencies) if latencies else 0,
        "avg_tokens": sum(tokens) / len(tokens) if tokens else 0,
        "by_difficulty": by_diff, "failure_categories": fail_cats,
        "failure_count": len(failures),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Text-to-SQL Ablation Study")
    parser.add_argument("--config", nargs="+", default=list(CONFIGS.keys()),
                        choices=list(CONFIGS.keys()),
                        help="Which configs to run (default: all)")
    parser.add_argument("--dataset", default="evaluation/datasets/pilot_10.json",
                        help="Dataset JSON file (default: pilot_10.json)")
    parser.add_argument("--no-resume", action="store_true",
                        help="Ignore cached results and rerun everything")
    parser.add_argument("--output", default="evaluation/results/ablation_study.json",
                        help="Output file for final results")
    args = parser.parse_args()

    dataset_path = root / args.dataset
    with open(dataset_path) as f:
        dataset = json.load(f)

    provider = create_provider()
    model_name = getattr(provider, "model", "unknown")

    schema_text = load_schema_from_sql(settings.schema_path)
    tables = parse_create_statements(schema_text)
    retriever = SchemaRetriever(tables)

    resume_dir = root / "evaluation" / "results" / "partial"
    resume_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("ABLATION STUDY")
    print("=" * 80)
    print(f"Provider: {settings.provider}")
    print(f"Model: {model_name}")
    print(f"Dataset: {dataset_path.name} ({len(dataset)} questions)")
    print(f"Configs: {', '.join(args.config)}")
    print(f"Resume: {'yes' if not args.no_resume else 'no'}")
    print()

    all_results = {}
    all_metrics = {}

    for config_key in args.config:
        label, _ = CONFIGS[config_key]
        print(f"[Config {config_key}] {label}")
        print("-" * 40)
        results = run_config(
            config_key, dataset, provider, retriever, resume_dir,
            resume=not args.no_resume,
        )
        metrics = compute_metrics(results)
        all_results[config_key] = results
        all_metrics[config_key] = metrics
        print(f"  => {metrics['correct']}/{metrics['total']} "
              f"({metrics['execution_accuracy']*100:.1f}%) "
              f"avg {metrics['avg_latency']:.1f}s, {metrics['avg_tokens']:.0f} tokens")
        print()

    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    print()
    fmt = "{:<8} {:<22} {:>10} {:>10} {:>10} {:>8}"
    print(fmt.format("Config", "Name", "Accuracy", "Tokens", "Latency", "Fails"))
    print("-" * 78)
    for key in args.config:
        m = all_metrics[key]
        print(fmt.format(
            f"  {key}", CONFIGS[key][0],
            f"{m['execution_accuracy']*100:.1f}%",
            f"{m['avg_tokens']:.0f}",
            f"{m['avg_latency']:.1f}s",
            str(m["failure_count"]),
        ))

    print()
    dfmt = "{:<8} {:<22} {:>10} {:>10} {:>10}"
    print(dfmt.format("Config", "Name", "Easy", "Medium", "Hard"))
    print("-" * 68)
    for key in args.config:
        m = all_metrics[key]
        ea = m["by_difficulty"].get("easy", {}).get("accuracy", 0) * 100
        ma = m["by_difficulty"].get("medium", {}).get("accuracy", 0) * 100
        ha = m["by_difficulty"].get("hard", {}).get("accuracy", 0) * 100
        print(dfmt.format(
            f"  {key}", CONFIGS[key][0],
            f"{ea:.0f}%", f"{ma:.0f}%", f"{ha:.0f}%",
        ))

    print()
    print("Failure Analysis:")
    for key in args.config:
        m = all_metrics[key]
        if m["failure_categories"]:
            print(f"  Config {key} ({CONFIGS[key][0]}):")
            for cat, cnt in m["failure_categories"].items():
                print(f"    {cat}: {cnt}")

    out = root / args.output
    out.parent.mkdir(exist_ok=True)
    with open(out, "w") as f:
        json.dump({
            "provider": settings.provider,
            "model": model_name,
            "dataset": dataset_path.name,
            "configs": {k: all_metrics[k] for k in args.config},
            "results": {k: all_results[k] for k in args.config},
        }, f, indent=2)
    print(f"\nSaved to {out}")
