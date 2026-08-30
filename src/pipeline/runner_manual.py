"""Main pipeline"""

from __future__ import annotations
import json, logging, time
from ..config import settings
from ..providers.base import LLMProvider, ChatResponse
from ..providers.factory import create_provider
from ..schema.loader import load_schema_from_sql, parse_create_statements
from ..schema.retriever import SchemaRetriever
from ..schema.formatter import format_tables
from ..agents.sql_agent import SQLAgent
from ..agents.validator_agent import ValidatorAgent
from ..agents.repair_agent import RepairAgent
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
    def __init__(self, provider=None, schema_path=None):
        self.provider = provider or create_provider()
        self.schema_path = schema_path or settings.schema_path
        self.model_name = getattr(self.provider, "model", "unknown")
        schema_text = load_schema_from_sql(self.schema_path)
        self.tables = parse_create_statements(schema_text)
        self.schema_text = format_tables(self.tables)
        self.retriever = SchemaRetriever(self.tables)
        self.sql_agent = SQLAgent(self.provider)
        self.validator_agent = ValidatorAgent(self.provider)
        self.repair_agent = RepairAgent(self.provider)
        self.db = DatabaseConnection(settings.database_url)
        self.executor = SQLExecutor(self.db, read_only=True)
        self.cache = CacheStore(settings.cache_db) if settings.cache_enabled else None

    def _accum_tokens(self, total, response):
        total["input"] += response.input_tokens
        total["output"] += response.output_tokens

    def run(self, question):
        start = time.time()
        steps = []
        cache_hit = False
        repair_attempts = 0
        tokens = {"input": 0, "output": 0}

        if self.cache:
            cached = self.cache.get(question, prefix="pipeline", model=self.model_name)
            if cached:
                cache_hit = True
                return PipelineResult(question=question, sql=cached.get("sql", ""),
                    result=cached.get("result", {}), steps=[{"step": "cache_hit", "time_ms": 0}],
                    total_time_ms=(time.time()-start)*1000, model=self.model_name, cache_hit=True)

        t0 = time.time()
        relevant_tables = self.retriever.get_relevant(question, top_k=5)
        if not relevant_tables:
            relevant_tables = self.retriever.get_all()
        relevant_schema = format_tables(relevant_tables)
        steps.append({"step": "schema_retrieval", "tables": [t.name for t in relevant_tables], "time_ms": (time.time()-t0)*1000})

        t0 = time.time()
        sql_result, sql_response = self.sql_agent.run(question, relevant_schema)
        self._accum_tokens(tokens, sql_response)
        sql = sql_result.get("sql", "")
        steps.append({"step": "sql_generation", "sql": sql, "explanation": sql_result.get("explanation", ""), "time_ms": (time.time()-t0)*1000})

        t0 = time.time()
        validation, val_response = self.validator_agent.run(question, relevant_schema, sql)
        self._accum_tokens(tokens, val_response)
        if not validation.get("is_valid", True) and validation.get("corrected_sql"):
            sql = validation["corrected_sql"]
            steps.append({"step": "validation_fix", "corrected_sql": sql, "issues": validation.get("issues", []), "time_ms": (time.time()-t0)*1000})
        else:
            steps.append({"step": "validation", "is_valid": True, "time_ms": (time.time()-t0)*1000})

        t0 = time.time()
        exec_result = self.executor.execute(sql)
        steps.append({"step": "execution", "success": exec_result.success, "row_count": exec_result.row_count, "time_ms": (time.time()-t0)*1000})

        if not exec_result.success:
            for attempt in range(settings.max_repair_attempts):
                repair_attempts += 1
                t0 = time.time()
                repair, repair_response = self.repair_agent.run(question, relevant_schema, sql, exec_result.error)
                self._accum_tokens(tokens, repair_response)
                sql = repair.get("fixed_sql", sql)
                steps.append({"step": f"repair_attempt_{attempt+1}", "sql": sql, "root_cause": repair.get("root_cause", ""), "time_ms": (time.time()-t0)*1000})
                t0 = time.time()
                exec_result = self.executor.execute(sql)
                steps.append({"step": f"re_execution_{attempt+1}", "success": exec_result.success, "row_count": exec_result.row_count, "time_ms": (time.time()-t0)*1000})
                if exec_result.success:
                    break

        result_data = exec_result.to_dict()
        total_time = (time.time() - start) * 1000
        if self.cache and exec_result.success:
            self.cache.set(question, {"sql": sql, "result": result_data}, prefix="pipeline", model=self.model_name)
        return PipelineResult(question=question, sql=sql, result=result_data, steps=steps,
            total_time_ms=total_time, model=self.model_name, cache_hit=cache_hit,
            repair_attempts=repair_attempts, input_tokens=tokens["input"], output_tokens=tokens["output"])
