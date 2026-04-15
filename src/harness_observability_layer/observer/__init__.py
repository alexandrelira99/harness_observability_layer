"""Observer package namespace."""

from .analyzer import analyze_jsonl, load_events
from .events import Event
from .logger import JsonlEventLogger
from .metrics import compute_metrics, merge_spans, span_line_count

__all__ = [
    "Event",
    "JsonlEventLogger",
    "analyze_jsonl",
    "compute_metrics",
    "load_events",
    "merge_spans",
    "span_line_count",
]
