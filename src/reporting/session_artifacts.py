"""Shared helpers to materialize session artifacts inside the project."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Callable, Dict, Iterable

from harness_observability_layer.security import sanitize_session_id
from integrations.codex_jsonl import normalize_codex_jsonl_file
from integrations.claude_code_jsonl import normalize_claude_code_jsonl_file
from observer.analyzer import analyze_jsonl, load_events
from observer.logger import JsonlEventLogger

from .html_report import build_session_report_html, report_css
from .session_index import build_sessions_index_html
from .session_metadata import derive_session_metadata


def ensure_project_artifact_dirs(project_root: str | Path) -> Dict[str, Path]:
    """Ensure artifact directories exist and return their paths."""
    root = Path(project_root)
    artifacts_root = root / "artifacts"
    sessions_root = artifacts_root / "sessions"
    live_runs_root = artifacts_root / "live_runs"
    artifacts_root.mkdir(parents=True, exist_ok=True)
    sessions_root.mkdir(parents=True, exist_ok=True)
    live_runs_root.mkdir(parents=True, exist_ok=True)
    return {
        "artifacts_root": artifacts_root,
        "sessions_root": sessions_root,
        "live_runs_root": live_runs_root,
    }


def refresh_sessions_index(project_root: str | Path) -> Path:
    """Rebuild the sessions index HTML from existing imported sessions."""
    dirs = ensure_project_artifact_dirs(project_root)
    sessions_root = dirs["sessions_root"]
    entries = []
    for session_dir in sorted((path for path in sessions_root.iterdir() if path.is_dir()), key=lambda p: p.name, reverse=True):
        summary_path = session_dir / "summary.json"
        normalized_path = session_dir / "normalized.events.jsonl"
        if not summary_path.exists():
            continue
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        metadata = derive_session_metadata(session_dir.name, load_events(normalized_path)) if normalized_path.exists() else {}
        metadata_path = session_dir / "metadata.json"
        if metadata_path.exists():
            try:
                stored_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                metadata = {**stored_metadata, **metadata}
            except json.JSONDecodeError:
                metadata = metadata or {}
        entries.append(
            {
                "session_name": session_dir.name,
                "summary": summary,
                "metadata": metadata,
                "report_relpath": f"./{session_dir.name}/report.html",
            }
        )

    index_html_path = sessions_root / "index.html"
    index_css_path = sessions_root / "report.css"
    index_css_path.write_text(report_css(), encoding="utf-8")
    index_html_path.write_text(build_sessions_index_html(entries), encoding="utf-8")
    return index_html_path


def import_codex_session_to_dir(
    input_path: str | Path,
    output_dir: str | Path,
    project_root: str | Path,
    *,
    copy_raw: bool = True,
    resolve_file_stats: bool = True,
) -> Dict[str, Any]:
    """Import a raw Codex session into a project-local artifact folder."""
    source_path = Path(input_path).expanduser().resolve()
    session_dir = Path(output_dir).expanduser().resolve()
    session_dir.mkdir(parents=True, exist_ok=True)

    raw_copy_path = session_dir / "raw.codex.jsonl"
    normalized_path = session_dir / "normalized.events.jsonl"
    summary_path = session_dir / "summary.json"
    metadata_path = session_dir / "metadata.json"
    report_html_path = session_dir / "report.html"
    report_css_path = session_dir / "report.css"

    if copy_raw:
        shutil.copyfile(source_path, raw_copy_path)
    if normalized_path.exists():
        normalized_path.unlink()

    logger = JsonlEventLogger(normalized_path)
    for event in normalize_codex_jsonl_file(source_path):
        logger.log(event)

    summary = analyze_jsonl(normalized_path, resolve_file_stats=resolve_file_stats)
    events = load_events(normalized_path)
    metadata = derive_session_metadata(session_dir.name, events)
    metadata["raw_copy_enabled"] = copy_raw
    metadata["file_stats_resolution"] = "enabled" if resolve_file_stats else "disabled"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    report_css_path.write_text(report_css(), encoding="utf-8")
    report_html_path.write_text(
        build_session_report_html(
            session_label=session_dir.name,
            summary=summary,
            normalized_events_file=str(normalized_path),
            events=events,
            session_metadata=metadata,
        ),
        encoding="utf-8",
    )
    index_path = refresh_sessions_index(project_root)
    return {
        "summary": summary,
        "raw_copy_path": raw_copy_path if copy_raw else None,
        "normalized_path": normalized_path,
        "summary_path": summary_path,
        "metadata_path": metadata_path,
        "report_html_path": report_html_path,
        "report_css_path": report_css_path,
        "index_html_path": index_path,
    }


def import_session_to_dir(
    input_path: str | Path,
    output_dir: str | Path,
    project_root: str | Path,
    *,
    source_name: str,
    raw_filename: str,
    normalizer: Callable[[str | Path], Iterable[Any]],
    copy_raw: bool = True,
    resolve_file_stats: bool = True,
) -> Dict[str, Any]:
    """Import a raw source session into a project-local artifact folder."""
    source_path = Path(input_path).expanduser().resolve()
    session_dir = Path(output_dir).expanduser().resolve()
    session_dir.mkdir(parents=True, exist_ok=True)

    raw_copy_path = session_dir / raw_filename
    normalized_path = session_dir / "normalized.events.jsonl"
    summary_path = session_dir / "summary.json"
    metadata_path = session_dir / "metadata.json"
    report_html_path = session_dir / "report.html"
    report_css_path = session_dir / "report.css"

    if copy_raw:
        shutil.copyfile(source_path, raw_copy_path)
    if normalized_path.exists():
        normalized_path.unlink()

    logger = JsonlEventLogger(normalized_path)
    for event in normalizer(source_path):
        logger.log(event)

    summary = analyze_jsonl(normalized_path, resolve_file_stats=resolve_file_stats)
    events = load_events(normalized_path)
    metadata = derive_session_metadata(session_dir.name, events)
    metadata["source_name"] = source_name
    metadata["raw_filename"] = raw_filename
    metadata["raw_copy_enabled"] = copy_raw
    metadata["file_stats_resolution"] = "enabled" if resolve_file_stats else "disabled"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    report_css_path.write_text(report_css(), encoding="utf-8")
    report_html_path.write_text(
        build_session_report_html(
            session_label=session_dir.name,
            summary=summary,
            normalized_events_file=str(normalized_path),
            events=events,
            session_metadata=metadata,
        ),
        encoding="utf-8",
    )
    index_path = refresh_sessions_index(project_root)
    return {
        "summary": summary,
        "raw_copy_path": raw_copy_path if copy_raw else None,
        "normalized_path": normalized_path,
        "summary_path": summary_path,
        "metadata_path": metadata_path,
        "report_html_path": report_html_path,
        "report_css_path": report_css_path,
        "index_html_path": index_path,
    }


def import_claude_code_session_to_dir(
    input_path: str | Path,
    output_dir: str | Path,
    project_root: str | Path,
    *,
    copy_raw: bool = True,
    resolve_file_stats: bool = True,
) -> Dict[str, Any]:
    """Import a raw Claude Code session into a project-local artifact folder."""
    return import_session_to_dir(
        input_path,
        output_dir,
        project_root,
        source_name="claude",
        raw_filename="raw.claude.jsonl",
        normalizer=normalize_claude_code_jsonl_file,
        copy_raw=copy_raw,
        resolve_file_stats=resolve_file_stats,
    )
