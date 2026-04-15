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


def _strip_shell_prefix(text: str) -> str:
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    if not lines:
        return text.strip()
    first = lines[0]
    if "$ " in first:
        command = first.rsplit("$ ", 1)[-1].strip()
        remainder = "\n".join(lines[1:]).strip()
        return f"{command}\n{remainder}".strip() if remainder else command
    shell_match = re.search(r"(?:^|\s)(?:[A-Za-z0-9_.-]+@[-A-Za-z0-9_.]+:)?[^\n$]*\$\s+(?P<cmd>.+)$", first)
    if shell_match:
        command = shell_match.group("cmd").strip()
        remainder = "\n".join(lines[1:]).strip()
        return f"{command}\n{remainder}".strip() if remainder else command
    return "\n".join(lines)


def _looks_like_json_blob(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    return stripped.startswith("{") or stripped.startswith("[")


def _looks_like_terminal_dump(text: str) -> bool:
    lowered = text.lower()
    markers = [
        "chunk id:",
        "wall time:",
        "process exited with code",
        "original token count:",
        "output:",
    ]
    return any(marker in lowered for marker in markers)


def _command_headline(command: str) -> str | None:
    clean = _clean_text(command)
    clean = _strip_shell_prefix(clean)
    lowered = clean.lower()

    command_patterns = [
        (r"^hol\s+import\s+claude-latest\b", "Import Claude Latest Session"),
        (r"^hol\s+import\s+claude-all\b", "Import All Claude Sessions"),
        (r"^hol\s+import\s+claude-session\b", "Import Claude Session"),
        (r"^hol\s+import\s+latest\b", "Import Latest Codex Session"),
        (r"^hol\s+import\s+all\b", "Import All Codex Sessions"),
        (r"^hol\s+import\s+session\b", "Import Codex Session"),
        (r"^hol\s+analyze\s+latest\b", "Analyze Latest Session"),
        (r"^hol\s+analyze\s+session\b", "Analyze Session"),
        (r"^hol\s+analyze\s+compare\b", "Compare Sessions"),
        (r"^hol\s+report\s+html\b", "Generate HTML Report"),
        (r"^hol\s+report\s+markdown\b", "Generate Markdown Report"),
        (r"^hol\s+report\s+summary\b", "Generate Session Summary"),
        (r"^hol\s+list\b", "List Imported Sessions"),
        (r"^hol\s+portfolio\b", "Generate Session Portfolio"),
        (r"^hol\s+failures\b", "Find High-Failure Sessions"),
        (r"^pip\s+install\b", "Install Python Package"),
        (r"^python\s+-m\s+harness_observability_layer\b", "Run HOL Module"),
        (r"^reflex\s+run\b", "Run Reflex App"),
    ]
    for pattern, headline in command_patterns:
        if re.search(pattern, lowered):
            if headline == "Run Reflex App" and "not found" in lowered:
                return "Reflex Command Not Found"
            return headline
    return None


def _headline_from_prompt(prompt: str) -> str:
    clean = _clean_text(prompt)
    if not clean:
        return "Untitled Session"

    command_headline = _command_headline(clean)
    if command_headline:
        return command_headline

    lowered = clean.lower()
    if "adequado profissionalmente" in lowered and "chat.py" in lowered:
        return "Review do chat.py"
    if "aplique corre" in lowered or "aplique correções" in lowered:
        return "Correções dos achados"
    if lowered.startswith("say only ok"):
        return "Sessão de teste: Say only OK"
    if _looks_like_json_blob(clean):
        return "Imported Session"
    if _looks_like_terminal_dump(clean):
        return "Terminal Session"

    words = clean.split()
    headline = " ".join(words[:8])
    if len(words) > 8:
        headline += "..."
    return headline


def _excerpt_from_prompt(prompt: str, words_limit: int = 18) -> str | None:
    clean = _clean_text(prompt)
    if not clean:
        return None
    clean = _strip_shell_prefix(clean)
    json_start = clean.find("{")
    if json_start > 0:
        clean = clean[:json_start].strip()
    if _looks_like_terminal_dump(clean):
        lines = [line.strip() for line in clean.splitlines() if line.strip()]
        clean = lines[0] if lines else clean
    words = clean.split()
    excerpt = " ".join(words[:words_limit])
    if len(words) > words_limit:
        excerpt += "..."
    return excerpt


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


def _first_event_payload(events: List[Dict[str, Any]], event_type: str) -> Dict[str, Any]:
    for event in events:
        if event.get("event_type") == event_type:
            payload = event.get("payload") or {}
            if isinstance(payload, dict):
                return payload
    return {}


def _source_label(payload: Dict[str, Any], events: List[Dict[str, Any]]) -> str:
    source_name = str(payload.get("source") or payload.get("source_name") or "").strip().lower()
    if source_name in {"codex", "openai"}:
        return "Codex"
    if source_name == "claude":
        return "Claude Code"
    for event in events:
        source = str(event.get("source") or "").strip().lower()
        if source == "codex_jsonl":
            return "Codex"
        if source == "claude_code_jsonl":
            return "Claude Code"
    return "Imported"


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
    prompt_headline = _headline_from_prompt(prompt) if prompt else None
    prompt_excerpt = _excerpt_from_prompt(prompt) if prompt else None
    project = _project_name_from_events(events)
    session_payload = _first_event_payload(events, "session_started")
    task_payload = _first_event_payload(events, "task_started")
    source = _source_label(session_payload, events)
    model_provider = session_payload.get("model_provider")
    cli_version = session_payload.get("cli_version")
    runtime_version = session_payload.get("version")
    git_branch = session_payload.get("git_branch")
    entrypoint = session_payload.get("entrypoint")
    collaboration_mode = task_payload.get("collaboration_mode_kind")
    model_context_window = task_payload.get("model_context_window")

    if prompt_headline:
        title = prompt_headline
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
        "source_name": source,
        "model_provider": str(model_provider) if model_provider else None,
        "cli_version": str(cli_version) if cli_version else None,
        "runtime_version": str(runtime_version) if runtime_version else None,
        "git_branch": str(git_branch) if git_branch else None,
        "entrypoint": str(entrypoint) if entrypoint else None,
        "collaboration_mode_kind": str(collaboration_mode) if collaboration_mode else None,
        "model_context_window": model_context_window,
        "task_headline": prompt_headline,
        "prompt_excerpt": prompt_excerpt if include_prompt_excerpt or prompt_excerpt else None,
        "first_user_message": _clean_text(prompt or "") or None if include_prompt_excerpt else None,
    }
