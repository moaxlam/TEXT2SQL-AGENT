"""Wrapper to run evaluation with correct paths."""
import sys
from pathlib import Path

root = Path('.').resolve()
sys.path.insert(0, str(root / 'src'))
sys.path.insert(0, str(root / 'evaluation'))

# Import and run with args
import argparse, json, time
from src.config import settings
from src.pipeline.runner import TextToSQLPipeline
from metrics import execute_sql, execution_match, compute_metrics

def load_dataset(path):
    with open(path) as f:
        return json.load(f)

def run_baseline(pipeline, dataset, db_path):
    results = []
    for i, item in enumerate(dataset):
        question = item["question"]
        gold_sql = item["gold_sql"]
        difficulty = item["difficulty"]
        print(f"  {i+1}/{len(dataset)} [{difficulty}] {question[:50]}")
        schema_text = pipeline.schema_text
        t0 = time.time()
        try:
            sql_result, sql_response = pipeline.sql_agent.run(question, schema_text)
            sql = sql_result.get("sql", "")
            latency = time.time() - t0
            correct = execution_match(sql, gold_sql, db_path)
            result_rows = execute_sql(db_path, sql)
            results.append({
                "question": question, "gold_sql": gold_sql, "generated_sql": sql,
                "difficulty": difficulty, "correct": correct, "error": None,
                "latency_seconds": round(latency, 2),
                "input_tokens": sql_response.input_tokens, "output_tokens": sql_response.output_tokens,
                "total_tokens": sql_response.total_tokens, "repair_attempts": 0,
                "status": "success" if result_rows is not None else "error",
            })
        except Exception as e:
            results.append({
                "question": question, "gold_sql": gold_sql, "generated_sql": "",
                "difficulty": difficulty, "correct": False, "error": str(e),
                "latency_seconds": round(time.time() - t0, 2),
                "input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
                "repair_attempts": 0, "status": "exception",
            })
    return results

def run_full(pipeline, dataset, db_path):
    results = []
    for i, item in enumerate(dataset):
        question = item["question"]
        gold_sql = item["gold_sql"]
        difficulty = item["difficulty"]
        print(f"  {i+1}/{len(dataset)} [{difficulty}] {question[:50]}")
        try:
            r = pipeline.run(question)
            correct = execution_match(r.sql, gold_sql, db_path)
            results.append({
                "question": question, "gold_sql": gold_sql,
                "generated_sql": r.sql, "final_sql": r.sql,
                "difficulty": difficulty, "correct": correct,
                "error": r.result.get("error"),
                "latency_seconds": r.to_dict()["latency_seconds"],
                "input_tokens": r.input_tokens, "output_tokens": r.output_tokens,
                "total_tokens": r.input_tokens + r.output_tokens,
                "repair_attempts": r.repair_attempts, "status": r.status,
            })
        except Exception as e:
            results.append({
                "question": question, "gold_sql": gold_sql, "generated_sql": "",
                "difficulty": difficulty, "correct": False, "error": str(e),
                "latency_seconds": 0, "input_tokens": 0, "output_tokens": 0,
                "total_tokens": 0, "repair_attempts": 0, "status": "exception",
            })
    return results

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="evaluation/datasets/local_ecommerce.json")
    parser.add_argument("--system", choices=["baseline", "full"], default="full")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    
    dataset = load_dataset(args.dataset)
    if args.limit:
        dataset = dataset[:args.limit]
    
    db_path = settings.database_url.replace("sqlite:///", "")
    pipeline = TextToSQLPipeline()
    
    print(f"Running {args.system} on {len(dataset)} questions...")
    
    if args.system == "baseline":
        results = run_baseline(pipeline, dataset, db_path)
    else:
        results = run_full(pipeline, dataset, db_path)
    
    metrics = compute_metrics(results)
    
    print()
    print("=" * 60)
    print(f"System: {args.system}")
    print(f"Total: {metrics['total']} | Correct: {metrics['correct']} | Accuracy: {metrics['execution_accuracy']*100:.1f}%")
    print(f"Avg latency: {metrics['avg_latency_seconds']:.1f}s | Avg tokens: {metrics['avg_tokens_per_query']:.0f}")
    print(f"Avg repairs: {metrics['avg_repairs']:.1f} | Repair rate: {metrics['repair_rate']*100:.1f}%")
    print("=" * 60)
    for diff, stats in metrics["by_difficulty"].items():
        print(f"  {diff}: {stats['correct']}/{stats['total']} ({stats['accuracy']*100:.0f}%)")
    
    output = args.output or f"evaluation/results/{args.system}_results.json"
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        json.dump({"metrics": metrics, "results": results}, f, indent=2)
    print(f"\nResults saved to {output}")

if __name__ == "__main__":
    main()
