"""Plain-text reporting helpers for observability sessions."""

from __future__ import annotations

from typing import Any, Dict


def _format_duration(seconds: float) -> str:
    if seconds <= 0:
        return "—"
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes = seconds / 60
    if minutes < 60:
        return f"{minutes:.1f}m"
    hours = minutes / 60
    return f"{hours:.1f}h"


def _format_cost(cost: Any) -> str:
    if cost is None:
        return "—"
    c = float(cost)
    if c < 0.01:
        return f"${c:.4f}"
    return f"${c:.2f}"


def _format_cost_line(summary: Dict[str, Any]) -> str:
    plan = summary.get("plan_type")
    cost = summary.get("estimated_cost_usd")
    if plan:
        label = plan.capitalize()
        if cost is not None:
            return f"{label} (API-equiv {_format_cost(cost)})"
        return label
    return _format_cost(cost)


def _format_tokens(count: int) -> str:
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1_000:
        return f"{count / 1_000:.1f}K"
    return str(count)


def build_session_text(
    session_id: str, summary: Dict[str, Any], metadata: Dict[str, Any] | None = None
) -> str:
    """Render a concise plain-text session summary."""
    metadata = metadata or {}
    title = str(metadata.get("display_title") or session_id)
    failures = sum(int(v) for v in summary.get("tool_failures_by_name", {}).values())
    efficiency = summary.get("efficiency_indicators", {})
    return (
        f"{title}\n"
        f"session={session_id}\n"
        f"model={summary.get('model') or '—'}\n"
        f"duration={_format_duration(summary.get('session_duration_seconds', 0))}\n"
        f"tool_calls={summary.get('total_tool_calls', 0)}\n"
        f"files_read={summary.get('distinct_files_read', 0)}\n"
        f"files_edited={summary.get('distinct_files_edited', 0)}\n"
        f"failures={failures}\n"
        f"turns={summary.get('turns_per_session', 0)}\n"
        f"total_tokens={_format_tokens(summary.get('total_tokens', 0))}\n"
        f"input_tokens={_format_tokens(summary.get('total_input_tokens', 0))}\n"
        f"output_tokens={_format_tokens(summary.get('total_output_tokens', 0))}\n"
        f"cache_hit_rate={summary.get('cache_hit_rate_pct', 0):.1f}%\n"
        f"est_cost={_format_cost_line(summary)}\n"
        f"tools_per_minute={efficiency.get('tool_calls_per_minute', 0):.1f}\n"
        f"edits_per_minute={efficiency.get('edits_per_minute', 0):.1f}\n"
        f"continuation_loops={efficiency.get('continuation_loops', 0)}\n"
        f"max_tokens_stops={efficiency.get('max_tokens_stops', 0)}\n"
        f"file_stats_resolution={summary.get('file_stats_resolution', 'enabled')}"
    )
