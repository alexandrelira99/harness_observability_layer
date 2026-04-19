"""Derived metrics for event streams."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from .attribution import (
    aggregate_skill_attribution,
    aggregate_unattributed_activity,
    compute_attribution_shares,
    derive_attribution_segments,
)
from .schemas import (
    AGENT_MESSAGE,
    FILE_EDIT,
    FILE_READ,
    FILE_SEARCH,
    PLUGIN_INVOKED,
    SESSION_FINISHED,
    SESSION_STARTED,
    SKILL_LOADED,
    TASK_FINISHED,
    TASK_STARTED,
    TOKEN_USAGE,
    TOOL_CALL_FAILED,
    TOOL_CALL_FINISHED,
    TOOL_CALL_STARTED,
    USER_MESSAGE,
)

PRICING_PER_MILLION_TOKENS = {
    "claude-sonnet-4-20250514": {
        "input": 3.0,
        "output": 15.0,
        "cache_write": 3.75,
        "cache_read": 0.30,
    },
    "claude-opus-4-20250514": {
        "input": 15.0,
        "output": 75.0,
        "cache_write": 18.75,
        "cache_read": 1.50,
    },
    "claude-haiku-3-20250414": {
        "input": 0.80,
        "output": 4.0,
        "cache_write": 1.00,
        "cache_read": 0.08,
    },
    "gpt-5.4": {
        "input": 2.50,
        "output": 15.0,
        "cache_write": 0.0,
        "cache_read": 0.25,
    },
    "gpt-5.2": {
        "input": 1.75,
        "output": 14.0,
        "cache_write": 0.0,
        "cache_read": 0.175,
    },
    "gpt-5.1": {
        "input": 1.25,
        "output": 10.0,
        "cache_write": 0.0,
        "cache_read": 0.125,
    },
    "gpt-5": {
        "input": 1.25,
        "output": 10.0,
        "cache_write": 0.0,
        "cache_read": 0.125,
    },
    "gpt-4o": {
        "input": 2.50,
        "output": 10.0,
        "cache_write": 0.0,
        "cache_read": 1.25,
    },
    "gpt-4.1": {
        "input": 2.00,
        "output": 8.0,
        "cache_write": 0.0,
        "cache_read": 0.50,
    },
    "gpt-4.1-mini": {
        "input": 0.40,
        "output": 1.6,
        "cache_write": 0.0,
        "cache_read": 0.10,
    },
    "o4-mini": {
        "input": 4.00,
        "output": 16.0,
        "cache_write": 0.0,
        "cache_read": 1.00,
    },
}


def _estimate_cost(token_totals: Dict[str, int], model: str | None) -> float | None:
    pricing = PRICING_PER_MILLION_TOKENS.get(model) if model else None
    if not pricing:
        return None
    input_cost = (token_totals["total_input_tokens"] / 1_000_000) * pricing["input"]
    output_cost = (token_totals["total_output_tokens"] / 1_000_000) * pricing["output"]
    cache_write_cost = (
        token_totals["total_cache_creation_tokens"] / 1_000_000
    ) * pricing["cache_write"]
    cache_read_cost = (token_totals["total_cache_read_tokens"] / 1_000_000) * pricing[
        "cache_read"
    ]
    return round(input_cost + output_cost + cache_write_cost + cache_read_cost, 4)


def _parse_ts(ts_str: str | None) -> datetime | None:
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _categorize_bash_command(cmd: str) -> str:
    if not cmd:
        return "unknown"
    cmd_stripped = cmd.strip()
    lowered = cmd_stripped.lower()
    prefixes = [
        ("git ", "git"),
        ("git", "git"),
        ("pytest", "test"),
        ("python -m pytest", "test"),
        ("npm test", "test"),
        ("yarn test", "test"),
        ("go test", "test"),
        ("cargo test", "test"),
        ("npm run lint", "lint"),
        ("yarn lint", "lint"),
        ("ruff", "lint"),
        ("flake8", "lint"),
        ("eslint", "lint"),
        ("mypy", "lint"),
        ("pylint", "lint"),
        ("npm run build", "build"),
        ("yarn build", "build"),
        ("cargo build", "build"),
        ("go build", "build"),
        ("make", "build"),
        ("pip install", "install"),
        ("npm install", "install"),
        ("cargo add", "install"),
        ("go get", "install"),
        ("docker", "docker"),
        ("curl", "network"),
        ("wget", "network"),
        ("ssh", "network"),
        ("ls", "file_ops"),
        ("find", "file_ops"),
        ("mkdir", "file_ops"),
        ("cp ", "file_ops"),
        ("mv ", "file_ops"),
        ("rm ", "file_ops"),
        ("chmod", "file_ops"),
        ("cat ", "file_ops"),
        ("sed ", "file_ops"),
        ("grep", "file_ops"),
        ("rg ", "search"),
        ("ag ", "search"),
    ]
    for prefix, category in prefixes:
        if lowered.startswith(prefix):
            return category
    return "other"


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


def compute_metrics(
    events: List[Dict[str, Any]], *, resolve_file_stats: bool = True
) -> Dict[str, Any]:
    """Compute a compact metrics summary from canonical events."""
    tool_counts: Counter[str] = Counter()
    tool_failures: Counter[str] = Counter()
    distinct_files_read = set()
    distinct_files_edited = set()
    file_read_spans: Dict[str, List[Tuple[int, int]]] = defaultdict(list)
    file_edit_stats: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {"edit_count": 0, "added_lines": 0, "removed_lines": 0}
    )
    skill_counts: Counter[str] = Counter()
    plugin_counts: Counter[str] = Counter()
    total_input_tokens = 0
    total_output_tokens = 0
    total_cache_creation_tokens = 0
    total_cache_read_tokens = 0
    models_used: set[str] = set()
    stop_reasons: Counter[str] = Counter()
    user_message_count = 0
    agent_message_count = 0
    agent_message_total_chars = 0
    call_start_times: Dict[str, datetime] = {}
    tool_durations: Dict[str, List[float]] = defaultdict(list)
    task_start_times: Dict[str, datetime] = {}
    task_durations: Dict[str, float] = {}
    bash_categories: Counter[str] = Counter()
    active_calls = 0
    plan_type: str | None = None
    max_concurrent = 0
    file_read_count: Counter[str] = Counter()
    file_edit_types: Counter[str] = Counter()
    search_events: List[Dict[str, Any]] = []

    for event in events:
        event_type = event.get("event_type")
        payload = event.get("payload", {})

        if event_type == TOOL_CALL_FINISHED:
            tool_name = payload.get("tool_name", "unknown")
            tool_counts[tool_name] += 1
            active_calls = max(0, active_calls - 1)
            call_id = payload.get("call_id")
            ts = _parse_ts(event.get("ts"))
            if call_id and ts and call_id in call_start_times:
                duration = (ts - call_start_times.pop(call_id)).total_seconds()
                tool_durations[tool_name].append(duration)
        elif event_type == TOOL_CALL_FAILED:
            tool_name = payload.get("tool_name", "unknown")
            tool_failures[tool_name] += 1
            active_calls = max(0, active_calls - 1)
            call_id = payload.get("call_id")
            ts = _parse_ts(event.get("ts"))
            if call_id and ts and call_id in call_start_times:
                duration = (ts - call_start_times.pop(call_id)).total_seconds()
                tool_durations[tool_name].append(duration)
        elif event_type == FILE_READ:
            path = payload.get("path")
            if path:
                distinct_files_read.add(path)
                file_read_count[path] += 1
                file_read_spans[path].append(
                    (int(payload.get("line_start", 0)), int(payload.get("line_end", 0)))
                )
        elif event_type == FILE_EDIT:
            path = payload.get("path")
            if path:
                distinct_files_edited.add(path)
                file_edit_types[payload.get("edit_change_type", "update")] += 1
                file_edit_stats[path]["edit_count"] += 1
                file_edit_stats[path]["added_lines"] += int(
                    payload.get("added_lines", 0)
                )
                file_edit_stats[path]["removed_lines"] += int(
                    payload.get("removed_lines", 0)
                )
        elif event_type == SKILL_LOADED:
            skill_name = payload.get("skill_name", "unknown")
            skill_counts[skill_name] += 1
        elif event_type == PLUGIN_INVOKED:
            plugin_name = payload.get("plugin_name", "unknown")
            plugin_counts[plugin_name] += 1
        elif event_type == FILE_SEARCH:
            search_events.append(event)
        elif event_type == AGENT_MESSAGE:
            agent_message_count += 1
            agent_message_total_chars += len(payload.get("message") or "")
            usage = payload.get("usage") or {}
            total_input_tokens += int(usage.get("input_tokens", 0))
            total_output_tokens += int(usage.get("output_tokens", 0))
            total_cache_creation_tokens += int(
                usage.get("cache_creation_input_tokens", 0)
            )
            total_cache_read_tokens += int(usage.get("cache_read_input_tokens", 0))
            model = payload.get("model")
            if model:
                models_used.add(model)
            reason = payload.get("stop_reason")
            if reason:
                stop_reasons[reason] += 1
        elif event_type == TOKEN_USAGE:
            usage = payload.get("usage") or {}
            total_input_tokens += int(usage.get("input_tokens", 0))
            total_output_tokens += int(usage.get("output_tokens", 0))
            total_cache_creation_tokens += int(
                usage.get("cache_creation_input_tokens", 0)
            )
            total_cache_read_tokens += int(usage.get("cache_read_input_tokens", 0))
        elif event_type == TASK_FINISHED:
            usage = payload.get("usage") or {}
            total_input_tokens += int(usage.get("input_tokens", 0))
            total_output_tokens += int(usage.get("output_tokens", 0))
            total_cache_creation_tokens += int(
                usage.get("cache_creation_input_tokens", 0)
            )
            total_cache_read_tokens += int(usage.get("cache_read_input_tokens", 0))
            ts = _parse_ts(event.get("ts"))
            tid = event.get("task_id")
            if ts and tid and tid in task_start_times:
                task_durations[tid] = round(
                    (ts - task_start_times.pop(tid)).total_seconds(), 2
                )
        elif event_type == TOOL_CALL_STARTED:
            active_calls += 1
            max_concurrent = max(max_concurrent, active_calls)
            call_id = payload.get("call_id")
            ts = _parse_ts(event.get("ts"))
            if call_id and ts:
                call_start_times[call_id] = ts
            if payload.get("tool_name") == "Bash":
                cmd = str((payload.get("arguments") or {}).get("command", ""))
                bash_categories[_categorize_bash_command(cmd)] += 1
        elif event_type == TASK_STARTED:
            ts = _parse_ts(event.get("ts"))
            tid = event.get("task_id")
            if ts and tid:
                task_start_times[tid] = ts
        elif event_type == USER_MESSAGE:
            user_message_count += 1
        elif event_type == SESSION_STARTED:
            pt = payload.get("plan_type")
            if pt and plan_type is None:
                plan_type = pt

    file_summary: Dict[str, Dict[str, Any]] = {}
    for path, spans in file_read_spans.items():
        merged = merge_spans(spans)
        total_lines = None
        total_lines_status = "unresolved"
        file_path = Path(path)
        if resolve_file_stats:
            try:
                if file_path.exists() and file_path.is_file():
                    total_lines = len(
                        file_path.read_text(encoding="utf-8").splitlines()
                    )
                    total_lines_status = "resolved"
            except (OSError, UnicodeDecodeError):
                total_lines = None
                total_lines_status = "unresolved"
        else:
            total_lines_status = "disabled"
        read_line_count = span_line_count(merged)
        if total_lines is not None:
            read_line_count = min(read_line_count, total_lines)
        coverage_pct = (
            round((read_line_count / total_lines) * 100, 2) if total_lines else None
        )
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

    edited_without_prior_read = sorted(
        path for path in distinct_files_edited if path not in distinct_files_read
    )
    total_tool_calls = sum(tool_counts.values())
    total_failures = sum(tool_failures.values())
    top_tool_name = None
    top_tool_count = 0
    if tool_counts:
        top_tool_name, top_tool_count = sorted(
            tool_counts.items(), key=lambda item: (-item[1], item[0])
        )[0]
    failure_rate_pct = (
        round((total_failures / total_tool_calls) * 100, 2) if total_tool_calls else 0.0
    )
    skill_load_count = sum(skill_counts.values())
    plugin_invocation_count = sum(plugin_counts.values())

    total_tokens = (
        total_input_tokens
        + total_output_tokens
        + total_cache_creation_tokens
        + total_cache_read_tokens
    )
    model = next(iter(models_used), None)
    token_totals = {
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_cache_creation_tokens": total_cache_creation_tokens,
        "total_cache_read_tokens": total_cache_read_tokens,
    }
    estimated_cost_usd = _estimate_cost(token_totals, model)
    total_input_for_cache = total_input_tokens + total_cache_read_tokens
    cache_hit_rate_pct = (
        round((total_cache_read_tokens / total_input_for_cache) * 100, 2)
        if total_input_for_cache
        else 0.0
    )
    max_tokens_stops = stop_reasons.get("max_tokens", 0)
    continuation_loops = 0
    prev_was_max_tokens = False
    for event in events:
        if event.get("event_type") == AGENT_MESSAGE:
            reason = event.get("payload", {}).get("stop_reason")
            if reason == "max_tokens":
                if prev_was_max_tokens:
                    continuation_loops += 1
                prev_was_max_tokens = True
            else:
                prev_was_max_tokens = False
    turns_per_session = user_message_count
    tool_calls_per_turn = (
        round(total_tool_calls / user_message_count, 2) if user_message_count else 0.0
    )
    tokens_per_turn = (
        round(total_tokens / user_message_count, 0) if user_message_count else 0
    )

    timestamps = [_parse_ts(e.get("ts")) for e in events]
    valid_ts = [t for t in timestamps if t is not None]
    session_duration_seconds = (
        round((valid_ts[-1] - valid_ts[0]).total_seconds(), 2)
        if len(valid_ts) >= 2
        else 0.0
    )

    tool_call_durations_by_name = {k: sorted(v) for k, v in tool_durations.items()}
    avg_tool_duration_by_name = {
        name: round(sum(durs) / len(durs), 3) for name, durs in tool_durations.items()
    }
    total_tool_duration_seconds = round(
        sum(d for ds in tool_durations.values() for d in ds), 2
    )

    tool_failure_rate_by_name: Dict[str, float] = {}
    for tname in set(tool_counts) | set(tool_failures):
        calls = tool_counts.get(tname, 0)
        fails = tool_failures.get(tname, 0)
        total_t = calls + fails
        tool_failure_rate_by_name[tname] = (
            round((fails / total_t) * 100, 2) if total_t else 0.0
        )

    reread_count_by_file = {p: c for p, c in file_read_count.items() if c > 1}
    reread_files = sorted(reread_count_by_file.keys())

    overlapping_read_spans_by_file: Dict[str, int] = {}
    for path, spans in file_read_spans.items():
        if len(spans) <= 1:
            continue
        sorted_spans = sorted(spans)
        overlaps = 0
        for i in range(len(sorted_spans)):
            for j in range(i + 1, len(sorted_spans)):
                _s1, e1 = sorted_spans[i]
                s2, _e2 = sorted_spans[j]
                if s2 <= e1:
                    overlaps += 1
        if overlaps > 0:
            overlapping_read_spans_by_file[path] = overlaps

    file_read_to_edit_ratio: Dict[str, float] = {}
    for path, stats in file_summary.items():
        edits = stats["added_lines"] + stats["removed_lines"]
        if edits > 0:
            ratio = round(stats["union_lines_read"] / edits, 2)
            file_read_to_edit_ratio[path] = ratio

    read_path_set = {
        e.get("payload", {}).get("path")
        for e in events
        if e.get("event_type") == FILE_READ
    }
    searches_with_read = 0
    searches_without_read = 0
    for search_event in search_events:
        sp = search_event.get("payload", {}).get("path")
        if not sp:
            continue
        matched = any(
            rp and (rp.startswith(sp) or sp.startswith(rp)) for rp in read_path_set
        )
        if matched:
            searches_with_read += 1
        else:
            searches_without_read += 1
    total_searches = len(search_events)
    search_to_read_rate = (
        round((searches_with_read / total_searches) * 100, 2) if total_searches else 0.0
    )

    skill_activity: Dict[str, Dict[str, bool]] = {}
    for i, event in enumerate(events):
        if event.get("event_type") != SKILL_LOADED:
            continue
        skill_name = event.get("payload", {}).get("skill_name", "unknown")
        has_tool_activity = False
        has_file_activity = False
        for future_event in events[i + 1 : i + 21]:
            ft = future_event.get("event_type")
            if ft in (TOOL_CALL_STARTED, TOOL_CALL_FINISHED):
                has_tool_activity = True
            if ft in (FILE_READ, FILE_EDIT, FILE_SEARCH):
                has_file_activity = True
        skill_activity[skill_name] = {
            "has_tool_activity": has_tool_activity,
            "has_file_activity": has_file_activity,
        }
    skills_without_followup = sorted(
        name
        for name, activity in skill_activity.items()
        if not activity["has_tool_activity"] and not activity["has_file_activity"]
    )

    read_without_edit = sorted(
        path for path in distinct_files_read if path not in distinct_files_edited
    )

    efficiency_indicators = {
        "edited_without_read_ratio": round(
            len(edited_without_prior_read) / max(len(distinct_files_edited), 1) * 100, 2
        ),
        "reread_ratio": round(
            len(reread_files) / max(len(distinct_files_read), 1) * 100, 2
        ),
        "failure_rate_pct": failure_rate_pct,
        "continuation_loops": continuation_loops,
        "max_tokens_stops": max_tokens_stops,
        "tool_calls_per_minute": round(
            total_tool_calls / max(session_duration_seconds / 60, 0.01), 2
        )
        if session_duration_seconds > 0
        else 0.0,
        "edits_per_minute": round(
            len(distinct_files_edited) / max(session_duration_seconds / 60, 0.01), 2
        )
        if session_duration_seconds > 0
        else 0.0,
    }
    attribution_segments = derive_attribution_segments(events)
    skill_attribution = aggregate_skill_attribution(attribution_segments)
    unattributed_activity = aggregate_unattributed_activity(attribution_segments)
    attribution_shares = compute_attribution_shares(
        skill_attribution=skill_attribution,
        unattributed_activity=unattributed_activity,
        total_tool_calls=total_tool_calls + total_failures,
        total_tokens=total_tokens,
        distinct_files_edited=len(distinct_files_edited),
        session_duration_seconds=session_duration_seconds,
    )

    return {
        "total_events": len(events),
        "total_tool_calls": total_tool_calls,
        "total_failures": total_failures,
        "failure_rate_pct": failure_rate_pct,
        "tool_calls_by_name": dict(tool_counts),
        "tool_failures_by_name": dict(tool_failures),
        "top_tool_name": top_tool_name,
        "top_tool_count": top_tool_count,
        "distinct_files_read": len(distinct_files_read),
        "distinct_files_edited": len(distinct_files_edited),
        "edited_without_prior_read": edited_without_prior_read,
        "edited_without_prior_read_count": len(edited_without_prior_read),
        "skill_load_count": skill_load_count,
        "skill_loads_by_name": dict(skill_counts),
        "distinct_skills_loaded": len(skill_counts),
        "plugin_invocation_count": plugin_invocation_count,
        "plugin_invocations_by_name": dict(plugin_counts),
        "file_stats_resolution": "enabled" if resolve_file_stats else "disabled",
        "files": file_summary,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_cache_creation_tokens": total_cache_creation_tokens,
        "total_cache_read_tokens": total_cache_read_tokens,
        "total_tokens": total_tokens,
        "model": model,
        "models_used": sorted(models_used),
        "plan_type": plan_type,
        "estimated_cost_usd": estimated_cost_usd,
        "cache_hit_rate_pct": cache_hit_rate_pct,
        "stop_reasons": dict(stop_reasons),
        "max_tokens_stops": max_tokens_stops,
        "continuation_loops": continuation_loops,
        "user_message_count": user_message_count,
        "agent_message_count": agent_message_count,
        "agent_message_total_chars": agent_message_total_chars,
        "turns_per_session": turns_per_session,
        "tool_calls_per_turn": tool_calls_per_turn,
        "tokens_per_turn": tokens_per_turn,
        "session_duration_seconds": session_duration_seconds,
        "tool_call_durations_by_name": tool_call_durations_by_name,
        "avg_tool_duration_by_name": avg_tool_duration_by_name,
        "total_tool_duration_seconds": total_tool_duration_seconds,
        "task_durations": task_durations,
        "tool_failure_rate_by_name": tool_failure_rate_by_name,
        "bash_command_categories": dict(bash_categories),
        "max_concurrent_tool_calls": max_concurrent,
        "reread_files": reread_files,
        "reread_count_by_file": reread_count_by_file,
        "reread_file_count": len(reread_files),
        "overlapping_read_spans_by_file": overlapping_read_spans_by_file,
        "file_edit_types": dict(file_edit_types),
        "files_created": file_edit_types.get("add", 0),
        "files_modified": file_edit_types.get("update", 0),
        "files_deleted": file_edit_types.get("delete", 0),
        "file_read_to_edit_ratio": file_read_to_edit_ratio,
        "total_searches": total_searches,
        "searches_with_read": searches_with_read,
        "searches_without_read": searches_without_read,
        "search_to_read_rate": search_to_read_rate,
        "skills_without_followup": skills_without_followup,
        "skills_without_followup_count": len(skills_without_followup),
        "read_without_edit": read_without_edit,
        "read_without_edit_count": len(read_without_edit),
        "efficiency_indicators": efficiency_indicators,
        "skill_attribution": skill_attribution,
        "unattributed_activity": unattributed_activity,
        "attribution_shares": attribution_shares,
        "attribution_segments": attribution_segments,
    }
