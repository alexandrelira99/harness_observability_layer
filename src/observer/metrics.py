"""Derived metrics for event streams."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from .schemas import FILE_EDIT, FILE_READ, PLUGIN_INVOKED, SKILL_LOADED, TOOL_CALL_FAILED, TOOL_CALL_FINISHED


def merge_spans(spans: Iterable[Tuple[int, int]]) -> List[Tuple[int, int]]:
    """Merge overlapping line spans."""
    ordered = sorted((start, end) for start, end in spans if start > 0 and end >= start)
    if not ordered:
        return []

    merged: List[Tuple[int, int]] = [ordered[0]]
    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end + 1:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def span_line_count(spans: Iterable[Tuple[int, int]]) -> int:
    """Return the number of lines covered by merged spans."""
    return sum((end - start + 1) for start, end in spans)


def compute_metrics(events: List[Dict[str, Any]], *, resolve_file_stats: bool = True) -> Dict[str, Any]:
    """Compute a compact metrics summary from canonical events."""
    tool_counts: Counter[str] = Counter()
    tool_failures: Counter[str] = Counter()
    distinct_files_read = set()
    distinct_files_edited = set()
    file_read_spans: Dict[str, List[Tuple[int, int]]] = defaultdict(list)
    file_edit_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {"edit_count": 0, "added_lines": 0, "removed_lines": 0})
    skill_counts: Counter[str] = Counter()
    plugin_counts: Counter[str] = Counter()

    for event in events:
        event_type = event.get("event_type")
        payload = event.get("payload", {})

        if event_type == TOOL_CALL_FINISHED:
            tool_name = payload.get("tool_name", "unknown")
            tool_counts[tool_name] += 1
        elif event_type == TOOL_CALL_FAILED:
            tool_name = payload.get("tool_name", "unknown")
            tool_failures[tool_name] += 1
        elif event_type == FILE_READ:
            path = payload.get("path")
            if path:
                distinct_files_read.add(path)
                file_read_spans[path].append((int(payload.get("line_start", 0)), int(payload.get("line_end", 0))))
        elif event_type == FILE_EDIT:
            path = payload.get("path")
            if path:
                distinct_files_edited.add(path)
                file_edit_stats[path]["edit_count"] += 1
                file_edit_stats[path]["added_lines"] += int(payload.get("added_lines", 0))
                file_edit_stats[path]["removed_lines"] += int(payload.get("removed_lines", 0))
        elif event_type == SKILL_LOADED:
            skill_name = payload.get("skill_name", "unknown")
            skill_counts[skill_name] += 1
        elif event_type == PLUGIN_INVOKED:
            plugin_name = payload.get("plugin_name", "unknown")
            plugin_counts[plugin_name] += 1

    file_summary: Dict[str, Dict[str, Any]] = {}
    for path, spans in file_read_spans.items():
        merged = merge_spans(spans)
        total_lines = None
        total_lines_status = "unresolved"
        file_path = Path(path)
        if resolve_file_stats:
            try:
                if file_path.exists() and file_path.is_file():
                    total_lines = len(file_path.read_text(encoding="utf-8").splitlines())
                    total_lines_status = "resolved"
            except (OSError, UnicodeDecodeError):
                total_lines = None
                total_lines_status = "unresolved"
        else:
            total_lines_status = "disabled"
        read_line_count = span_line_count(merged)
        if total_lines is not None:
            read_line_count = min(read_line_count, total_lines)
        coverage_pct = round((read_line_count / total_lines) * 100, 2) if total_lines else None
        file_summary[path] = {
            "merged_read_spans": merged,
            "union_lines_read": read_line_count,
            "total_lines": total_lines,
            "total_lines_status": total_lines_status,
            "read_coverage_pct": coverage_pct,
            "edited": path in distinct_files_edited,
            "edit_count": file_edit_stats[path]["edit_count"],
            "added_lines": file_edit_stats[path]["added_lines"],
            "removed_lines": file_edit_stats[path]["removed_lines"],
        }

    edited_without_prior_read = sorted(path for path in distinct_files_edited if path not in distinct_files_read)

    return {
        "total_events": len(events),
        "total_tool_calls": sum(tool_counts.values()),
        "tool_calls_by_name": dict(tool_counts),
        "tool_failures_by_name": dict(tool_failures),
        "distinct_files_read": len(distinct_files_read),
        "distinct_files_edited": len(distinct_files_edited),
        "edited_without_prior_read": edited_without_prior_read,
        "skill_loads_by_name": dict(skill_counts),
        "plugin_invocations_by_name": dict(plugin_counts),
        "file_stats_resolution": "enabled" if resolve_file_stats else "disabled",
        "files": file_summary,
    }
