"""Normalize Codex session JSONL into canonical observability events."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List

from observer.events import Event
from observer.normalizers import make_file_edit_payload, make_file_read_payload
from observer.schemas import (
    AGENT_MESSAGE,
    FILE_EDIT,
    FILE_READ,
    FILE_SEARCH,
    SESSION_FINISHED,
    SESSION_STARTED,
    TASK_FINISHED,
    TASK_STARTED,
    TOOL_CALL_FAILED,
    TOOL_CALL_FINISHED,
    TOOL_CALL_STARTED,
    USER_MESSAGE,
)


_SED_RANGE_RE = re.compile(r"sed\s+-n\s+'(?P<start>\d+),(?P<end>\d+)p'")


def _task_id_from_payload(payload: Dict[str, Any], session_id: str) -> str:
    return str(payload.get("turn_id") or session_id)


def _timestamp_of(raw: Dict[str, Any]) -> str:
    return str(raw.get("timestamp") or "")


def _parse_line_range(cmd: str) -> tuple[int, int] | None:
    match = _SED_RANGE_RE.search(cmd or "")
    if not match:
        return None
    return int(match.group("start")), int(match.group("end"))


def _count_patch_lines(content: str | None) -> tuple[int, int]:
    if not content:
        return 0, 0
    added_lines = 0
    removed_lines = 0
    for line in content.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            added_lines += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed_lines += 1
    return added_lines, removed_lines


def _parse_apply_patch_input(patch_text: str | None) -> Dict[str, tuple[int, int]]:
    """Estimate added and removed lines per file from an apply_patch input."""
    if not patch_text:
        return {}

    counts: Dict[str, list[int]] = {}
    current_file: str | None = None

    for raw_line in patch_text.splitlines():
        if raw_line.startswith("*** Add File: "):
            current_file = raw_line.removeprefix("*** Add File: ").strip()
            counts[current_file] = [0, 0]
            continue
        if raw_line.startswith("*** Update File: "):
            current_file = raw_line.removeprefix("*** Update File: ").strip()
            counts.setdefault(current_file, [0, 0])
            continue
        if raw_line.startswith("*** Delete File: "):
            current_file = raw_line.removeprefix("*** Delete File: ").strip()
            counts.setdefault(current_file, [0, 0])
            continue
        if raw_line.startswith("***"):
            current_file = None
            continue
        if current_file is None:
            continue
        if raw_line.startswith("+"):
            counts[current_file][0] += 1
        elif raw_line.startswith("-"):
            counts[current_file][1] += 1

    return {path: (added, removed) for path, (added, removed) in counts.items()}


def normalize_codex_records(records: Iterable[Dict[str, Any]]) -> List[Event]:
    """Convert raw Codex JSONL records into canonical events."""
    normalized: List[Event] = []
    call_names: Dict[str, str] = {}
    call_inputs: Dict[str, Any] = {}
    session_id = "unknown_session"
    agent_id = "main"
    current_task_id = "task_1"
    turn_counter = 0

    for raw in records:
        raw_type = raw.get("type")
        payload = raw.get("payload") or {}
        payload_type = payload.get("type")
        timestamp = _timestamp_of(raw)

        if raw_type == "thread.started":
            session_id = str(raw.get("thread_id") or session_id)
            current_task_id = session_id
            normalized.append(
                Event(
                    event_type=SESSION_STARTED,
                    source="codex_jsonl",
                    session_id=session_id,
                    task_id=current_task_id,
                    agent_id=agent_id,
                    ts=timestamp,
                    payload={},
                )
            )
            continue

        if raw_type == "turn.started":
            turn_counter += 1
            current_task_id = f"{session_id}:turn_{turn_counter}"
            normalized.append(
                Event(
                    event_type=TASK_STARTED,
                    source="codex_jsonl",
                    session_id=session_id,
                    task_id=current_task_id,
                    agent_id=agent_id,
                    ts=timestamp,
                    payload={},
                )
            )
            continue

        if raw_type == "item.completed":
            item = raw.get("item") or {}
            item_type = item.get("type")
            if item_type == "agent_message":
                normalized.append(
                    Event(
                        event_type=AGENT_MESSAGE,
                        source="codex_jsonl",
                        session_id=session_id,
                        task_id=current_task_id,
                        agent_id=agent_id,
                        ts=timestamp,
                        payload={"message": item.get("text"), "phase": "final_answer"},
                    )
                )
            continue

        if raw_type == "turn.completed":
            normalized.append(
                Event(
                    event_type=TASK_FINISHED,
                    source="codex_jsonl",
                    session_id=session_id,
                    task_id=current_task_id,
                    agent_id=agent_id,
                    ts=timestamp,
                    payload={"outcome": "completed", "usage": raw.get("usage") or {}},
                )
            )
            continue

        if raw_type == "session_meta":
            session_id = str(payload.get("id") or session_id)
            current_task_id = session_id
            normalized.append(
                Event(
                    event_type=SESSION_STARTED,
                    source="codex_jsonl",
                    session_id=session_id,
                    task_id=session_id,
                    agent_id=agent_id,
                    ts=timestamp,
                    payload={
                        "cwd": payload.get("cwd"),
                        "originator": payload.get("originator"),
                        "cli_version": payload.get("cli_version"),
                        "source": payload.get("source"),
                        "model_provider": payload.get("model_provider"),
                    },
                )
            )
            continue

        task_id = _task_id_from_payload(payload, session_id)

        if raw_type == "response_item" and payload_type in {"function_call", "custom_tool_call"}:
            tool_name = str(payload.get("name") or "unknown")
            call_id = str(payload.get("call_id") or "")
            arguments = payload.get("arguments")
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    arguments = {"raw_arguments": arguments}
            if call_id:
                call_names[call_id] = tool_name
                call_inputs[call_id] = arguments if arguments is not None else payload.get("input")
            normalized.append(
                Event(
                    event_type=TOOL_CALL_STARTED,
                    source="codex_jsonl",
                    session_id=session_id,
                    task_id=task_id,
                    agent_id=agent_id,
                    ts=timestamp,
                    payload={
                        "tool_name": tool_name,
                        "call_id": call_id,
                        "arguments": arguments if arguments is not None else payload.get("input"),
                    },
                )
            )
            continue

        if raw_type == "response_item" and payload_type in {"function_call_output", "custom_tool_call_output"}:
            call_id = str(payload.get("call_id") or "")
            tool_name = call_names.get(call_id, "unknown")
            normalized.append(
                Event(
                    event_type=TOOL_CALL_FINISHED,
                    source="codex_jsonl",
                    session_id=session_id,
                    task_id=task_id,
                    agent_id=agent_id,
                    ts=timestamp,
                    payload={
                        "tool_name": tool_name,
                        "call_id": call_id,
                        "output_preview": str(payload.get("output") or "")[:1000],
                    },
                )
            )
            continue

        if raw_type == "event_msg" and payload_type == "exec_command_end":
            exit_code = int(payload.get("exit_code", 1))
            if exit_code != 0:
                normalized.append(
                    Event(
                        event_type=TOOL_CALL_FAILED,
                        source="codex_jsonl",
                        session_id=session_id,
                        task_id=task_id,
                        agent_id=agent_id,
                        ts=timestamp,
                        payload={
                            "tool_name": "exec_command",
                            "call_id": payload.get("call_id"),
                            "exit_code": exit_code,
                            "stderr": payload.get("stderr"),
                        },
                    )
                )

            for parsed_cmd in payload.get("parsed_cmd", []):
                parsed_type = parsed_cmd.get("type")
                if parsed_type == "read":
                    cmd = str(parsed_cmd.get("cmd") or "")
                    path = parsed_cmd.get("path")
                    start_end = _parse_line_range(cmd) or (1, 1)
                    aggregated_output = str(payload.get("aggregated_output") or "")
                    line_count = len(aggregated_output.splitlines())
                    line_start, line_end = start_end
                    if line_count:
                        line_end = line_start + line_count - 1
                    normalized.append(
                        Event(
                            event_type=FILE_READ,
                            source="codex_jsonl",
                            session_id=session_id,
                            task_id=task_id,
                            agent_id=agent_id,
                            ts=timestamp,
                            payload=make_file_read_payload(
                                path or "",
                                line_start,
                                line_end,
                                "exec_command",
                                len(aggregated_output.encode("utf-8")),
                            ),
                        )
                    )
                elif parsed_type == "search":
                    normalized.append(
                        Event(
                            event_type=FILE_SEARCH,
                            source="codex_jsonl",
                            session_id=session_id,
                            task_id=task_id,
                            agent_id=agent_id,
                            ts=timestamp,
                            payload={
                                "query": parsed_cmd.get("query"),
                                "path": parsed_cmd.get("path"),
                                "cmd": parsed_cmd.get("cmd"),
                            },
                        )
                    )
            continue

        if raw_type == "event_msg" and payload_type == "patch_apply_end":
            patch_counts = _parse_apply_patch_input(str(call_inputs.get(payload.get("call_id")) or ""))
            for path, change in (payload.get("changes") or {}).items():
                added_lines, removed_lines = patch_counts.get(path, (0, 0))
                if change.get("type") == "add" and change.get("content"):
                    added_lines = len(str(change.get("content")).splitlines())
                    removed_lines = 0
                normalized.append(
                    Event(
                        event_type=FILE_EDIT,
                        source="codex_jsonl",
                        session_id=session_id,
                        task_id=task_id,
                        agent_id=agent_id,
                        ts=timestamp,
                        payload=make_file_edit_payload(path, "apply_patch", added_lines, removed_lines),
                    )
                )
            continue

        if raw_type == "event_msg" and payload_type == "task_started":
            normalized.append(
                Event(
                    event_type=TASK_STARTED,
                    source="codex_jsonl",
                    session_id=session_id,
                    task_id=task_id,
                    agent_id=agent_id,
                    ts=timestamp,
                    payload={
                        "model_context_window": payload.get("model_context_window"),
                        "collaboration_mode_kind": payload.get("collaboration_mode_kind"),
                    },
                )
            )
            continue

        if raw_type == "event_msg" and payload_type == "user_message":
            normalized.append(
                Event(
                    event_type=USER_MESSAGE,
                    source="codex_jsonl",
                    session_id=session_id,
                    task_id=task_id,
                    agent_id=agent_id,
                    ts=timestamp,
                    payload={"message": payload.get("message")},
                )
            )
            continue

        if raw_type == "event_msg" and payload_type == "task_complete":
            normalized.append(
                Event(
                    event_type=TASK_FINISHED,
                    source="codex_jsonl",
                    session_id=session_id,
                    task_id=task_id,
                    agent_id=agent_id,
                    ts=timestamp,
                    payload={"outcome": "completed", "last_agent_message": payload.get("last_agent_message")},
                )
            )
            continue

        if raw_type == "event_msg" and payload_type == "agent_message":
            normalized.append(
                Event(
                    event_type=AGENT_MESSAGE,
                    source="codex_jsonl",
                    session_id=session_id,
                    task_id=task_id,
                    agent_id=agent_id,
                    ts=timestamp,
                    payload={"message": payload.get("message"), "phase": payload.get("phase")},
                )
            )
            continue

    normalized.append(
        Event(
            event_type=SESSION_FINISHED,
            source="codex_jsonl",
            session_id=session_id,
            task_id=session_id,
            agent_id=agent_id,
            payload={},
        )
    )
    return normalized


def load_codex_jsonl(path: str | Path) -> List[Dict[str, Any]]:
    """Load raw Codex JSONL records from disk."""
    input_path = Path(path)
    records: List[Dict[str, Any]] = []
    with input_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records


def normalize_codex_jsonl_file(path: str | Path) -> List[Event]:
    """Load and normalize a Codex session file."""
    return normalize_codex_records(load_codex_jsonl(path))
