"""Thin tool-facing API over the observability library."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

from harness_observability_layer.observer.analyzer import analyze_jsonl, load_events
from harness_observability_layer.reporting import (
    build_session_report_html,
    build_session_text,
    ensure_project_artifact_dirs,
    import_claude_code_session_to_dir,
    import_codex_session_to_dir,
    refresh_sessions_index,
    report_css,
)
from harness_observability_layer.reporting.markdown_report import build_portfolio_markdown, build_session_markdown
from harness_observability_layer.reporting.session_metadata import derive_session_metadata
from harness_observability_layer.security import redact_events, redact_metadata, redact_summary, sanitize_session_id


def _paths(project_root: str | Path) -> Dict[str, Path]:
    return ensure_project_artifact_dirs(Path(project_root).resolve())


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _session_dirs(project_root: str | Path) -> List[Path]:
    sessions_root = _paths(project_root)["sessions_root"]
    return sorted((path for path in sessions_root.iterdir() if path.is_dir()), key=lambda path: path.name, reverse=True)


def _session_entry(session_dir: Path, *, resolve_file_stats: bool | None = None) -> Dict[str, Any]:
    summary_path = session_dir / "summary.json"
    normalized_path = session_dir / "normalized.events.jsonl"
    metadata_path = session_dir / "metadata.json"
    if summary_path.exists() and resolve_file_stats is None:
        summary = _load_json(summary_path)
    else:
        summary = analyze_jsonl(normalized_path, resolve_file_stats=resolve_file_stats if resolve_file_stats is not None else True)
    derived_metadata = derive_session_metadata(session_dir.name, load_events(normalized_path))
    stored_metadata = _load_json(metadata_path) if metadata_path.exists() else {}
    metadata = {**stored_metadata, **derived_metadata}
    failures = sum(int(v) for v in summary.get("tool_failures_by_name", {}).values())
    return {
        "session_name": session_dir.name,
        "session_dir": session_dir,
        "summary": summary,
        "metadata": metadata,
        "normalized_path": normalized_path,
        "failures": failures,
    }


def _resolve_session(session_id_or_path: str, project_root: str | Path) -> Path:
    candidate = Path(session_id_or_path).expanduser()
    if candidate.exists():
        return candidate.resolve()
    session_dir = _paths(project_root)["sessions_root"] / session_id_or_path
    if session_dir.exists():
        return session_dir
    raise FileNotFoundError(f"Session not found: {session_id_or_path}")


def _sort_entries(entries: List[Dict[str, Any]], sort_by: str) -> List[Dict[str, Any]]:
    if sort_by == "failures":
        return sorted(entries, key=lambda entry: (-entry["failures"], entry["session_name"]))
    if sort_by == "tool_calls":
        return sorted(
            entries,
            key=lambda entry: (-int(entry["summary"].get("total_tool_calls", 0)), entry["session_name"]),
        )
    return sorted(entries, key=lambda entry: entry["session_name"], reverse=True)


def _archive_candidates(archive_root: Path, source: str) -> List[Path]:
    if source == "codex":
        return sorted(archive_root.glob("rollout-*.jsonl"))
    if source == "claude":
        return sorted(path for path in archive_root.rglob("*.jsonl") if path.is_file())
    raise ValueError(f"Unsupported source: {source}")


def format_result(data: Any, format: str) -> str | Dict[str, Any] | List[Dict[str, Any]]:
    """Format plugin results for CLI or tool responses."""
    if format == "json":
        return data
    if isinstance(data, str):
        return data
    return json.dumps(data, indent=2)


def import_session(
    path: str,
    output_dir: str | None = None,
    project_root: str | Path = ".",
    *,
    source: str = "codex",
    copy_raw: bool = True,
    resolve_file_stats: bool = True,
) -> Dict[str, Any]:
    """Import one raw session for the given source."""
    source_path = Path(path).expanduser().resolve()
    dirs = _paths(project_root)
    stem = sanitize_session_id(source_path.stem)
    default_name = stem if source == "codex" else sanitize_session_id(f"{source}-{stem}")
    destination = Path(output_dir).expanduser() if output_dir else dirs["sessions_root"] / default_name
    if source == "codex":
        result = import_codex_session_to_dir(
            source_path,
            destination,
            Path(project_root).resolve(),
            copy_raw=copy_raw,
            resolve_file_stats=resolve_file_stats,
        )
    elif source == "claude":
        result = import_claude_code_session_to_dir(
            source_path,
            destination,
            Path(project_root).resolve(),
            copy_raw=copy_raw,
            resolve_file_stats=resolve_file_stats,
        )
    else:
        raise ValueError(f"Unsupported source: {source}")
    return {
        "session_id": destination.name,
        "source": source,
        "summary": result["summary"],
        "paths": {
            "session_dir": str(destination),
            "raw": str(result["raw_copy_path"]) if result["raw_copy_path"] is not None else None,
            "normalized": str(result["normalized_path"]),
            "summary": str(result["summary_path"]),
            "html": str(result["report_html_path"]),
            "index": str(result["index_html_path"]),
        },
    }


def import_latest_session(
    archived_dir: str = "~/.codex/archived_sessions",
    reimport: bool = False,
    project_root: str | Path = ".",
    *,
    source: str = "codex",
    copy_raw: bool = True,
    resolve_file_stats: bool = True,
) -> Dict[str, Any]:
    """Import the most recent archived session for the given source."""
    archive_root = Path(archived_dir).expanduser().resolve()
    candidates = sorted(_archive_candidates(archive_root, source), key=lambda path: path.stat().st_mtime, reverse=True)
    if not candidates:
        raise FileNotFoundError(f"No archived {source} sessions found in {archive_root}")
    latest = candidates[0]
    stem = sanitize_session_id(latest.stem)
    destination_name = stem if source == "codex" else sanitize_session_id(f"{source}-{stem}")
    destination = _paths(project_root)["sessions_root"] / destination_name
    if destination.exists() and not reimport:
        return {"session_id": destination.name, "source": source, "skipped": True, "paths": {"session_dir": str(destination)}}
    return import_session(
        str(latest),
        output_dir=str(destination),
        project_root=project_root,
        source=source,
        copy_raw=copy_raw,
        resolve_file_stats=resolve_file_stats,
    )


def import_all_sessions(
    archived_dir: str = "~/.codex/archived_sessions",
    reimport: bool = False,
    project_root: str | Path = ".",
    *,
    source: str = "codex",
    copy_raw: bool = True,
    resolve_file_stats: bool = True,
) -> Dict[str, Any]:
    """Import all archived sessions for the given source."""
    archive_root = Path(archived_dir).expanduser().resolve()
    candidates = _archive_candidates(archive_root, source)
    imported: List[str] = []
    skipped: List[str] = []
    for session_path in candidates:
        stem = sanitize_session_id(session_path.stem)
        destination_name = stem if source == "codex" else sanitize_session_id(f"{source}-{stem}")
        destination = _paths(project_root)["sessions_root"] / destination_name
        if destination.exists() and not reimport:
            skipped.append(destination_name)
            continue
        import_session(
            str(session_path),
            output_dir=str(destination),
            project_root=project_root,
            source=source,
            copy_raw=copy_raw,
            resolve_file_stats=resolve_file_stats,
        )
        imported.append(destination_name)
    index_path = refresh_sessions_index(Path(project_root).resolve())
    return {
        "source": source,
        "imported_count": len(imported),
        "skipped_count": len(skipped),
        "imported_sessions": imported,
        "skipped_sessions": skipped,
        "index_path": str(index_path),
    }


def list_sessions(
    limit: int = 10,
    sort_by: str = "recent",
    format: str = "markdown",
    project_root: str | Path = ".",
    *,
    redact_sensitive: bool = False,
) -> str | List[Dict[str, Any]]:
    """List imported sessions with key metrics."""
    entries = [_session_entry(path) for path in _session_dirs(project_root)]
    entries = _sort_entries(entries, sort_by)[:limit]
    if format == "json":
        return [
            {
                "session_id": entry["session_name"],
                "title": (redact_metadata(entry["metadata"]) if redact_sensitive else entry["metadata"]).get("display_title"),
                "summary": redact_summary(entry["summary"]) if redact_sensitive else entry["summary"],
                "failures": entry["failures"],
            }
            for entry in entries
        ]
    if format == "markdown":
        if redact_sensitive:
            entries = [{**entry, "summary": redact_summary(entry["summary"]), "metadata": redact_metadata(entry["metadata"])} for entry in entries]
        return build_portfolio_markdown(entries)
    header = "session_id | tool_calls | files_read | files_edited | failures"
    rows = [
        "{session} | {tools} | {read} | {edited} | {failures}".format(
            session=entry["session_name"],
            tools=entry["summary"].get("total_tool_calls", 0),
            read=entry["summary"].get("distinct_files_read", 0),
            edited=entry["summary"].get("distinct_files_edited", 0),
            failures=entry["failures"],
        )
        for entry in entries
    ]
    return "\n".join([header, *rows])


def summarize_session(
    session_id: str | None = None,
    session_path: str | None = None,
    format: str = "markdown",
    project_root: str | Path = ".",
    *,
    resolve_file_stats: bool | None = None,
    redact_sensitive: bool = False,
) -> str | Dict[str, Any]:
    """Summarize a single imported session."""
    target = session_path or session_id
    if not target:
        raise ValueError("Either session_id or session_path is required")
    entry = _session_entry(_resolve_session(target, project_root), resolve_file_stats=resolve_file_stats)
    summary = redact_summary(entry["summary"]) if redact_sensitive else entry["summary"]
    metadata = redact_metadata(entry["metadata"]) if redact_sensitive else entry["metadata"]
    if format == "json":
        return {
            "session_id": entry["session_name"],
            "metadata": metadata,
            "summary": summary,
            "failures": entry["failures"],
        }
    if format == "text":
        return build_session_text(entry["session_name"], summary, metadata)
    return build_session_markdown(entry["session_name"], summary, metadata)


def compare_sessions(
    a: str,
    b: str,
    format: str = "markdown",
    project_root: str | Path = ".",
    *,
    redact_sensitive: bool = False,
) -> str | Dict[str, Any]:
    """Compare two imported sessions."""
    left = _session_entry(_resolve_session(a, project_root))
    right = _session_entry(_resolve_session(b, project_root))
    comparison = {
        "a": left["session_name"],
        "b": right["session_name"],
        "tool_call_delta": int(right["summary"].get("total_tool_calls", 0)) - int(left["summary"].get("total_tool_calls", 0)),
        "files_read_delta": int(right["summary"].get("distinct_files_read", 0)) - int(left["summary"].get("distinct_files_read", 0)),
        "files_edited_delta": int(right["summary"].get("distinct_files_edited", 0)) - int(left["summary"].get("distinct_files_edited", 0)),
        "failures_delta": right["failures"] - left["failures"],
        "edited_without_read": {
            "a": left["summary"].get("edited_without_prior_read", []),
            "b": right["summary"].get("edited_without_prior_read", []),
        },
    }
    if redact_sensitive:
        comparison["edited_without_read"] = {
            "a": [str(item).split("/")[-1] for item in comparison["edited_without_read"]["a"]],
            "b": [str(item).split("/")[-1] for item in comparison["edited_without_read"]["b"]],
        }
    if format == "json":
        return comparison
    if format == "text":
        return (
            f"compare {left['session_name']} -> {right['session_name']}\n"
            f"tool_call_delta={comparison['tool_call_delta']}\n"
            f"files_read_delta={comparison['files_read_delta']}\n"
            f"files_edited_delta={comparison['files_edited_delta']}\n"
            f"failures_delta={comparison['failures_delta']}"
        )
    return "\n".join(
        [
            f"# Session Comparison",
            "",
            f"- A: `{left['session_name']}`",
            f"- B: `{right['session_name']}`",
            f"- Tool call delta: {comparison['tool_call_delta']}",
            f"- Files read delta: {comparison['files_read_delta']}",
            f"- Files edited delta: {comparison['files_edited_delta']}",
            f"- Failures delta: {comparison['failures_delta']}",
        ]
    )


def find_high_failure_sessions(
    min_failures: int = 1,
    limit: int = 10,
    format: str = "markdown",
    project_root: str | Path = ".",
    *,
    redact_sensitive: bool = False,
) -> str | List[Dict[str, Any]]:
    """Find sessions with at least `min_failures` tool failures."""
    entries = [_session_entry(path) for path in _session_dirs(project_root)]
    ranked = [entry for entry in _sort_entries(entries, "failures") if entry["failures"] >= min_failures][:limit]
    if format == "json":
        return [
            {
                "session_id": entry["session_name"],
                "title": (redact_metadata(entry["metadata"]) if redact_sensitive else entry["metadata"]).get("display_title"),
                "failures": entry["failures"],
            }
            for entry in ranked
        ]
    if format == "text":
        return "\n".join(f"{entry['session_name']}: {entry['failures']}" for entry in ranked) or "No matching sessions."
    lines = ["# High Failure Sessions", ""]
    if not ranked:
        lines.append("No matching sessions.")
    else:
        lines.extend(f"- `{entry['session_name']}`: {entry['failures']} failures" for entry in ranked)
    return "\n".join(lines)


def generate_session_markdown(
    session_id: str,
    verbosity: str = "normal",
    project_root: str | Path = ".",
    *,
    resolve_file_stats: bool | None = None,
    redact_sensitive: bool = False,
) -> str:
    """Generate markdown for one session."""
    entry = _session_entry(_resolve_session(session_id, project_root), resolve_file_stats=resolve_file_stats)
    summary = redact_summary(entry["summary"]) if redact_sensitive else entry["summary"]
    metadata = redact_metadata(entry["metadata"]) if redact_sensitive else entry["metadata"]
    return build_session_markdown(entry["session_name"], summary, metadata, verbosity=verbosity)


def generate_portfolio_markdown(
    limit: int = 10,
    sort_by: str = "recent",
    project_root: str | Path = ".",
    *,
    redact_sensitive: bool = False,
) -> str:
    """Generate a markdown portfolio for imported sessions."""
    entries = [_session_entry(path) for path in _session_dirs(project_root)]
    entries = _sort_entries(entries, sort_by)[:limit]
    if redact_sensitive:
        entries = [{**entry, "summary": redact_summary(entry["summary"]), "metadata": redact_metadata(entry["metadata"])} for entry in entries]
    return build_portfolio_markdown(entries)


def generate_session_html(
    session_id: str,
    project_root: str | Path = ".",
    *,
    resolve_file_stats: bool | None = None,
    redact_sensitive: bool = False,
) -> Dict[str, str]:
    """Regenerate HTML artifacts for one imported session."""
    session_dir = _resolve_session(session_id, project_root)
    entry = _session_entry(session_dir, resolve_file_stats=resolve_file_stats)
    events = load_events(entry["normalized_path"])
    metadata = entry["metadata"] or derive_session_metadata(entry["session_name"], events)
    summary = entry["summary"]
    if redact_sensitive:
        metadata = redact_metadata(metadata)
        summary = redact_summary(summary)
        events = redact_events(events)
    report_path = session_dir / "report.html"
    css_path = session_dir / "report.css"
    report_path.write_text(
        build_session_report_html(
            session_label=entry["session_name"],
            summary=summary,
            normalized_events_file="[redacted]" if redact_sensitive else str(entry["normalized_path"]),
            events=events,
            session_metadata=metadata,
        ),
        encoding="utf-8",
    )
    css_path.write_text(report_css(), encoding="utf-8")
    index_path = refresh_sessions_index(Path(project_root).resolve())
    return {"report_html": str(report_path), "report_css": str(css_path), "index_html": str(index_path)}
