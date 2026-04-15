"""Observer package namespace."""

from observer.analyzer import analyze_jsonl, load_events
from observer.events import Event
from observer.logger import JsonlEventLogger
from observer.metrics import compute_metrics, merge_spans, span_line_count

__all__ = [
    "Event",
    "JsonlEventLogger",
    "analyze_jsonl",
    "compute_metrics",
    "load_events",
    "merge_spans",
    "span_line_count",
]

