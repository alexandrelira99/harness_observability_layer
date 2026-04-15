"""JSONL event logger."""

from __future__ import annotations

import json
from pathlib import Path

from .events import Event


class JsonlEventLogger:
    """Append-only JSONL logger for observability events."""

    def __init__(self, output_path: str | Path):
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, event: Event) -> None:
        """Persist an event as a single JSON line."""
        with self.output_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.to_dict(), ensure_ascii=True))
            handle.write("\n")

