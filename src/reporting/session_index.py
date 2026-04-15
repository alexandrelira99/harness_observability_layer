"""HTML index page for imported session artifacts."""

from __future__ import annotations

from html import escape
from typing import Any, Dict, Iterable


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
                <div class="session-row-kicker">Imported Session</div>
                <div class="session-row-title">{escape(str(metadata.get('display_title') or entry['session_name']))}</div>
                <div class="session-row-subtitle">{escape(str(metadata.get('display_subtitle') or entry['session_name']))}</div>
              </div>
              <div class="session-row-metric">{summary.get('total_tool_calls', 0)}</div>
              <div class="session-row-metric">{summary.get('distinct_files_read', 0)}</div>
              <div class="session-row-metric">{summary.get('distinct_files_edited', 0)}</div>
              <div class="session-row-metric">{failures}</div>
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
          Navigate imported Codex sessions, compare file-touch patterns, and jump into the session reports.
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
        <div>Read</div>
        <div>Edited</div>
        <div>Failure</div>
      </div>
      <div class="session-grid-body">
        {rows_markup}
      </div>
    </section>
  </main>
</body>
</html>
"""
