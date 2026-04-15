"""Offline analysis for JSONL event logs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from .metrics import compute_metrics


def load_events(path: str | Path) -> List[Dict[str, Any]]:
    """Load events from a JSONL file."""
    input_path = Path(path)
    events: List[Dict[str, Any]] = []
    if not input_path.exists():
        return events

    with input_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def analyze_jsonl(path: str | Path, *, resolve_file_stats: bool = True) -> Dict[str, Any]:
    """Analyze a JSONL event file and return summary metrics."""
    return compute_metrics(load_events(path), resolve_file_stats=resolve_file_stats)
