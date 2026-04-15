"""Normalize Claude Code session JSONL into canonical observability events."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List

from harness_observability_layer.observer.events import Event
from harness_observability_layer.observer.normalizers import make_file_edit_payload, make_file_read_payload
from harness_observability_layer.observer.schemas import (
    AGENT_MESSAGE,
    FILE_EDIT,
    FILE_READ,
    FILE_SEARCH,
    SESSION_FINISHED,
    SESSION_STARTED,
    SKILL_LOADED,
    TOOL_CALL_FAILED,
    TOOL_CALL_FINISHED,
    TOOL_CALL_STARTED,
    USER_MESSAGE,
)


_NUMBERED_READ_LINE_RE = re.compile(r"^\s*(?P<line>\d+)\t", re.MULTILINE)
_OBSERVED_BLOCK_RE = re.compile(r"<observed_from_primary_session>\s*(?P<body>.*?)\s*</observed_from_primary_session>", re.DOTALL)
_OBSERVED_FIELD_RE = re.compile(r"<(?P<name>[a-zA-Z0-9_]+)>\s*(?P<value>.*?)\s*</(?P=name)>", re.DOTALL)
_SED_RANGE_RE = re.compile(r"sed\s+-n\s+'(?P<start>\d+),(?P<end>\d+)p'\s+(?P<path>\S+)")
_RG_RE = re.compile(r"\brg\s+-n\s+(?P<query>.+?)\s+-S\s+(?P<path>\S+)")
_CAT_RE = re.compile(r"\bcat\s+(?P<path>/\S+|\./\S+|\S+)")
_EXIT_CODE_RE = re.compile(r"Process exited with code (?P<code>-?\d+)")
_SESSION_ID_RE = re.compile(r"session ID (?P<session_id>\d+)")


def _timestamp_of(raw: Dict[str, Any]) -> str:
    return str(raw.get("timestamp") or "")


def _extract_text_blocks(content: Any) -> List[str]:
    if isinstance(content, str):
        return [content]
    if not isinstance(content, list):
        return []
    texts: List[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text" and block.get("text"):
            texts.append(str(block.get("text")))
    return texts


def _count_numbered_lines(text: str) -> int:
    if not text:
        return 0
    return len(_NUMBERED_READ_LINE_RE.findall(text))


def _count_lines(value: str | None) -> int:
    if not value:
        return 0
    return len(str(value).splitlines())


def _parse_observed_block(body: str) -> Dict[str, str]:
    fields: Dict[str, str] = {}
    for match in _OBSERVED_FIELD_RE.finditer(body):
        fields[match.group("name")] = match.group("value").strip()
    return fields


def _unwrap_embedded_json_string(value: str | None) -> str:
    if not value:
        return ""
    text = value.strip()
    for _ in range(3):
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError:
            return text
        if not isinstance(decoded, str):
            return text
        if decoded == text:
            return decoded
        text = decoded
    return text


def _parse_observed_parameters(raw_value: str | None) -> Dict[str, Any]:
    decoded = _unwrap_embedded_json_string(raw_value)
    if not decoded:
        return {}
    try:
        parsed = json.loads(decoded)
    except json.JSONDecodeError:
        return {"raw": decoded}
    return parsed if isinstance(parsed, dict) else {"raw": parsed}


def _parse_observed_outcome(raw_value: str | None) -> str:
    return _unwrap_embedded_json_string(raw_value)


def _parse_line_range(cmd: str) -> tuple[int, int] | None:
    match = _SED_RANGE_RE.search(cmd or "")
    if not match:
        return None
    return int(match.group("start")), int(match.group("end"))


def _extract_observed_output_body(outcome_text: str) -> str:
    if not outcome_text:
        return ""
    marker = "Output:\n"
    if marker in outcome_text:
        return outcome_text.split(marker, 1)[1].strip("\n")
    return outcome_text


def _clean_command_path(path: str) -> str:
    return path.strip().strip("\"'`")


def _parse_observed_file_events(
    *,
    tool_name: str,
    command_text: str,
    output_text: str,
    session_id: str,
    task_id: str,
    agent_id: str,
    timestamp: str,
) -> List[Event]:
    events: List[Event] = []
    output_body = _extract_observed_output_body(output_text)

    sed_match = _SED_RANGE_RE.search(command_text or "")
    if sed_match:
        path = _clean_command_path(sed_match.group("path"))
        line_start = int(sed_match.group("start"))
        line_end = int(sed_match.group("end"))
        line_count = _count_lines(output_body)
        if line_count:
            line_end = line_start + line_count - 1
        events.append(
            Event(
                event_type=FILE_READ,
                source="claude_code_jsonl",
                session_id=session_id,
                task_id=task_id,
                agent_id=agent_id,
                ts=timestamp,
                payload=make_file_read_payload(
                    path,
                    line_start,
                    line_end,
                    tool_name,
                    len(output_body.encode("utf-8")),
                ),
            )
        )

    rg_match = _RG_RE.search(command_text or "")
    if rg_match:
        query = rg_match.group("query").strip().strip("\"'")
        search_path = _clean_command_path(rg_match.group("path"))
        events.append(
            Event(
                event_type=FILE_SEARCH,
                source="claude_code_jsonl",
                session_id=session_id,
                task_id=task_id,
                agent_id=agent_id,
                ts=timestamp,
                payload={
                    "query": query,
                    "path": search_path,
                    "tool_name": tool_name,
                },
            )
        )

    if not events:
        cat_match = _CAT_RE.search(command_text or "")
        if cat_match:
            path = _clean_command_path(cat_match.group("path"))
            line_end = max(_count_lines(output_body), 1)
            events.append(
                Event(
                    event_type=FILE_READ,
                    source="claude_code_jsonl",
                    session_id=session_id,
                    task_id=task_id,
                    agent_id=agent_id,
                    ts=timestamp,
                    payload=make_file_read_payload(
                        path,
                        1,
                        line_end,
                        tool_name,
                        len(output_body.encode("utf-8")),
                    ),
                )
            )
    return events


def _observed_primary_session_events(text: str, session_id: str, task_id: str, agent_id: str) -> List[Event]:
    events: List[Event] = []

    for match in _OBSERVED_BLOCK_RE.finditer(text or ""):
        fields = _parse_observed_block(match.group("body"))
        tool_name = fields.get("what_happened")
        if not tool_name:
            continue

        timestamp = fields.get("occurred_at") or ""
        parameters = _parse_observed_parameters(fields.get("parameters"))
        outcome_text = _parse_observed_outcome(fields.get("outcome"))
        call_id = str(
            parameters.get("session_id")
            or parameters.get("call_id")
            or (_SESSION_ID_RE.search(outcome_text).group("session_id") if _SESSION_ID_RE.search(outcome_text) else "")
            or fields.get("occurred_at")
            or ""
        )

        events.append(
            Event(
                event_type=TOOL_CALL_STARTED,
                source="claude_code_jsonl",
                session_id=session_id,
                task_id=task_id,
                agent_id=agent_id,
                ts=timestamp,
                payload={
                    "tool_name": tool_name,
                    "call_id": call_id,
                    "arguments": parameters,
                },
            )
        )
        events.append(
            Event(
                event_type=TOOL_CALL_FINISHED,
                source="claude_code_jsonl",
                session_id=session_id,
                task_id=task_id,
                agent_id=agent_id,
                ts=timestamp,
                payload={
                    "tool_name": tool_name,
                    "call_id": call_id,
                    "output_preview": outcome_text[:1000],
                },
            )
        )

        exit_code_match = _EXIT_CODE_RE.search(outcome_text)
        if exit_code_match:
            exit_code = int(exit_code_match.group("code"))
            if exit_code != 0:
                events.append(
                    Event(
                        event_type=TOOL_CALL_FAILED,
                        source="claude_code_jsonl",
                        session_id=session_id,
                        task_id=task_id,
                        agent_id=agent_id,
                        ts=timestamp,
                        payload={
                            "tool_name": tool_name,
                            "call_id": call_id,
                            "exit_code": exit_code,
                        },
                    )
                )

        command_text = str(parameters.get("cmd") or "")
        if command_text:
            events.extend(
                _parse_observed_file_events(
                    tool_name=tool_name,
                    command_text=command_text,
                    output_text=outcome_text,
                    session_id=session_id,
                    task_id=task_id,
                    agent_id=agent_id,
                    timestamp=timestamp,
                )
            )

    return events


def _assistant_text_message(raw: Dict[str, Any], session_id: str, task_id: str, agent_id: str) -> List[Event]:
    message = raw.get("message") or {}
    texts = _extract_text_blocks(message.get("content"))
    if not texts:
        return []
    return [
        Event(
            event_type=AGENT_MESSAGE,
            source="claude_code_jsonl",
            session_id=session_id,
            task_id=task_id,
            agent_id=agent_id,
            ts=_timestamp_of(raw),
            payload={"message": "\n".join(texts), "phase": "assistant"},
        )
    ]


def normalize_claude_code_records(records: Iterable[Dict[str, Any]]) -> List[Event]:
    """Convert raw Claude Code JSONL records into canonical events."""
    normalized: List[Event] = []
    started = False
    session_id = "unknown_claude_session"
    agent_id = "main"
    task_id = "task_1"
    cwd: str | None = None
    call_names: Dict[str, str] = {}
    call_inputs: Dict[str, Dict[str, Any]] = {}

    for raw in records:
        session_id = str(raw.get("sessionId") or session_id)
        cwd = str(raw.get("cwd") or cwd or "")
        task_id = session_id
        timestamp = _timestamp_of(raw)

        if not started and session_id != "unknown_claude_session":
            normalized.append(
                Event(
                    event_type=SESSION_STARTED,
                    source="claude_code_jsonl",
                    session_id=session_id,
                    task_id=task_id,
                    agent_id=agent_id,
                    ts=timestamp,
                    payload={
                        "cwd": cwd or None,
                        "entrypoint": raw.get("entrypoint"),
                        "version": raw.get("version"),
                        "git_branch": raw.get("gitBranch"),
                    },
                )
            )
            started = True

        raw_type = raw.get("type")

        if raw_type == "user":
            message = raw.get("message") or {}
            content = message.get("content")
            for text in _extract_text_blocks(content):
                normalized.append(
                    Event(
                        event_type=USER_MESSAGE,
                        source="claude_code_jsonl",
                        session_id=session_id,
                        task_id=task_id,
                        agent_id=agent_id,
                        ts=timestamp,
                        payload={"message": text},
                    )
                )
                normalized.extend(_observed_primary_session_events(text, session_id, task_id, agent_id))

            if isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict) or block.get("type") != "tool_result":
                        continue
                    call_id = str(block.get("tool_use_id") or "")
                    tool_name = call_names.get(call_id, "unknown")
                    output_text = str(block.get("content") or "")
                    normalized.append(
                        Event(
                            event_type=TOOL_CALL_FINISHED,
                            source="claude_code_jsonl",
                            session_id=session_id,
                            task_id=task_id,
                            agent_id=agent_id,
                            ts=timestamp,
                            payload={
                                "tool_name": tool_name,
                                "call_id": call_id,
                                "output_preview": output_text[:1000],
                            },
                        )
                    )

                    tool_result = raw.get("toolUseResult") or {}
                    if tool_name == "Read":
                        path = call_inputs.get(call_id, {}).get("file_path") or tool_result.get("filePath")
                        if path:
                            numbered_lines = _count_numbered_lines(output_text)
                            line_end = numbered_lines if numbered_lines else max(_count_lines(output_text), 1)
                            normalized.append(
                                Event(
                                    event_type=FILE_READ,
                                    source="claude_code_jsonl",
                                    session_id=session_id,
                                    task_id=task_id,
                                    agent_id=agent_id,
                                    ts=timestamp,
                                    payload=make_file_read_payload(
                                        path,
                                        1,
                                        line_end,
                                        "Read",
                                        len(output_text.encode("utf-8")),
                                    ),
                                )
                            )
                    elif tool_name in {"Grep", "Glob"}:
                        query = call_inputs.get(call_id, {}).get("pattern") or call_inputs.get(call_id, {}).get("glob")
                        search_path = call_inputs.get(call_id, {}).get("path") or tool_result.get("filePath")
                        normalized.append(
                            Event(
                                event_type=FILE_SEARCH,
                                source="claude_code_jsonl",
                                session_id=session_id,
                                task_id=task_id,
                                agent_id=agent_id,
                                ts=timestamp,
                                payload={
                                    "query": query,
                                    "path": search_path,
                                    "tool_name": tool_name,
                                },
                            )
                        )
                    elif tool_name == "Edit":
                        edit_path = tool_result.get("filePath") or call_inputs.get(call_id, {}).get("file_path")
                        if edit_path:
                            old_string = tool_result.get("oldString") or call_inputs.get(call_id, {}).get("old_string")
                            new_string = tool_result.get("newString") or call_inputs.get(call_id, {}).get("new_string")
                            normalized.append(
                                Event(
                                    event_type=FILE_EDIT,
                                    source="claude_code_jsonl",
                                    session_id=session_id,
                                    task_id=task_id,
                                    agent_id=agent_id,
                                    ts=timestamp,
                                    payload=make_file_edit_payload(
                                        edit_path,
                                        "Edit",
                                        _count_lines(str(new_string) if new_string is not None else ""),
                                        _count_lines(str(old_string) if old_string is not None else ""),
                                    ),
                                )
                            )
                    elif tool_name == "Bash":
                        exit_code = raw.get("toolUseResult", {}).get("exitCode")
                        if exit_code not in (None, 0):
                            normalized.append(
                                Event(
                                    event_type=TOOL_CALL_FAILED,
                                    source="claude_code_jsonl",
                                    session_id=session_id,
                                    task_id=task_id,
                                    agent_id=agent_id,
                                    ts=timestamp,
                                    payload={
                                        "tool_name": tool_name,
                                        "call_id": call_id,
                                        "exit_code": exit_code,
                                    },
                                )
                            )
            continue

        if raw_type == "assistant":
            normalized.extend(_assistant_text_message(raw, session_id, task_id, agent_id))
            message = raw.get("message") or {}
            content = message.get("content")
            if isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict) or block.get("type") != "tool_use":
                        continue
                    call_id = str(block.get("id") or "")
                    tool_name = str(block.get("name") or "unknown")
                    tool_input = block.get("input") or {}
                    call_names[call_id] = tool_name
                    call_inputs[call_id] = tool_input if isinstance(tool_input, dict) else {"raw_input": tool_input}
                    normalized.append(
                        Event(
                            event_type=TOOL_CALL_STARTED,
                            source="claude_code_jsonl",
                            session_id=session_id,
                            task_id=task_id,
                            agent_id=agent_id,
                            ts=timestamp,
                            payload={
                                "tool_name": tool_name,
                                "call_id": call_id,
                                "arguments": tool_input,
                            },
                        )
                    )
            continue

        if raw_type == "attachment":
            attachment = raw.get("attachment") or {}
            if attachment.get("type") == "skill_listing":
                content = str(attachment.get("content") or "")
                for line in content.splitlines():
                    skill_name = line.strip()
                    if not skill_name.startswith("- "):
                        continue
                    skill_label = skill_name[2:].split(":", 1)[0].strip()
                    normalized.append(
                        Event(
                            event_type=SKILL_LOADED,
                            source="claude_code_jsonl",
                            session_id=session_id,
                            task_id=task_id,
                            agent_id=agent_id,
                            ts=timestamp,
                            payload={"skill_name": skill_label},
                        )
                    )
            continue

    normalized.append(
        Event(
            event_type=SESSION_FINISHED,
            source="claude_code_jsonl",
            session_id=session_id,
            task_id=task_id,
            agent_id=agent_id,
            payload={},
        )
    )
    return normalized


def load_claude_code_jsonl(path: str | Path) -> List[Dict[str, Any]]:
    """Load raw Claude Code JSONL records from disk."""
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


def normalize_claude_code_jsonl_file(path: str | Path) -> List[Event]:
    """Load and normalize a Claude Code session file."""
    return normalize_claude_code_records(load_claude_code_jsonl(path))
