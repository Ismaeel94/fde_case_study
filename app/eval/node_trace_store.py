import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langchain_core.messages import BaseMessage, messages_to_dict

NODE_TRACES_DIR = Path(__file__).resolve().parent / "node_traces"


def _trace_payload(trace: Any) -> dict:
    if hasattr(trace, "model_dump"):
        return trace.model_dump()
    if isinstance(trace, dict):
        return trace
    raise TypeError(f"Unsupported node trace type: {type(trace)!r}")


def _serialize_graph_input(messages: list[BaseMessage]) -> list[dict]:
    return messages_to_dict(messages)


def persist_run_trace(
    *,
    graph_input: list[BaseMessage],
    graph_output: str | None,
    node_traces: list[Any],
) -> Path | None:
    """Write input, output, and node traces from one graph run to a single JSON file."""
    NODE_TRACES_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    path = NODE_TRACES_DIR / f"{timestamp}_run_trace.json"
    record = {
        "input": _serialize_graph_input(graph_input),
        "output": graph_output,
        "node_traces": [_trace_payload(trace) for trace in node_traces],
    }
    path.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
    return path
