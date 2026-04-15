"""Security and privacy helpers for HOL."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List


_SAFE_SEGMENT_RE = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_session_id(value: str, fallback: str = "session") -> str:
    """Return a filesystem-safe session identifier."""
    text = (value or "").strip()
    text = text.replace("\\", "/").split("/")[-1]
    text = _SAFE_SEGMENT_RE.sub("-", text).strip("._-")
    if not text:
        text = fallback
    return text[:120]


def sanitize_project_label(value: str | None, fallback: str = "session") -> str:
    """Return a display-safe project label."""
    if not value:
        return fallback
    cleaned = _SAFE_SEGMENT_RE.sub("-", value).strip("._-")
    return cleaned or fallback


def redact_text(value: str | None, replacement: str = "[redacted]") -> str:
    """Return a redacted string placeholder."""
    if not value:
        return replacement
    return replacement


def redact_path(value: str | None) -> str:
    """Redact a path while keeping only the trailing filename for operator orientation."""
    if not value:
        return "[redacted-path]"
    path = Path(str(value))
    parts = [part for part in path.parts if part not in {"/", "\\"}]
    if not parts:
        return "[redacted-path]"
    if len(parts) == 1:
        return parts[0]
    return f".../{parts[-1]}"


def redact_summary(summary: Dict[str, Any]) -> Dict[str, Any]:
    """Return a redacted copy of a session summary."""
    redacted = dict(summary)
    files = {}
    for path, meta in (summary.get("files") or {}).items():
        files[redact_path(path)] = dict(meta)
    redacted["files"] = files
    redacted["edited_without_prior_read"] = [redact_path(path) for path in summary.get("edited_without_prior_read", [])]
    return redacted


def redact_metadata(metadata: Dict[str, Any] | None) -> Dict[str, Any]:
    """Return a redacted copy of session metadata."""
    metadata = dict(metadata or {})
    started_at = metadata.get("started_at")
    technical_id = metadata.get("technical_id")
    return {
        **metadata,
        "display_title": "Redacted Session",
        "display_subtitle": started_at or "Sensitive details redacted",
        "technical_id": redact_text(str(technical_id) if technical_id else None),
        "project_name": redact_text(str(metadata.get("project_name")) if metadata.get("project_name") else None),
        "first_user_message": None,
    }


def redact_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return redacted events for report rendering."""
    redacted_events: List[Dict[str, Any]] = []
    for event in events:
        copied = dict(event)
        payload = dict(copied.get("payload") or {})
        if "path" in payload:
            payload["path"] = redact_path(str(payload["path"]))
        if "message" in payload:
            payload["message"] = "[redacted]"
        copied["payload"] = payload
        redacted_events.append(copied)
    return redacted_events


def is_relative_to(base: Path, candidate: Path) -> bool:
    """Compat helper for Path.is_relative_to across Python versions."""
    try:
        candidate.relative_to(base)
        return True
    except ValueError:
        return False
