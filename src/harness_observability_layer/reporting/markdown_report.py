"""Markdown reporting for observability sessions."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List
from harness_observability_layer.security import redact_path


def _top_items(values: Dict[str, Any], limit: int = 5) -> List[tuple[str, int]]:
    return sorted(
        ((str(name), int(count)) for name, count in values.items()),
        key=lambda item: (-item[1], item[0]),
    )[:limit]


def _top_files(
    files: Dict[str, Dict[str, Any]], limit: int = 5
) -> List[tuple[str, Dict[str, Any]]]:
    return sorted(
        files.items(),
        key=lambda item: (
            -(item[1].get("read_coverage_pct") or 0),
            -(item[1].get("edit_count") or 0),
            item[0],
        ),
    )[:limit]


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


def _format_token_breakdown(summary: Dict[str, Any]) -> str:
    input_tokens = int(summary.get("total_input_tokens", 0) or 0)
    cache_tokens = int(summary.get("total_cache_read_tokens", 0) or 0)
    output_tokens = int(summary.get("total_output_tokens", 0) or 0)
    if cache_tokens:
        return (
            f"{_format_tokens(input_tokens)} in / "
            f"{_format_tokens(cache_tokens)} cache / "
            f"{_format_tokens(output_tokens)} out"
        )
    return f"{_format_tokens(input_tokens)} in / {_format_tokens(output_tokens)} out"


def build_session_markdown(
    session_id: str,
    summary: Dict[str, Any],
    metadata: Dict[str, Any] | None = None,
    verbosity: str = "normal",
) -> str:
    """Render a session summary as chat-friendly markdown."""
    metadata = metadata or {}
    title = str(metadata.get("display_title") or session_id)
    subtitle = str(metadata.get("display_subtitle") or session_id)
    failures = sum(int(v) for v in summary.get("tool_failures_by_name", {}).values())
    lines = [
        f"# {title}",
        "",
        subtitle,
        "",
        "## Summary",
        f"- Session: `{session_id}`",
        f"- Model: {summary.get('model') or '—'}",
        f"- Duration: {_format_duration(summary.get('session_duration_seconds', 0))}",
        f"- Tool calls: {summary.get('total_tool_calls', 0)}",
        f"- Files read: {summary.get('distinct_files_read', 0)}",
        f"- Files edited: {summary.get('distinct_files_edited', 0)}",
        f"- Failures: {failures}",
        f"- Turns: {summary.get('turns_per_session', 0)}",
        f"- Total tokens: {_format_tokens(summary.get('total_tokens', 0))} ({_format_token_breakdown(summary)})",
        f"- Est. cost: {_format_cost_line(summary)}",
        f"- Cache hit rate: {summary.get('cache_hit_rate_pct', 0):.1f}%",
    ]

    tools = _top_items(summary.get("tool_calls_by_name", {}))
    if tools:
        lines.extend(["", "## Most Used Tools"])
        lines.extend(f"- `{name}`: {count}" for name, count in tools)

    files = _top_files(summary.get("files", {}))
    if files:
        lines.extend(["", "## Top Files"])
        for path, meta in files:
            coverage = meta.get("read_coverage_pct")
            coverage_text = "n/a" if coverage is None else f"{coverage:.2f}%"
            status = meta.get("total_lines_status")
            if status == "disabled":
                coverage_text = "disabled"
            elif status == "unresolved" and coverage is None:
                coverage_text = "unresolved"
            lines.append(
                f"- `{path}`: read {meta.get('union_lines_read', 0)} lines, coverage {coverage_text}, edits {meta.get('edit_count', 0)}"
            )

    edited_without_read = summary.get("edited_without_prior_read", [])
    reread_files = summary.get("reread_files", [])
    read_without_edit = summary.get("read_without_edit", [])
    if edited_without_read or reread_files or read_without_edit:
        lines.extend(["", "## Warnings"])
        for path in edited_without_read[:8]:
            lines.append(f"- Edited without prior read: `{path}`")
        for path in reread_files[:8]:
            lines.append(f"- Re-read file: `{path}`")
        for path in read_without_edit[:8]:
            lines.append(f"- Read without edit: `{path}`")

    efficiency = summary.get("efficiency_indicators", {})
    if efficiency:
        lines.extend(["", "## Efficiency Indicators"])
        lines.append(
            f"- Edited w/o read ratio: {efficiency.get('edited_without_read_ratio', 0):.1f}%"
        )
        lines.append(f"- Re-read ratio: {efficiency.get('reread_ratio', 0):.1f}%")
        lines.append(f"- Failure rate: {efficiency.get('failure_rate_pct', 0):.1f}%")
        lines.append(f"- Continuation loops: {efficiency.get('continuation_loops', 0)}")
        lines.append(f"- Max-token stops: {efficiency.get('max_tokens_stops', 0)}")
        lines.append(f"- Tools/min: {efficiency.get('tool_calls_per_minute', 0):.1f}")
        lines.append(f"- Edits/min: {efficiency.get('edits_per_minute', 0):.1f}")

    stop_reasons = summary.get("stop_reasons", {})
    if stop_reasons:
        lines.extend(["", "## Stop Reasons"])
        for reason, count in sorted(
            stop_reasons.items(), key=lambda item: (-item[1], item[0])
        ):
            lines.append(f"- {reason}: {count}")

    bash_categories = summary.get("bash_command_categories", {})
    if bash_categories:
        lines.extend(["", "## Bash Command Categories"])
        for cat, cnt in sorted(
            bash_categories.items(), key=lambda item: (-item[1], item[0])
        ):
            lines.append(f"- {cat}: {cnt}")

    if verbosity == "high":
        skills = _top_items(summary.get("skill_loads_by_name", {}), limit=10)
        plugins = _top_items(summary.get("plugin_invocations_by_name", {}), limit=10)
        if skills:
            lines.extend(["", "## Skills"])
            lines.extend(f"- `{name}`: {count}" for name, count in skills)
        if plugins:
            lines.extend(["", "## Plugins"])
            lines.extend(f"- `{name}`: {count}" for name, count in plugins)

    return "\n".join(lines)


def build_portfolio_markdown(entries: Iterable[Dict[str, Any]]) -> str:
    """Render a multi-session markdown overview."""
    entries = list(entries)
    lines = [
        "# Session Portfolio",
        "",
        f"Imported sessions: {len(entries)}",
    ]
    if not entries:
        lines.extend(["", "No imported sessions found."])
        return "\n".join(lines)

    lines.extend(
        [
            "",
            "| Session | Tools | Read | Edited | Tokens | Cost | Duration | Failures |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for entry in entries:
        summary = entry["summary"]
        metadata = entry.get("metadata") or {}
        failures = sum(
            int(v) for v in summary.get("tool_failures_by_name", {}).values()
        )
        lines.append(
            "| {title} | {tools} | {read} | {edited} | {tokens} | {cost} | {duration} | {failures} |".format(
                title=str(
                    metadata.get("display_title") or entry["session_name"]
                ).replace("|", "\\|"),
                tools=summary.get("total_tool_calls", 0),
                read=summary.get("distinct_files_read", 0),
                edited=summary.get("distinct_files_edited", 0),
                tokens=_format_tokens(summary.get("total_tokens", 0)),
                cost=_format_cost_line(summary),
                duration=_format_duration(summary.get("session_duration_seconds", 0)),
                failures=failures,
            )
        )
    return "\n".join(lines)
