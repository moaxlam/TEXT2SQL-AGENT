"""Main pipeline — CrewAI-powered with Python-controlled execution.

Python is the source of truth for SQL execution and repair loop bounds.
CrewAI agents handle LLM-powered SQL generation, validation, and repair.
"""
from __future__ import annotations
import json, logging, time
from ..config import settings
from ..crewai_runner import CrewAIRunner, _get_schema
from ..execution.connection import DatabaseConnection
from ..execution.executor import SQLExecutor
from ..cache.store import CacheStore

logger = logging.getLogger(__name__)


class PipelineResult:
    def __init__(self, question, sql, result, steps, total_time_ms,
                 model="", cache_hit=False, repair_attempts=0,
                 input_tokens=0, output_tokens=0):
        self.question = question
        self.sql = sql
        self.result = result
        self.steps = steps
        self.total_time_ms = total_time_ms
        self.model = model
        self.cache_hit = cache_hit
        self.repair_attempts = repair_attempts
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens

    @property
    def status(self):
        return "success" if self.result.get("success") else "error"

    def to_dict(self):
        return {
            "question": self.question, "generated_sql": self.sql, "final_sql": self.sql,
            "status": self.status, "repair_attempts": self.repair_attempts,
            "rows_returned": self.result.get("row_count", 0),
            "latency_seconds": round(self.total_time_ms / 1000, 2),
            "cache_hit": self.cache_hit, "model": self.model,
            "error": self.result.get("error"),
            "input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
            "total_tokens": self.input_tokens + self.output_tokens, "steps": self.steps,
        }

    def __str__(self):
        return f"Q: {self.question} | Status: {self.status} | Tokens: {self.input_tokens}in/{self.output_tokens}out"


class TextToSQLPipeline:
    """CrewAI-powered pipeline with Python-controlled execution."""

    def __init__(self, crew_runner=None):
        self.crew_runner = crew_runner or CrewAIRunner()
        self.model_name = getattr(self.crew_runner.llm, "model", "unknown")
        self.db = DatabaseConnection(settings.database_url)
        self.executor = SQLExecutor(self.db, read_only=True)
        self.cache = CacheStore(settings.cache_db) if settings.cache_enabled else None

    def run(self, question):
        start = time.time()
        steps = []
        cache_hit = False
        repair_attempts = 0

        # Check cache
        if self.cache:
            cached = self.cache.get(question, prefix="pipeline", model=self.model_name)
            if cached:
                cache_hit = True
                return PipelineResult(question=question, sql=cached.get("sql", ""),
                    result=cached.get("result", {}), steps=[{"step": "cache_hit", "time_ms": 0}],
                    total_time_ms=(time.time()-start)*1000, model=self.model_name, cache_hit=True)

        # 1. Schema retrieval (Python — deterministic)
        t0 = time.time()
        schema_text = _get_schema(question)
        steps.append({"step": "schema_retrieval", "time_ms": (time.time()-t0)*1000})

        # 2. Generate SQL (CrewAI — LLM)
        t0 = time.time()
        sql, gen_meta = self.crew_runner.generate_sql(question, schema_text)
        steps.append({"step": "sql_generation", "sql": sql, "time_ms": gen_meta["latency_seconds"]})

        # 3. Execute SQL (Python — source of truth)
        t0 = time.time()
        exec_result = self.executor.execute(sql)
        steps.append({"step": "execution", "success": exec_result.success,
                       "row_count": exec_result.row_count, "time_ms": (time.time()-t0)*1000})

        # 4. Optional validation diagnostic (CrewAI — analysis only, does NOT replace SQL)
        if not exec_result.success:
            try:
                t0 = time.time()
                validation = self.crew_runner.validate_sql(question, schema_text, sql)
                steps.append({"step": "validation_diagnostic", "validation": validation,
                               "time_ms": (time.time()-t0)*1000})
            except Exception as e:
                logger.warning("Validation diagnostic failed: %s", e)

        # 5. Repair loop (Python-controlled, bounded)
        if not exec_result.success:
            for attempt in range(settings.max_repair_attempts):
                repair_attempts += 1
                t0 = time.time()
                sql, repair_meta = self.crew_runner.repair_sql(
                    question, schema_text, sql, exec_result.error)
                steps.append({"step": f"repair_attempt_{attempt+1}", "sql": sql,
                               "time_ms": repair_meta["latency_seconds"]})

                # Python executes the repaired SQL
                t0 = time.time()
                exec_result = self.executor.execute(sql)
                steps.append({"step": f"re_execution_{attempt+1}", "success": exec_result.success,
                               "row_count": exec_result.row_count, "time_ms": (time.time()-t0)*1000})
                if exec_result.success:
                    break

        # Cache successful results
        result_data = exec_result.to_dict()
        total_time = (time.time() - start) * 1000
        if self.cache and exec_result.success:
            self.cache.set(question, {"sql": sql, "result": result_data},
                           prefix="pipeline", model=self.model_name)

        return PipelineResult(question=question, sql=sql, result=result_data, steps=steps,
            total_time_ms=total_time, model=self.model_name, cache_hit=cache_hit,
            repair_attempts=repair_attempts)
