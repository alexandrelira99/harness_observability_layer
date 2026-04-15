"""Normalize Claude Code session JSONL into canonical observability events."""

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
    SKILL_LOADED,
    TOOL_CALL_FAILED,
    TOOL_CALL_FINISHED,
    TOOL_CALL_STARTED,
    USER_MESSAGE,
)


_NUMBERED_READ_LINE_RE = re.compile(r"^\s*(?P<line>\d+)\t", re.MULTILINE)


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

