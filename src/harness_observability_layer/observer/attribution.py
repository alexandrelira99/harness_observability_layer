"""Deterministic attribution segment derivation for session events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List

from .schemas import (
    AGENT_MESSAGE,
    FILE_EDIT,
    FILE_READ,
    FILE_SEARCH,
    SESSION_FINISHED,
    SKILL_LOADED,
    TASK_FINISHED,
    TOKEN_USAGE,
    TOOL_CALL_FAILED,
    TOOL_CALL_FINISHED,
    USER_MESSAGE,
)


def _parse_ts(ts_str: str | None) -> datetime | None:
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _empty_accumulator() -> Dict[str, Any]:
    return {
        "tool_call_count": 0,
        "tool_failure_count": 0,
        "file_read_count": 0,
        "file_edit_count": 0,
        "file_search_count": 0,
        "input_tokens": 0,
        "cache_read_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "duration_seconds": 0.0,
    }


@dataclass
class AttributionSegment:
    segment_id: str
    driver_type: str
    driver_name: str
    start_ts: str | None
    start_event_index: int
    end_ts: str | None = None
    end_event_index: int = 0
    boundary_reason: str = "open"
    tool_call_count: int = 0
    tool_failure_count: int = 0
    file_read_count: int = 0
    file_edit_count: int = 0
    file_search_count: int = 0
    input_tokens: int = 0
    cache_read_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    duration_seconds: float = 0.0

    def add_event(self, event: Dict[str, Any]) -> None:
        event_type = event.get("event_type")
        payload = event.get("payload") or {}
        if event_type == TOOL_CALL_FINISHED:
            self.tool_call_count += 1
        elif event_type == TOOL_CALL_FAILED:
            self.tool_call_count += 1
            self.tool_failure_count += 1
        elif event_type == FILE_READ:
            self.file_read_count += 1
        elif event_type == FILE_EDIT:
            self.file_edit_count += 1
        elif event_type == FILE_SEARCH:
            self.file_search_count += 1
        elif event_type in {AGENT_MESSAGE, TASK_FINISHED, TOKEN_USAGE}:
            usage = payload.get("usage") or {}
            self.input_tokens += int(usage.get("input_tokens", 0) or 0)
            self.cache_read_tokens += int(
                usage.get("cache_read_input_tokens", 0) or 0
            )
            self.output_tokens += int(usage.get("output_tokens", 0) or 0)
            self.total_tokens += (
                int(usage.get("input_tokens", 0) or 0)
                + int(usage.get("cache_read_input_tokens", 0) or 0)
                + int(usage.get("output_tokens", 0) or 0)
                + int(usage.get("cache_creation_input_tokens", 0) or 0)
            )

    def close(
        self, *, end_ts: str | None, end_event_index: int, boundary_reason: str
    ) -> None:
        self.end_ts = end_ts
        self.end_event_index = end_event_index
        self.boundary_reason = boundary_reason
        start_dt = _parse_ts(self.start_ts)
        end_dt = _parse_ts(end_ts)
        if start_dt and end_dt:
            self.duration_seconds = round(
                max(0.0, (end_dt - start_dt).total_seconds()), 3
            )

    def has_activity(self) -> bool:
        return any(
            [
                self.tool_call_count,
                self.tool_failure_count,
                self.file_read_count,
                self.file_edit_count,
                self.file_search_count,
                self.input_tokens,
                self.cache_read_tokens,
                self.output_tokens,
                self.total_tokens,
                self.duration_seconds > 0,
            ]
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "driver_type": self.driver_type,
            "driver_name": self.driver_name,
            "start_ts": self.start_ts,
            "end_ts": self.end_ts,
            "start_event_index": self.start_event_index,
            "end_event_index": self.end_event_index,
            "boundary_reason": self.boundary_reason,
            "tool_call_count": self.tool_call_count,
            "tool_failure_count": self.tool_failure_count,
            "file_read_count": self.file_read_count,
            "file_edit_count": self.file_edit_count,
            "file_search_count": self.file_search_count,
            "input_tokens": self.input_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "duration_seconds": self.duration_seconds,
        }


BOUNDARY_EVENTS = {SKILL_LOADED, USER_MESSAGE, TASK_FINISHED, SESSION_FINISHED}
ATTRIBUTABLE_EVENTS = {
    TOOL_CALL_FINISHED,
    TOOL_CALL_FAILED,
    FILE_READ,
    FILE_EDIT,
    FILE_SEARCH,
    AGENT_MESSAGE,
    TOKEN_USAGE,
    TASK_FINISHED,
}


def derive_attribution_segments(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    segments: List[AttributionSegment] = []
    current: AttributionSegment | None = None
    segment_counter = 0

    def open_segment(
        *, driver_type: str, driver_name: str, ts: str | None, event_index: int
    ) -> AttributionSegment:
        nonlocal segment_counter
        segment_counter += 1
        return AttributionSegment(
            segment_id=f"segment_{segment_counter}",
            driver_type=driver_type,
            driver_name=driver_name,
            start_ts=ts,
            start_event_index=event_index,
        )

    def close_current(event: Dict[str, Any], event_index: int, reason: str) -> None:
        nonlocal current
        if current is None:
            return
        current.close(
            end_ts=event.get("ts"),
            end_event_index=event_index,
            boundary_reason=reason,
        )
        if current.has_activity():
            segments.append(current)
        current = None

    for index, event in enumerate(events):
        event_type = event.get("event_type")
        payload = event.get("payload") or {}

        if event_type == SKILL_LOADED:
            close_current(event, index, "next_skill_loaded")
            current = open_segment(
                driver_type="skill",
                driver_name=str(payload.get("skill_name") or "unknown"),
                ts=event.get("ts"),
                event_index=index,
            )
            continue

        if event_type == USER_MESSAGE:
            close_current(event, index, "user_message")
            current = open_segment(
                driver_type="unattributed",
                driver_name="unattributed",
                ts=event.get("ts"),
                event_index=index,
            )
            continue

        if event_type in ATTRIBUTABLE_EVENTS:
            if current is None:
                current = open_segment(
                    driver_type="unattributed",
                    driver_name="unattributed",
                    ts=event.get("ts"),
                    event_index=index,
                )
            current.add_event(event)
            if event_type in {TASK_FINISHED, SESSION_FINISHED}:
                close_current(event, index, f"{event_type}_boundary")
            continue

        if event_type == SESSION_FINISHED:
            close_current(event, index, "session_finished")

    if current is not None:
        current.close(
            end_ts=current.start_ts,
            end_event_index=current.start_event_index,
            boundary_reason="end_of_stream",
        )
        if current.has_activity():
            segments.append(current)

    return [segment.to_dict() for segment in segments]


def aggregate_skill_attribution(
    segments: List[Dict[str, Any]]
) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    for segment in segments:
        if segment.get("driver_type") != "skill":
            continue
        name = str(segment.get("driver_name") or "unknown")
        bucket = result.setdefault(name, {"segments_count": 0, **_empty_accumulator()})
        bucket["segments_count"] += 1
        for key in _empty_accumulator():
            bucket[key] += segment.get(key, 0) or 0
    return result


def aggregate_unattributed_activity(segments: List[Dict[str, Any]]) -> Dict[str, Any]:
    result = _empty_accumulator()
    for segment in segments:
        if segment.get("driver_type") != "unattributed":
            continue
        for key in result:
            result[key] += segment.get(key, 0) or 0
    return result


def compute_attribution_shares(
    *,
    skill_attribution: Dict[str, Dict[str, Any]],
    unattributed_activity: Dict[str, Any],
    total_tool_calls: int,
    total_tokens: int,
    distinct_files_edited: int,
    session_duration_seconds: float,
) -> Dict[str, float]:
    skill_tool_calls = sum(
        int(bucket.get("tool_call_count", 0) or 0)
        for bucket in skill_attribution.values()
    )
    skill_tokens = sum(
        int(bucket.get("total_tokens", 0) or 0) for bucket in skill_attribution.values()
    )
    skill_edits = sum(
        int(bucket.get("file_edit_count", 0) or 0)
        for bucket in skill_attribution.values()
    )
    skill_duration = sum(
        float(bucket.get("duration_seconds", 0) or 0)
        for bucket in skill_attribution.values()
    )
    return {
        "skill_attributed_tool_call_pct": round(
            (skill_tool_calls / total_tool_calls) * 100, 2
        )
        if total_tool_calls
        else 0.0,
        "skill_attributed_token_pct": round((skill_tokens / total_tokens) * 100, 2)
        if total_tokens
        else 0.0,
        "skill_attributed_file_edit_pct": round(
            (skill_edits / distinct_files_edited) * 100, 2
        )
        if distinct_files_edited
        else 0.0,
        "skill_attributed_duration_pct": round(
            (skill_duration / session_duration_seconds) * 100, 2
        )
        if session_duration_seconds
        else 0.0,
    }
