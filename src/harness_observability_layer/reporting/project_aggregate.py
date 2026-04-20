"""Project-level aggregation for imported HOL session artifacts."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List

from harness_observability_layer.observer.metrics import PRICING_PER_MILLION_TOKENS

from .session_metadata import derive_session_metadata


def _parse_ts(ts_str: str | None) -> datetime | None:
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
    except ValueError:
        return None


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _event_usage(event: Dict[str, Any]) -> Dict[str, int]:
    usage = (event.get("payload") or {}).get("usage") or {}
    return {
        "input_tokens": _safe_int(usage.get("input_tokens")),
        "output_tokens": _safe_int(usage.get("output_tokens")),
        "cache_creation_input_tokens": _safe_int(
            usage.get("cache_creation_input_tokens")
        ),
        "cache_read_input_tokens": _safe_int(usage.get("cache_read_input_tokens")),
    }


def _usage_total(usage: Dict[str, int]) -> int:
    return (
        usage["input_tokens"]
        + usage["output_tokens"]
        + usage["cache_creation_input_tokens"]
        + usage["cache_read_input_tokens"]
    )


def _estimate_cost_from_usage(usage: Dict[str, int], model: str | None) -> float:
    pricing = PRICING_PER_MILLION_TOKENS.get(model or "")
    if not pricing:
        return 0.0
    return round(
        (usage["input_tokens"] / 1_000_000) * pricing["input"]
        + (usage["output_tokens"] / 1_000_000) * pricing["output"]
        + (usage["cache_creation_input_tokens"] / 1_000_000) * pricing["cache_write"]
        + (usage["cache_read_input_tokens"] / 1_000_000) * pricing["cache_read"],
        6,
    )


def _prompt_hash(text: str) -> str:
    normalized = " ".join(str(text or "").split()).strip().lower()
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12]


def _excerpt(text: str, limit: int = 24) -> str:
    words = str(text or "").split()
    short = " ".join(words[:limit])
    if len(words) > limit:
        short += "..."
    return short


def _load_json(path: Path) -> Dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _group_driver_label(skill_counts: Counter[str]) -> tuple[str, str]:
    if not skill_counts:
        return "unattributed", "unattributed"
    skill_name, _count = sorted(skill_counts.items(), key=lambda item: (-item[1], item[0]))[
        0
    ]
    return "skill", skill_name


def group_events_into_prompt_turns(
    *,
    events: List[Dict[str, Any]],
    session_name: str,
    summary: Dict[str, Any],
    metadata: Dict[str, Any],
) -> Dict[str, List[Dict[str, Any]]]:
    """Build prompt-group and turn-level aggregates from normalized events."""
    prompt_groups: List[Dict[str, Any]] = []
    turns: List[Dict[str, Any]] = []

    current_model = str(summary.get("model") or metadata.get("model") or "")
    current_turn: Dict[str, Any] | None = None
    current_prompt_group: Dict[str, Any] | None = None
    current_prompt_skill_counts: Counter[str] = Counter()
    active_skill_name: str | None = None
    prompt_index = 0
    turn_index = 0
    global_tools_seen = 0

    def _new_bucket(kind: str, ordinal: int, prompt_text: str | None = None) -> Dict[str, Any]:
        return {
            "kind": kind,
            "session_name": session_name,
            "session_title": metadata.get("display_title") or session_name,
            "session_subtitle": metadata.get("display_subtitle") or session_name,
            "source_name": metadata.get("source_name") or "Imported",
            "model": current_model or str(summary.get("model") or ""),
            "start_ts": None,
            "end_ts": None,
            "duration_seconds": 0.0,
            "ordinal": ordinal,
            "prompt": prompt_text or "",
            "prompt_excerpt": _excerpt(prompt_text or "", limit=18),
            "prompt_hash": _prompt_hash(prompt_text or "") if prompt_text else None,
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
            "total_tokens": 0,
            "estimated_cost_usd": 0.0,
            "tool_call_count": 0,
            "tool_failure_count": 0,
            "tool_counts": {},
            "continuation_like_events": 0,
            "max_tokens_stops": 0,
            "driver_type": "unattributed",
            "driver_name": "unattributed",
            "saw_tool_activity": False,
            "saw_file_activity": False,
            "turn_count": 0,
            "global_tool_start_count": global_tools_seen,
        }

    def _stamp(bucket: Dict[str, Any], ts: str | None) -> None:
        if not ts:
            return
        if not bucket["start_ts"]:
            bucket["start_ts"] = ts
        bucket["end_ts"] = ts

    def _add_usage(bucket: Dict[str, Any], usage: Dict[str, int]) -> None:
        bucket["input_tokens"] += usage["input_tokens"]
        bucket["output_tokens"] += usage["output_tokens"]
        bucket["cache_creation_input_tokens"] += usage["cache_creation_input_tokens"]
        bucket["cache_read_input_tokens"] += usage["cache_read_input_tokens"]
        bucket["total_tokens"] += _usage_total(usage)
        bucket["estimated_cost_usd"] = round(
            bucket["estimated_cost_usd"]
            + _estimate_cost_from_usage(usage, bucket.get("model") or current_model),
            6,
        )

    def _close_bucket(bucket: Dict[str, Any] | None, *, turn_count_increment: bool = False) -> Dict[str, Any] | None:
        if bucket is None:
            return None
        start_dt = _parse_ts(bucket.get("start_ts"))
        end_dt = _parse_ts(bucket.get("end_ts"))
        if start_dt and end_dt:
            bucket["duration_seconds"] = round(
                max(0.0, (end_dt - start_dt).total_seconds()), 3
            )
        if turn_count_increment:
            bucket["turn_count"] += 1
        return bucket

    for event in events:
        event_type = event.get("event_type")
        payload = event.get("payload") or {}
        ts = event.get("ts")

        if event_type == "task_started":
            if current_turn is not None:
                turns.append(_close_bucket(current_turn) or current_turn)
            turn_index += 1
            current_turn = _new_bucket("turn", turn_index, current_prompt_group["prompt"] if current_prompt_group else None)
            _stamp(current_turn, ts)
            continue

        if event_type == "user_message":
            if current_prompt_group is not None:
                driver_type, driver_name = _group_driver_label(current_prompt_skill_counts)
                current_prompt_group["driver_type"] = driver_type
                current_prompt_group["driver_name"] = driver_name
                prompt_groups.append(_close_bucket(current_prompt_group) or current_prompt_group)
            prompt_index += 1
            current_prompt_group = _new_bucket(
                "prompt_group",
                prompt_index,
                str(payload.get("message") or ""),
            )
            current_prompt_skill_counts = Counter()
            active_skill_name = None
            _stamp(current_prompt_group, ts)
            continue

        if event_type == "skill_loaded":
            active_skill_name = str(payload.get("skill_name") or "unknown")
            if current_prompt_group is not None:
                current_prompt_skill_counts[active_skill_name] += 1
                _stamp(current_prompt_group, ts)
            if current_turn is not None:
                _stamp(current_turn, ts)
            continue

        if event_type in {"agent_message", "token_usage", "task_finished"}:
            usage = _event_usage(event)
            if any(usage.values()):
                if current_prompt_group is None:
                    prompt_index += 1
                    current_prompt_group = _new_bucket("prompt_group", prompt_index, "")
                if current_turn is None:
                    turn_index += 1
                    current_turn = _new_bucket("turn", turn_index, current_prompt_group.get("prompt"))
                _stamp(current_prompt_group, ts)
                _stamp(current_turn, ts)
                _add_usage(current_prompt_group, usage)
                _add_usage(current_turn, usage)
            stop_reason = str(payload.get("stop_reason") or "")
            if stop_reason == "max_tokens":
                if current_prompt_group is not None:
                    current_prompt_group["max_tokens_stops"] += 1
                if current_turn is not None:
                    current_turn["max_tokens_stops"] += 1
            if event_type == "task_finished" and current_turn is not None:
                turns.append(_close_bucket(current_turn) or current_turn)
                current_turn = None
            continue

        if event_type in {"tool_call_started", "tool_call_finished", "tool_call_failed"}:
            if current_prompt_group is None:
                prompt_index += 1
                current_prompt_group = _new_bucket("prompt_group", prompt_index, "")
            if current_turn is None:
                turn_index += 1
                current_turn = _new_bucket("turn", turn_index, current_prompt_group.get("prompt"))
            _stamp(current_prompt_group, ts)
            _stamp(current_turn, ts)
            tool_name = str(payload.get("tool_name") or "unknown")
            if event_type == "tool_call_started":
                global_tools_seen += 1
            if event_type in {"tool_call_finished", "tool_call_failed"}:
                current_prompt_group["tool_call_count"] += 1
                current_turn["tool_call_count"] += 1
                prompt_tools = Counter(current_prompt_group["tool_counts"])
                turn_tools = Counter(current_turn["tool_counts"])
                prompt_tools[tool_name] += 1
                turn_tools[tool_name] += 1
                current_prompt_group["tool_counts"] = dict(prompt_tools)
                current_turn["tool_counts"] = dict(turn_tools)
            if event_type == "tool_call_failed":
                current_prompt_group["tool_failure_count"] += 1
                current_turn["tool_failure_count"] += 1
            current_prompt_group["saw_tool_activity"] = True
            current_turn["saw_tool_activity"] = True
            if active_skill_name:
                current_prompt_skill_counts[active_skill_name] += 1
                current_prompt_group["driver_type"] = "skill"
                current_prompt_group["driver_name"] = active_skill_name
                current_turn["driver_type"] = "skill"
                current_turn["driver_name"] = active_skill_name
            continue

        if event_type in {"file_read", "file_edit", "file_search"}:
            if current_prompt_group is None:
                continue
            _stamp(current_prompt_group, ts)
            if current_turn is not None:
                _stamp(current_turn, ts)
            current_prompt_group["saw_file_activity"] = True
            if current_turn is not None:
                current_turn["saw_file_activity"] = True
            if active_skill_name:
                current_prompt_skill_counts[active_skill_name] += 1
            continue

        if event_type == "session_finished":
            if current_turn is not None:
                turns.append(_close_bucket(current_turn) or current_turn)
                current_turn = None

    if current_turn is not None:
        turns.append(_close_bucket(current_turn) or current_turn)
    if current_prompt_group is not None:
        driver_type, driver_name = _group_driver_label(current_prompt_skill_counts)
        current_prompt_group["driver_type"] = driver_type
        current_prompt_group["driver_name"] = driver_name
        prompt_groups.append(_close_bucket(current_prompt_group) or current_prompt_group)

    for prompt_group in prompt_groups:
        prompt_group["turn_count"] = len(
            [turn for turn in turns if turn["session_name"] == prompt_group["session_name"]]
        )
        if (
            prompt_group["tool_call_count"] == 0
            and prompt_group["input_tokens"] > 0
            and prompt_group["global_tool_start_count"] == 0
        ):
            prompt_group["continuation_like_events"] += 1

    return {"prompt_groups": prompt_groups, "turns": turns}


def _session_attention_score(summary: Dict[str, Any]) -> float:
    return round(
        _safe_float(summary.get("estimated_cost_usd"))
        + (_safe_float(summary.get("failure_rate_pct")) / 20)
        + (_safe_float(summary.get("continuation_loops")) * 0.25)
        + (_safe_float(summary.get("max_tokens_stops")) * 0.25),
        4,
    )


def _empty_aggregate() -> Dict[str, Any]:
    return {
        "totals": {
            "sessions": 0,
            "prompt_groups": 0,
            "turns": 0,
            "total_tokens": 0,
            "estimated_cost_usd": 0.0,
            "total_cache_read_tokens": 0,
            "total_cache_write_tokens": 0,
        },
        "date_range": None,
        "model_breakdown": [],
        "session_rankings": [],
        "top_prompt_groups": [],
        "top_turns": [],
        "insights": [],
        "trends": {"daily": [], "weekly": []},
        "sessions": [],
    }


def build_project_aggregate_from_sessions(
    session_entries: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build a project-wide summary from in-memory session entries."""
    if not session_entries:
        return _empty_aggregate()

    sessions: List[Dict[str, Any]] = []
    all_prompt_groups: List[Dict[str, Any]] = []
    all_turns: List[Dict[str, Any]] = []
    daily: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"date": "", "sessions": 0, "tokens": 0, "cost": 0.0}
    )
    model_breakdown: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"model": "", "sessions": 0, "tokens": 0, "cost": 0.0, "tool_calls": 0}
    )

    for session_entry in session_entries:
        session_name = str(session_entry.get("session_name") or "unknown-session")
        summary = session_entry.get("summary") or {}
        metadata = session_entry.get("metadata") or {}
        events = session_entry.get("events") or []
        grouped = session_entry.get("grouped")
        if not grouped:
            grouped = group_events_into_prompt_turns(
                events=events,
                session_name=session_name,
                summary=summary,
                metadata=metadata,
            )
        prompt_groups = grouped["prompt_groups"]
        turns = grouped["turns"]
        all_prompt_groups.extend(prompt_groups)
        all_turns.extend(turns)

        session_date = None
        started_at = str(metadata.get("started_at") or "")
        if started_at:
            session_date = started_at.split(" ")[0]
        elif events:
            first_ts = str(events[0].get("ts") or "")
            session_date = first_ts.split("T")[0] if first_ts else None
        if session_date:
            day = daily[session_date]
            day["date"] = session_date
            day["sessions"] += 1
            day["tokens"] += _safe_int(summary.get("total_tokens"))
            day["cost"] = round(
                day["cost"] + _safe_float(summary.get("estimated_cost_usd")), 4
            )

        model_name = str(summary.get("model") or "unknown")
        model_bucket = model_breakdown[model_name]
        model_bucket["model"] = model_name
        model_bucket["sessions"] += 1
        model_bucket["tokens"] += _safe_int(summary.get("total_tokens"))
        model_bucket["cost"] = round(
            model_bucket["cost"] + _safe_float(summary.get("estimated_cost_usd")), 4
        )
        model_bucket["tool_calls"] += _safe_int(summary.get("total_tool_calls"))

        sessions.append(
            {
                "session_name": session_name,
                "summary": summary,
                "metadata": metadata,
                "events": events,
                "prompt_groups": prompt_groups,
                "turns": turns,
                "guided_report_relpath": str(session_entry.get("guided_report_relpath") or ""),
                "attention_score": _session_attention_score(summary),
            }
        )

    sessions.sort(
        key=lambda item: (
            -_safe_float(item["summary"].get("estimated_cost_usd")),
            -_safe_int(item["summary"].get("total_tokens")),
            item["session_name"],
        )
    )

    top_prompt_groups = sorted(
        all_prompt_groups,
        key=lambda item: (
            -_safe_float(item.get("estimated_cost_usd")),
            -_safe_int(item.get("total_tokens")),
            item.get("session_name", ""),
            item.get("ordinal", 0),
        ),
    )[:25]
    top_turns = sorted(
        all_turns,
        key=lambda item: (
            -_safe_float(item.get("estimated_cost_usd")),
            -_safe_int(item.get("total_tokens")),
            item.get("session_name", ""),
            item.get("ordinal", 0),
        ),
    )[:25]

    date_keys = sorted(daily)
    date_range = {"from": date_keys[0], "to": date_keys[-1]} if date_keys else None
    total_tokens = sum(_safe_int(item["summary"].get("total_tokens")) for item in sessions)
    total_cost = round(
        sum(_safe_float(item["summary"].get("estimated_cost_usd")) for item in sessions),
        4,
    )
    total_cache_read = sum(
        _safe_int(item["summary"].get("total_cache_read_tokens")) for item in sessions
    )
    total_cache_write = sum(
        _safe_int(item["summary"].get("total_cache_creation_tokens")) for item in sessions
    )

    return {
        "totals": {
            "sessions": len(sessions),
            "prompt_groups": len(all_prompt_groups),
            "turns": len(all_turns),
            "total_tokens": total_tokens,
            "estimated_cost_usd": total_cost,
            "total_cache_read_tokens": total_cache_read,
            "total_cache_write_tokens": total_cache_write,
        },
        "date_range": date_range,
        "model_breakdown": sorted(
            model_breakdown.values(),
            key=lambda item: (-item["cost"], -item["tokens"], item["model"]),
        ),
        "session_rankings": [
            {
                "session_name": item["session_name"],
                "display_title": item["metadata"].get("display_title") or item["session_name"],
                "display_subtitle": item["metadata"].get("display_subtitle")
                or item["session_name"],
                "source_name": item["metadata"].get("source_name") or "Imported",
                "prompt_excerpt": item["metadata"].get("prompt_excerpt"),
                "estimated_cost_usd": _safe_float(item["summary"].get("estimated_cost_usd")),
                "total_tokens": _safe_int(item["summary"].get("total_tokens")),
                "total_tool_calls": _safe_int(item["summary"].get("total_tool_calls")),
                "failure_rate_pct": _safe_float(item["summary"].get("failure_rate_pct")),
                "continuation_loops": _safe_int(item["summary"].get("continuation_loops")),
                "max_tokens_stops": _safe_int(item["summary"].get("max_tokens_stops")),
                "guided_report_relpath": item["guided_report_relpath"],
                "attention_score": item["attention_score"],
            }
            for item in sorted(
                sessions,
                key=lambda item: (-item["attention_score"], item["session_name"]),
            )
        ],
        "top_prompt_groups": top_prompt_groups,
        "top_turns": top_turns,
        "trends": {
            "daily": [daily[key] for key in date_keys],
            "weekly": [],
        },
        "sessions": sessions,
    }


