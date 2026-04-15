"""Markdown reporting for observability sessions."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from harness_observability_layer.security import redact_path


def _top_items(values: Dict[str, Any], limit: int = 5) -> List[tuple[str, int]]:
    return sorted(
        ((str(name), int(count)) for name, count in values.items()),
        key=lambda item: (-item[1], item[0]),
    )[:limit]


def _top_files(files: Dict[str, Dict[str, Any]], limit: int = 5) -> List[tuple[str, Dict[str, Any]]]:
    return sorted(
        files.items(),
        key=lambda item: (
            -(item[1].get("read_coverage_pct") or 0),
            -(item[1].get("edit_count") or 0),
            item[0],
        ),
    )[:limit]


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
        f"- Tool calls: {summary.get('total_tool_calls', 0)}",
        f"- Files read: {summary.get('distinct_files_read', 0)}",
        f"- Files edited: {summary.get('distinct_files_edited', 0)}",
        f"- Failures: {failures}",
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
    if edited_without_read:
        lines.extend(["", "## Warnings"])
        lines.extend(f"- Edited without prior read: `{path}`" for path in edited_without_read[:8])

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

    lines.extend(["", "| Session | Tools | Read | Edited | Failures |", "| --- | ---: | ---: | ---: | ---: |"])
    for entry in entries:
        summary = entry["summary"]
        metadata = entry.get("metadata") or {}
        failures = sum(int(v) for v in summary.get("tool_failures_by_name", {}).values())
        lines.append(
            "| {title} | {tools} | {read} | {edited} | {failures} |".format(
                title=str(metadata.get("display_title") or entry["session_name"]).replace("|", "\\|"),
                tools=summary.get("total_tool_calls", 0),
                read=summary.get("distinct_files_read", 0),
                edited=summary.get("distinct_files_edited", 0),
                failures=failures,
            )
        )
    return "\n".join(lines)
