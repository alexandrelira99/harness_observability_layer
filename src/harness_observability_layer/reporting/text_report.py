"""Plain-text reporting helpers for observability sessions."""

from __future__ import annotations

from typing import Any, Dict


def build_session_text(session_id: str, summary: Dict[str, Any], metadata: Dict[str, Any] | None = None) -> str:
    """Render a concise plain-text session summary."""
    metadata = metadata or {}
    title = str(metadata.get("display_title") or session_id)
    failures = sum(int(v) for v in summary.get("tool_failures_by_name", {}).values())
    return (
        f"{title}\n"
        f"session={session_id}\n"
        f"tool_calls={summary.get('total_tool_calls', 0)}\n"
        f"files_read={summary.get('distinct_files_read', 0)}\n"
        f"files_edited={summary.get('distinct_files_edited', 0)}\n"
        f"failures={failures}\n"
        f"file_stats_resolution={summary.get('file_stats_resolution', 'enabled')}"
    )
