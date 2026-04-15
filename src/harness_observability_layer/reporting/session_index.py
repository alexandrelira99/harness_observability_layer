"""HTML index page for imported session artifacts."""

from __future__ import annotations

from html import escape
from typing import Any, Dict, Iterable


def _format_rate(value: Any) -> str:
    if value in (None, ""):
        return "0.00%"
    return f"{float(value):.2f}%"


def _badge(label: str, tone: str = "neutral") -> str:
    return f'<span class="session-badge {tone}">{escape(label)}</span>'


def _runtime_badges(metadata: Dict[str, Any], summary: Dict[str, Any]) -> str:
    badges = []
    source_name = str(metadata.get("source_name") or "Imported")
    badges.append(_badge(source_name, "source"))
    model_provider = metadata.get("model_provider")
    runtime_version = metadata.get("runtime_version")
    cli_version = metadata.get("cli_version")
    if model_provider:
        badges.append(_badge(f"provider {model_provider}"))
    if runtime_version:
        badges.append(_badge(f"runtime {runtime_version}"))
    elif cli_version:
        badges.append(_badge(f"cli {cli_version}"))
    git_branch = metadata.get("git_branch")
    if git_branch:
        badges.append(_badge(f"branch {git_branch}"))
    collaboration_mode = metadata.get("collaboration_mode_kind")
    if collaboration_mode:
        badges.append(_badge(f"mode {collaboration_mode}"))
    skill_count = int(summary.get("skill_load_count", 0) or 0)
    plugin_count = int(summary.get("plugin_invocation_count", 0) or 0)
    if skill_count:
        badges.append(_badge(f"skills {skill_count}"))
    if plugin_count:
        badges.append(_badge(f"plugins {plugin_count}"))
    if int(summary.get("edited_without_prior_read_count", 0) or 0):
        badges.append(_badge("edited without read", "warning"))
    return "".join(badges)


def _top_tool(summary: Dict[str, Any]) -> str:
    name = summary.get("top_tool_name")
    count = int(summary.get("top_tool_count", 0) or 0)
    if not name:
        return "—"
    return f"{name} ({count})"


def build_sessions_index_html(entries: Iterable[Dict[str, Any]]) -> str:
    """Build a styled index page listing imported sessions."""
    entries = list(entries)
    rows = []
    for entry in entries:
        summary = entry["summary"]
        metadata = entry.get("metadata") or {}
        failures = sum(int(v) for v in summary.get("tool_failures_by_name", {}).values())
        rows.append(
            f"""
            <a class="session-row" href="{escape(entry['report_relpath'])}">
              <div class="session-row-main">
                <div class="session-row-kicker">{escape(str(metadata.get('source_name') or 'Imported Session'))}</div>
                <div class="session-row-title">{escape(str(metadata.get('display_title') or entry['session_name']))}</div>
                <div class="session-row-subtitle">{escape(str(metadata.get('display_subtitle') or entry['session_name']))}</div>
                <div class="session-row-context">{escape(str(metadata.get('prompt_excerpt') or ''))}</div>
                <div class="session-row-badges">{_runtime_badges(metadata, summary)}</div>
              </div>
              <div class="session-row-metric">{summary.get('total_tool_calls', 0)}</div>
              <div class="session-row-metric session-row-metric-text">{escape(_top_tool(summary))}</div>
              <div class="session-row-metric">{summary.get('distinct_files_read', 0)}</div>
              <div class="session-row-metric">{summary.get('distinct_files_edited', 0)}</div>
              <div class="session-row-metric session-row-metric-stack"><strong>{_format_rate(summary.get('failure_rate_pct', 0))}</strong><span>{failures} failures</span></div>
            </a>
            """
        )

    rows_markup = "\n".join(rows) if rows else '<div class="empty-state">No imported sessions found yet.</div>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Imported Sessions · Harness Observability</title>
  <link rel="stylesheet" href="./report.css" />
</head>
<body>
  <main class="page-shell">
    <section class="hero">
      <div class="hero-copy">
        <p class="eyebrow">Harness Observability Layer</p>
        <h1>Imported Sessions</h1>
        <p class="hero-text">
          Navigate imported agent sessions, compare runtime patterns, and jump into the session reports.
        </p>
      </div>
      <div class="hero-panel">
        <div class="artifact-label">Sessions indexed</div>
        <code>{len(entries)}</code>
      </div>
    </section>

    <section class="session-grid" style="margin-top:18px;">
      <div class="session-grid-head">
        <div>Session Description</div>
        <div>Tools</div>
        <div>Top Tool</div>
        <div>Read</div>
        <div>Edited</div>
        <div>Failure Rate</div>
      </div>
      <div class="session-grid-body">
        {rows_markup}
      </div>
    </section>
  </main>
</body>
</html>
"""
