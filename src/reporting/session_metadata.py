"""Human-friendly metadata derived from normalized session events."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from harness_observability_layer.security import sanitize_project_label


def _clean_text(value: str) -> str:
    text = re.sub(r"`+", "", value or "")
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _headline_from_prompt(prompt: str) -> str:
    clean = _clean_text(prompt)
    if not clean:
        return "Untitled Session"

    lowered = clean.lower()
    if "adequado profissionalmente" in lowered and "chat.py" in lowered:
        return "Review do chat.py"
    if "aplique corre" in lowered or "aplique correções" in lowered:
        return "Correções dos achados"
    if lowered.startswith("say only ok"):
        return "Sessão de teste: Say only OK"

    words = clean.split()
    headline = " ".join(words[:8])
    if len(words) > 8:
        headline += "..."
    return headline


def _project_name_from_events(events: List[Dict[str, Any]]) -> str | None:
    for event in events:
        payload = event.get("payload", {})
        cwd = payload.get("cwd")
        if cwd:
            return Path(str(cwd)).name

    for event in events:
        payload = event.get("payload", {})
        path = payload.get("path")
        if path:
            parts = Path(str(path)).parts
            if "projects" in parts:
                idx = parts.index("projects")
                if idx + 1 < len(parts):
                    return parts[idx + 1]
    return None


def _first_user_message(events: List[Dict[str, Any]]) -> str | None:
    for event in events:
        if event.get("event_type") == "user_message":
            return str((event.get("payload") or {}).get("message") or "")
    return None


def _format_timestamp(value: str | None) -> str | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return value


def derive_session_metadata(
    session_name: str,
    events: List[Dict[str, Any]],
    *,
    include_prompt_excerpt: bool = False,
) -> Dict[str, Any]:
    """Derive display-oriented metadata from normalized events."""
    first_ts = next((event.get("ts") for event in events if event.get("ts")), None)
    prompt = _first_user_message(events)
    project = _project_name_from_events(events)
    if include_prompt_excerpt and prompt:
        title = _headline_from_prompt(prompt)
    elif project:
        title = f"{sanitize_project_label(project)} Session"
    else:
        title = "Imported Session"
    subtitle_parts = []
    if project:
        subtitle_parts.append(project)
    formatted_ts = _format_timestamp(str(first_ts) if first_ts else None)
    if formatted_ts:
        subtitle_parts.append(formatted_ts)

    return {
        "session_name": session_name,
        "display_title": title,
        "display_subtitle": " · ".join(subtitle_parts) if subtitle_parts else session_name,
        "technical_id": session_name,
        "project_name": project,
        "started_at": formatted_ts,
        "first_user_message": _clean_text(prompt or "") or None if include_prompt_excerpt else None,
    }
