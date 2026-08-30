"""Run the 8-question benchmark and save results incrementally."""
import sys, json, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
sys.path.insert(0, str(Path(__file__).parent / "evaluation"))

from src.pipeline.runner import TextToSQLPipeline
from metrics import execute_sql, execution_match

DATASET = "evaluation/datasets/benchmark_8.json"
OUTPUT = "evaluation/results/benchmark_final.json"


def main():
    dataset = json.loads(Path(DATASET).read_text())
    db_path = str(Path("data/app.db").resolve())
    pipeline = TextToSQLPipeline()

    results = []
    for i, item in enumerate(dataset):
        q = item["question"]
        gold = item["gold_sql"]
        diff = item["difficulty"]
        print(f"  {i+1}/{len(dataset)} [{diff}] {q[:50]}...", flush=True)

        t0 = time.time()
        try:
            r = pipeline.run(q)
            latency = time.time() - t0
            correct = execution_match(r.sql, gold, db_path)
            results.append({
                "question": q, "gold_sql": gold, "generated_sql": r.sql,
                "difficulty": diff, "correct": correct,
                "repair_attempts": r.repair_attempts,
                "latency_seconds": round(latency, 2),
                "input_tokens": r.input_tokens, "output_tokens": r.output_tokens,
                "total_tokens": r.input_tokens + r.output_tokens,
                "status": r.status, "error": r.result.get("error"),
                "model": r.model, "cache_hit": r.cache_hit,
            })
        except Exception as e:
            results.append({
                "question": q, "gold_sql": gold, "generated_sql": "",
                "difficulty": diff, "correct": False,
                "repair_attempts": 0, "latency_seconds": round(time.time() - t0, 2),
                "input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
                "status": "exception", "error": str(e),
                "model": "", "cache_hit": False,
            })

        _save(results)

    total = len(results)
    correct = sum(1 for r in results if r["correct"])
    print(f"\n{'='*60}")
    print(f"Total: {total} | Correct: {correct} | Accuracy: {correct/total*100:.1f}%")
    print(f"{'='*60}")


def _save(results):
    Path(OUTPUT).parent.mkdir(parents=True, exist_ok=True)
    total = len(results)
    correct = sum(1 for r in results if r["correct"])
    failed = total - correct
    repaired = sum(1 for r in results if r["repair_attempts"] > 0 and r["correct"])
    avg_lat = sum(r["latency_seconds"] for r in results) / total if total else 0
    avg_tok = sum(r["total_tokens"] for r in results) / total if total else 0
    avg_rep = sum(r["repair_attempts"] for r in results) / total if total else 0

    data = {
        "metrics": {
            "total": total, "correct": correct, "failed": failed,
            "execution_accuracy": correct / total if total else 0,
            "failure_rate": failed / total if total else 0,
            "repair_success_rate": repaired / failed if failed else 0,
            "avg_latency_seconds": round(avg_lat, 2),
            "avg_tokens": round(avg_tok, 0),
            "avg_repairs": round(avg_rep, 2),
            "repaired_successfully": repaired,
        },
        "results": results,
    }
    Path(OUTPUT).write_text(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
