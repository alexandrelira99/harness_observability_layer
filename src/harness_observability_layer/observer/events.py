"""Canonical event models for harness observability."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4


def utc_now_iso() -> str:
    """Return a UTC ISO-8601 timestamp."""
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class Event:
    """A canonical append-only observability event."""

    event_type: str
    source: str
    session_id: str
    task_id: str
    agent_id: str = "main"
    payload: Dict[str, Any] = field(default_factory=dict)
    ts: str = field(default_factory=utc_now_iso)
    event_id: str = field(default_factory=lambda: str(uuid4()))

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable representation of the event."""
        return asdict(self)

