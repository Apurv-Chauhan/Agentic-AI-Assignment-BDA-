
import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from pydantic import BaseModel, Field
from tabulate import tabulate
from src.config import LOGS_DIR


# Conservative detection: if a string appears to contain a credential,
# redact the entire string rather than risk leaving part of it behind.
SENSITIVE_PATTERNS = [
    re.compile(r"\b(password|passwd|pwd)\b", re.IGNORECASE),
    re.compile(r"\b(one[\s-]?time[\s-]?(passcode|password|code)|otp)\b", re.IGNORECASE),
    re.compile(r"\b(api[\s_-]?key|access[\s_-]?token|secret[\s_-]?key)\b", re.IGNORECASE),
    re.compile(r"\bBearer\s+\S+", re.IGNORECASE),
    re.compile(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"),
    re.compile(r"\b(cvv|cvc)\s*(?:is|=|:)?\s*\d{3,4}\b", re.IGNORECASE),
]


def redact_sensitive_text(value: str) -> str:
    """Redact a complete text field if it appears to contain credentials."""
    if not isinstance(value, str):
        return value

    if any(pattern.search(value) for pattern in SENSITIVE_PATTERNS):
        return "[REDACTED SENSITIVE TEXT]"

    return value


def sanitize_json_value(value):
    """Recursively redact sensitive strings in JSON-compatible data."""
    if isinstance(value, str):
        return redact_sensitive_text(value)

    if isinstance(value, list):
        return [sanitize_json_value(item) for item in value]

    if isinstance(value, dict):
        return {
            key: sanitize_json_value(item)
            for key, item in value.items()
        }

    return value


class TraceRecord(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    scenario_id: str
    question: str
    student_id: Optional[str] = None
    success: bool
    tools_used: List[str] = Field(default_factory=list)
    tool_assessment: str = "Appropriate"
    latency_sec: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    retrieved_evidence: List[str] = Field(default_factory=list)
    final_response: str = ""
    evaluation_notes: str = ""


class ExecutionTracer:
    """
    Collect structured traces while redacting sensitive text before
    retaining or writing trace records.
    """

    def __init__(self, log_filename: str = "agent_trace_log.jsonl"):
        self.log_file = LOGS_DIR / log_filename
        self.traces: List[TraceRecord] = []

    def record_trace(self, trace: TraceRecord):
        # Sanitize the complete serialized record before retaining or writing it.
        safe_data = sanitize_json_value(trace.model_dump())
        safe_trace = TraceRecord.model_validate(safe_data)

        self.traces.append(safe_trace)

        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        with open(self.log_file, "a", encoding="utf-8") as file:
            file.write(safe_trace.model_dump_json() + "\n")

    def generate_summary_table(self) -> str:
        table_rows = []

        for trace in self.traces:
            tools_str = (
                ", ".join(trace.tools_used)
                if trace.tools_used
                else "None (Direct / RAG)"
            )

            evidence_str = (
                "; ".join(trace.retrieved_evidence)
                if trace.retrieved_evidence
                else "None"
            )

            if len(evidence_str) > 40:
                evidence_str = evidence_str[:37] + "..."

            status_str = "PASS" if trace.success else "FAIL"

            table_rows.append([
                trace.scenario_id,
                trace.question[:30] + (
                    "..." if len(trace.question) > 30 else ""
                ),
                status_str,
                f"{tools_str} ({trace.tool_assessment})",
                f"{trace.latency_sec:.2f}s",
                (
                    f"{trace.prompt_tokens} in / "
                    f"{trace.completion_tokens} out "
                    f"({trace.total_tokens} tot)"
                ),
                evidence_str,
            ])

        headers = [
            "Scenario",
            "Question",
            "Status",
            "Tools Used & Assessment",
            "Latency",
            "Token Usage (In/Out/Tot)",
            "Retrieved Evidence",
        ]

        return tabulate(table_rows, headers=headers, tablefmt="grid")

    def compute_aggregate_metrics(self) -> Dict[str, Any]:
        if not self.traces:
            return {}

        total_runs = len(self.traces)
        successful_runs = sum(1 for trace in self.traces if trace.success)

        avg_latency = (
            sum(trace.latency_sec for trace in self.traces) / total_runs
        )

        total_prompt_tokens = sum(
            trace.prompt_tokens for trace in self.traces
        )
        total_completion_tokens = sum(
            trace.completion_tokens for trace in self.traces
        )
        total_tokens = sum(trace.total_tokens for trace in self.traces)

        return {
            "total_runs": total_runs,
            "successful_runs": successful_runs,
            "accuracy_pct": round(
                (successful_runs / total_runs) * 100, 1
            ),
            "avg_latency_sec": round(avg_latency, 2),
            "total_prompt_tokens": total_prompt_tokens,
            "total_completion_tokens": total_completion_tokens,
            "total_tokens": total_tokens,
        }


def sanitize_existing_trace_log():
    """
    Sanitize existing JSONL traces in place using a temporary file.
    Invalid lines are skipped so malformed or sensitive raw records
    are not copied into the replacement log.
    """
    path = LOGS_DIR / "agent_trace_log.jsonl"

    if not path.exists():
        print("No existing trace log found.")
        return

    temp_path = path.with_suffix(".jsonl.tmp")
    processed = 0
    skipped = 0

    with open(path, "r", encoding="utf-8", errors="replace") as source, \
            open(temp_path, "w", encoding="utf-8") as target:

        for line in source:
            if not line.strip():
                continue

            try:
                record = json.loads(line)
                safe_record = sanitize_json_value(record)
                target.write(json.dumps(safe_record, ensure_ascii=False) + "\n")
                processed += 1
            except (json.JSONDecodeError, TypeError, ValueError):
                skipped += 1

    # Replace the old log only after writing the sanitized replacement.
    temp_path.replace(path)

    print(f"Sanitized trace records: {processed}")
    print(f"Skipped malformed records: {skipped}")
    print("Existing trace log replaced with sanitized records.")