def build_project_aggregate(project_root: str | Path) -> Dict[str, Any]:
    """Build a project-wide summary from imported session artifacts."""
    root = Path(project_root)
    sessions_root = root / "hol-artifacts" / "sessions"
    if not sessions_root.exists():
        return _empty_aggregate()

    session_entries: List[Dict[str, Any]] = []

    for session_dir in sorted(
        [path for path in sessions_root.iterdir() if path.is_dir()],
        key=lambda p: p.name,
        reverse=True,
    ):
        summary = _load_json(session_dir / "summary.json")
        if not summary:
            continue
        metadata = _load_json(session_dir / "metadata.json") or {}
        events_path = session_dir / "normalized.events.jsonl"
        events: List[Dict[str, Any]] = []
        if events_path.exists():
            try:
                events = [
                    json.loads(line)
                    for line in events_path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
            except json.JSONDecodeError:
                events = []
        if not metadata:
            metadata = derive_session_metadata(
                session_dir.name, events, include_prompt_excerpt=True
            )
        session_entries.append(
            {
                "session_name": session_dir.name,
                "summary": summary,
                "metadata": metadata,
                "events": events,
                "guided_report_relpath": f"./../sessions/{session_dir.name}/index.html",
            }
        )

    return build_project_aggregate_from_sessions(session_entries)
