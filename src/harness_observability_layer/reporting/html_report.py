"""Build a styled HTML report for an imported observability session."""

from __future__ import annotations

import json
from html import escape
from typing import Any, Dict, Iterable, List, Tuple


def _fmt_number(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _tool_cards(
    tool_calls_by_name: Dict[str, Any], failures_by_name: Dict[str, Any]
) -> str:
    if not tool_calls_by_name:
        return '<div class="empty-state">No tool calls were detected for this session.</div>'

    cards = []
    for tool_name, count in sorted(
        tool_calls_by_name.items(), key=lambda item: (-item[1], item[0])
    ):
        failures = int(failures_by_name.get(tool_name, 0))
        cards.append(
            f"""
            <article class="metric-card tool-card">
              <div class="metric-label">{escape(tool_name)}</div>
              <div class="metric-value">{count}</div>
              <div class="metric-subtle">failures: {failures}</div>
            </article>
            """
        )
    return "\n".join(cards)


def _top_files(
    files: Dict[str, Dict[str, Any]], limit: int = 12
) -> Iterable[Tuple[str, Dict[str, Any]]]:
    return sorted(
        files.items(),
        key=lambda item: (
            -(item[1].get("read_coverage_pct") or 0),
            -(item[1].get("edit_count") or 0),
            item[0],
        ),
    )[:limit]


def _files_table(files: Dict[str, Dict[str, Any]]) -> str:
    if not files:
        return '<div class="empty-state">No file reads or edits were detected.</div>'

    rows: List[str] = []
    for path, meta in _top_files(files):
        coverage = meta.get("read_coverage_pct")
        coverage_text = "—" if coverage is None else f"{coverage:.2f}%"
        coverage_ratio = (
            0 if coverage is None else max(0, min(int(round(coverage)), 100))
        )
        rows.append(
            f"""
            <tr>
              <td class="path-cell">{escape(path)}</td>
              <td>{_fmt_number(meta.get("union_lines_read"))}</td>
              <td>{_fmt_number(meta.get("total_lines"))}</td>
              <td>
                <div class="coverage-cell">
                  <div class="coverage-bar"><span style="width: {coverage_ratio}%"></span></div>
                  <span>{coverage_text}</span>
                </div>
              </td>
              <td>{_fmt_number(meta.get("edit_count"))}</td>
              <td>{_fmt_number(meta.get("added_lines"))}</td>
              <td>{_fmt_number(meta.get("removed_lines"))}</td>
            </tr>
            """
        )
    return "\n".join(rows)


def _list_block(values: Iterable[str], empty_text: str) -> str:
    values = list(values)
    if not values:
        return f'<div class="empty-state">{escape(empty_text)}</div>'
    return (
        '<ul class="inline-list">'
        + "".join(f"<li>{escape(value)}</li>" for value in values)
        + "</ul>"
    )


def _event_label(event: Dict[str, Any]) -> str:
    payload = event.get("payload", {})
    event_type = event.get("event_type", "unknown")
    if event_type in {"tool_call_started", "tool_call_finished", "tool_call_failed"}:
        return str(payload.get("tool_name") or event_type)
    if event_type == "file_read":
        return str(payload.get("path") or event_type)
    if event_type == "file_edit":
        return str(payload.get("path") or event_type)
    if event_type == "agent_message":
        return "assistant message"
    if event_type == "user_message":
        return "user message"
    return event_type


def _timeline_markup(events: List[Dict[str, Any]], limit: int = 18) -> str:
    if not events:
        return '<div class="empty-state">No normalized events available for timeline rendering.</div>'
    selected = events[:limit]
    items = []
    for event in selected:
        items.append(
            f"""
            <article class="timeline-item">
              <div class="timeline-dot"></div>
              <div class="timeline-content">
                <div class="timeline-meta">
                  <span class="timeline-type">{escape(str(event.get("event_type", "unknown")))}</span>
                  <span class="timeline-ts">{escape(str(event.get("ts", "")))}</span>
                </div>
                <div class="timeline-label">{escape(_event_label(event))}</div>
              </div>
            </article>
            """
        )
    return "\n".join(items)


def _heatmap_markup(files: Dict[str, Dict[str, Any]], limit: int = 12) -> str:
    if not files:
        return (
            '<div class="empty-state">No files available for heatmap rendering.</div>'
        )
    cards = []
    for path, meta in sorted(
        files.items(),
        key=lambda item: (
            -(item[1].get("union_lines_read") or 0),
            -(item[1].get("edit_count") or 0),
            item[0],
        ),
    )[:limit]:
        coverage = meta.get("read_coverage_pct") or 0
        intensity = max(8, min(int(round(coverage)), 100))
        edits = int(meta.get("edit_count") or 0)
        tone = "edited" if edits else "read"
        cards.append(
            f"""
            <article class="heat-card {tone}">
              <div class="heat-top">
                <div class="heat-path">{escape(path)}</div>
                <div class="heat-badge">{coverage:.2f}%</div>
              </div>
              <div class="heat-bar"><span style="width:{intensity}%"></span></div>
              <div class="heat-meta">
                <span>read {meta.get("union_lines_read", 0)} lines</span>
                <span>edits {edits}</span>
              </div>
            </article>
            """
        )
    return "\n".join(cards)


def _format_duration(seconds: float) -> str:
    if seconds <= 0:
        return "0s"
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes = seconds / 60
    if minutes < 60:
        return f"{minutes:.1f}m"
    hours = minutes / 60
    return f"{hours:.1f}h"


def _format_cost(cost: float | None) -> str:
    if cost is None:
        return "—"
    if cost < 0.01:
        return f"${cost:.4f}"
    return f"${cost:.2f}"


def _format_cost_card(summary: Dict[str, Any]) -> str:
    plan = summary.get("plan_type")
    cost = summary.get("estimated_cost_usd")
    if plan:
        label = plan.capitalize()
        if cost is not None:
            return f'{label} <span style="font-size:0.6em;opacity:0.6">(API-equiv {_format_cost(cost)})</span>'
        return label
    return _format_cost(cost)


def _format_tokens(count: int) -> str:
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1_000:
        return f"{count / 1_000:.1f}K"
    return str(count)


def _format_token_breakdown(summary: Dict[str, Any]) -> str:
    input_tokens = int(summary.get("total_input_tokens", 0) or 0)
    cache_tokens = int(summary.get("total_cache_read_tokens", 0) or 0)
    output_tokens = int(summary.get("total_output_tokens", 0) or 0)
    if cache_tokens:
        return (
            f"{_format_tokens(input_tokens)} in / "
            f"{_format_tokens(cache_tokens)} cache / "
            f"{_format_tokens(output_tokens)} out"
        )
    return f"{_format_tokens(input_tokens)} in / {_format_tokens(output_tokens)} out"


def build_session_report_html(
    session_label: str,
    summary: Dict[str, Any],
    normalized_events_file: str,
    events: List[Dict[str, Any]] | None = None,
    session_metadata: Dict[str, Any] | None = None,
) -> str:
    """Return a styled static HTML report."""
    files = summary.get("files", {})
    tool_calls_by_name = summary.get("tool_calls_by_name", {})
    failures_by_name = summary.get("tool_failures_by_name", {})
    edited_without_read = summary.get("edited_without_prior_read", [])
    read_without_edit = summary.get("read_without_edit", [])
    reread_files = summary.get("reread_files", [])
    skill_loads = summary.get("skill_loads_by_name", {})
    plugin_calls = summary.get("plugin_invocations_by_name", {})
    efficiency = summary.get("efficiency_indicators", {})
    stop_reasons = summary.get("stop_reasons", {})
    bash_categories = summary.get("bash_command_categories", {})
    skills_without_followup = summary.get("skills_without_followup", [])
    tool_failure_rate = summary.get("tool_failure_rate_by_name", {})
    summary_json = escape(json.dumps(summary, indent=2))
    events = events or []
    session_metadata = session_metadata or {}
    display_title = str(session_metadata.get("display_title") or session_label)
    display_subtitle = str(
        session_metadata.get("display_subtitle")
        or "Imported Codex session report with normalized metrics, file usage, tool activity, and workflow signals."
    )
    technical_id = str(session_metadata.get("technical_id") or session_label)

    skill_markup = _list_block(
        [
            f"{name} ({count})"
            for name, count in sorted(
                skill_loads.items(), key=lambda item: (-item[1], item[0])
            )
        ],
        "No skill activation detected in the imported stream.",
    )
    plugin_markup = _list_block(
        [
            f"{name} ({count})"
            for name, count in sorted(
                plugin_calls.items(), key=lambda item: (-item[1], item[0])
            )
        ],
        "No plugin invocation detected in the imported stream.",
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(display_title)} · Harness Observability</title>
  <link rel="stylesheet" href="./report.css" />
</head>
<body>
  <main class="page-shell">
    <section class="hero">
      <div class="hero-copy">
        <p class="eyebrow">Harness Observability Layer</p>
        <h1>{escape(display_title)}</h1>
        <p class="hero-text">
          {escape(display_subtitle)}
        </p>
      </div>
      <div class="hero-panel">
        <div class="artifact-label">Technical ID</div>
        <code>{escape(technical_id)}</code>
        <div class="artifact-label">Normalized events</div>
        <code>{escape(normalized_events_file)}</code>
      </div>
    </section>

    <section class="stats-grid">
      <article class="metric-card primary">
        <div class="metric-label">Tool Calls</div>
        <div class="metric-value">{summary.get("total_tool_calls", 0)}</div>
        <div class="metric-subtle">observed canonical completions</div>
      </article>
      <article class="metric-card">
        <div class="metric-label">Files Read</div>
        <div class="metric-value">{summary.get("distinct_files_read", 0)}</div>
        <div class="metric-subtle">distinct file paths touched</div>
      </article>
      <article class="metric-card">
        <div class="metric-label">Files Edited</div>
        <div class="metric-value">{summary.get("distinct_files_edited", 0)}</div>
        <div class="metric-subtle">canonical file edit events</div>
      </article>
      <article class="metric-card">
        <div class="metric-label">Failures</div>
        <div class="metric-value">{sum(int(v) for v in failures_by_name.values())}</div>
        <div class="metric-subtle">tool failures detected</div>
      </article>
      <article class="metric-card">
        <div class="metric-label">Total Tokens</div>
        <div class="metric-value">{_format_tokens(summary.get("total_tokens", 0))}</div>
        <div class="metric-subtle">{_format_token_breakdown(summary)}</div>
      </article>
      <article class="metric-card">
        <div class="metric-label">Est. Cost</div>
        <div class="metric-value">{_format_cost_card(summary)}</div>
        <div class="metric-subtle">cache hit {summary.get("cache_hit_rate_pct", 0):.1f}%</div>
      </article>
      <article class="metric-card">
        <div class="metric-label">Duration</div>
        <div class="metric-value">{_format_duration(summary.get("session_duration_seconds", 0))}</div>
        <div class="metric-subtle">{summary.get("turns_per_session", 0)} turns</div>
      </article>
      <article class="metric-card">
        <div class="metric-label">Model</div>
        <div class="metric-value" style="font-size:clamp(18px,2.5vw,28px)">{escape(str(summary.get("model") or "—"))}</div>
        <div class="metric-subtle">{summary.get("max_concurrent_tool_calls", 0)} max concurrent</div>
      </article>
    </section>

    <section class="panel-grid">
      <section class="panel">
        <div class="panel-head">
          <h2>Tool Activity</h2>
          <p>Most-used tools in the imported session.</p>
        </div>
        <div class="tool-grid">
          {_tool_cards(tool_calls_by_name, failures_by_name)}
        </div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h2>Operational Gaps</h2>
          <p>Quick signals that deserve review.</p>
        </div>
        <div class="callout-stack">
          <article class="callout">
            <h3>Edited Without Prior Read</h3>
            {_list_block(edited_without_read, "No edited-without-prior-read files detected.")}
          </article>
          <article class="callout">
            <h3>Re-read Files</h3>
            {_list_block(reread_files, "No files were re-read.")}
          </article>
          <article class="callout">
            <h3>Read Without Edit</h3>
            {_list_block(read_without_edit, "All read files were also edited.")}
          </article>
          <article class="callout">
            <h3>Skills Without Follow-up</h3>
            {_list_block(skills_without_followup, "All loaded skills had subsequent activity.")}
          </article>
          <article class="callout">
            <h3>Skills</h3>
            {skill_markup}
          </article>
          <article class="callout">
            <h3>Plugins</h3>
            {plugin_markup}
          </article>
        </div>
      </section>
    </section>

    <section class="panel-grid" style="margin-top:18px">
      <section class="panel">
        <div class="panel-head">
          <h2>Efficiency Indicators</h2>
          <p>Composite signals of session health.</p>
        </div>
        <div class="callout-stack">
          <article class="callout">
            <h3>Efficiency Summary</h3>
            <div class="efficiency-grid">
              <div class="efficiency-item"><span class="eff-label">Edited w/o Read</span><strong>{efficiency.get("edited_without_read_ratio", 0):.1f}%</strong></div>
              <div class="efficiency-item"><span class="eff-label">Re-read Ratio</span><strong>{efficiency.get("reread_ratio", 0):.1f}%</strong></div>
              <div class="efficiency-item"><span class="eff-label">Failure Rate</span><strong>{efficiency.get("failure_rate_pct", 0):.1f}%</strong></div>
              <div class="efficiency-item"><span class="eff-label">Continuation Loops</span><strong>{efficiency.get("continuation_loops", 0)}</strong></div>
              <div class="efficiency-item"><span class="eff-label">Max-Token Stops</span><strong>{efficiency.get("max_tokens_stops", 0)}</strong></div>
              <div class="efficiency-item"><span class="eff-label">Tools/min</span><strong>{efficiency.get("tool_calls_per_minute", 0):.1f}</strong></div>
              <div class="efficiency-item"><span class="eff-label">Edits/min</span><strong>{efficiency.get("edits_per_minute", 0):.1f}</strong></div>
            </div>
          </article>
          <article class="callout">
            <h3>Stop Reasons</h3>
            {_list_block([f"{k}: {v}" for k, v in sorted(stop_reasons.items(), key=lambda item: (-item[1], item[0]))], "No stop reasons recorded.")}
          </article>
        </div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h2>Bash Activity</h2>
          <p>Categorized shell command distribution.</p>
        </div>
        <div class="callout-stack">
          <article class="callout">
            <h3>Command Categories</h3>
            {_list_block([f"{cat}: {cnt}" for cat, cnt in sorted(bash_categories.items(), key=lambda item: (-item[1], item[0]))], "No bash commands detected.")}
          </article>
          <article class="callout">
            <h3>Tool Failure Rates</h3>
            {_list_block([f"{name}: {rate:.1f}%" for name, rate in sorted(tool_failure_rate.items(), key=lambda item: (-item[1], item[0])) if rate > 0], "No tool failures detected.")}
          </article>
        </div>
      </section>
    </section>

    <section class="panel-grid">
      <section class="panel">
        <div class="panel-head">
          <h2>Event Timeline</h2>
          <p>First normalized events observed in the session.</p>
        </div>
        <div class="timeline">
          {_timeline_markup(events)}
        </div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h2>Read Heatmap</h2>
          <p>Files with strongest observed reading intensity.</p>
        </div>
        <div class="heat-grid">
          {_heatmap_markup(files)}
        </div>
      </section>
    </section>

    <section class="panel full-width">
      <div class="panel-head">
        <h2>Top Files</h2>
        <p>Sorted by observed read coverage, then edit activity.</p>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>File</th>
              <th>Lines Read</th>
              <th>Total Lines</th>
              <th>Coverage</th>
              <th>Edit Count</th>
              <th>Added</th>
              <th>Removed</th>
            </tr>
          </thead>
          <tbody>
            {_files_table(files)}
          </tbody>
        </table>
      </div>
    </section>

    <section class="panel full-width">
      <div class="panel-head">
        <h2>Summary JSON</h2>
        <p>Raw derived summary used to build this page.</p>
      </div>
      <pre class="json-block">{summary_json}</pre>
    </section>
  </main>
</body>
</html>
"""


def report_css() -> str:
    """Return the shared CSS for the static report."""
    return """
:root {
  --bg: #f5efe3;
  --bg-deep: #efe3cf;
  --surface: rgba(255, 252, 246, 0.82);
  --surface-strong: #fffaf1;
  --ink: #1d1b16;
  --muted: #6d675d;
  --line: rgba(64, 48, 28, 0.12);
  --accent: #b85c38;
  --accent-soft: #f4c9aa;
  --accent-deep: #6e2f1a;
  --success: #265c42;
  --shadow: 0 18px 60px rgba(84, 52, 20, 0.12);
}

* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
  color: var(--ink);
  background:
    radial-gradient(circle at top left, rgba(184, 92, 56, 0.12), transparent 26%),
    radial-gradient(circle at top right, rgba(110, 47, 26, 0.08), transparent 22%),
    linear-gradient(180deg, var(--bg), var(--bg-deep));
}

.page-shell {
  width: min(1680px, calc(100vw - 48px));
  max-width: calc(100vw - 48px);
  margin: 0 0 0 24px;
  padding: 32px 0 48px;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 18px 16px;
}

.page-shell > * {
  grid-column: 1 / -1;
}

.hero, .panel, .metric-card {
  background: var(--surface);
  backdrop-filter: blur(16px);
  border: 1px solid var(--line);
  box-shadow: var(--shadow);
}

.hero {
  display: grid;
  grid-template-columns: 1.6fr 0.9fr;
  gap: 24px;
  padding: 28px;
  border-radius: 28px;
}

.hero-copy, .hero-panel {
  min-width: 0;
}

.eyebrow {
  margin: 0 0 10px;
  font-size: 12px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--accent-deep);
}

h1, h2, h3, p { margin: 0; }
h1 {
  font-size: clamp(36px, 5vw, 62px);
  line-height: 0.95;
  letter-spacing: -0.04em;
  max-width: 100%;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.hero-text, .panel-head p, .metric-subtle, .artifact-label, .empty-state {
  color: var(--muted);
}

.hero-text {
  margin-top: 14px;
  max-width: 60ch;
  font-size: 16px;
  line-height: 1.55;
}

.hero-panel {
  align-self: stretch;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  gap: 10px;
  padding: 18px;
  border-radius: 22px;
  background: linear-gradient(180deg, rgba(255,255,255,0.65), rgba(244, 201, 170, 0.35));
  border: 1px solid rgba(184, 92, 56, 0.18);
}

.hero-panel code, .json-block {
  font-family: "SFMono-Regular", "Consolas", "Liberation Mono", monospace;
}

.hero-panel code {
  display: block;
  white-space: pre-wrap;
  word-break: break-word;
  padding: 12px 14px;
  border-radius: 16px;
  background: rgba(29, 27, 22, 0.06);
}

.stats-grid, .panel-grid {
  display: grid;
  grid-template-columns: subgrid;
  gap: 16px;
}

.stats-grid {
  margin-top: 0;
}

@media (min-width: 981px) {
  .stats-grid {
    grid-template-columns: subgrid;
  }
}

.metric-card {
  border-radius: 22px;
  padding: 18px;
}

.metric-card.primary {
  background: linear-gradient(135deg, rgba(184, 92, 56, 0.14), rgba(255, 250, 241, 0.85));
}

.metric-label {
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--muted);
}

.metric-value {
  margin-top: 8px;
  font-size: clamp(28px, 4vw, 44px);
  line-height: 1;
  font-weight: 700;
}

.panel-grid {
  align-items: start;
}

.panel-grid > .panel {
  grid-column: span 2;
}

.tool-grid {
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
}

.panel {
  border-radius: 28px;
  padding: 24px;
  min-width: 0;
  max-width: 100%;
}

.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: end;
  gap: 16px;
  margin-bottom: 18px;
}

.panel-head > * {
  min-width: 0;
}

.panel-head h2 {
  font-size: 28px;
  letter-spacing: -0.03em;
}

.tool-grid {
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
}

.session-card {
  display: block;
  text-decoration: none;
  color: inherit;
  background: linear-gradient(180deg, rgba(255,255,255,0.72), rgba(244, 201, 170, 0.14));
  border: 1px solid var(--line);
  border-radius: 22px;
  padding: 16px;
  min-height: 0;
  box-shadow: var(--shadow);
  transition: transform 160ms ease, border-color 160ms ease;
}

.session-card:hover {
  transform: translateY(-2px);
  border-color: rgba(184, 92, 56, 0.35);
}

.session-card-top {
  margin-bottom: 14px;
}

.session-subtitle {
  margin-top: 6px;
  color: var(--muted);
  line-height: 1.4;
  font-size: 15px;
}

.session-tech-id {
  margin-top: 12px;
  color: var(--muted);
  font-size: 11px;
  font-family: "SFMono-Regular", "Consolas", "Liberation Mono", monospace;
  line-height: 1.35;
  word-break: break-word;
  opacity: 0.72;
}

.session-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

.session-stats div {
  padding: 10px 8px;
  border-radius: 14px;
  background: rgba(255, 250, 241, 0.7);
  border: 1px solid var(--line);
  text-align: center;
}

.session-stats span, .heat-meta, .timeline-meta {
  color: var(--muted);
  font-size: 12px;
}

.session-stats strong {
  display: block;
  margin-top: 4px;
  font-size: 22px;
  line-height: 1;
}

.session-card h2 {
  font-size: clamp(24px, 2.1vw, 36px);
  line-height: 1.02;
  letter-spacing: -0.04em;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.session-grid {
  display: grid;
  gap: 10px;
}

.session-grid-head,
.session-row {
  display: grid;
  grid-template-columns: minmax(0, 1.8fr) 72px 140px 72px 72px 80px 72px 80px 100px;
  gap: 8px;
  align-items: center;
}

.session-grid-head {
  padding: 0 10px;
  color: var(--muted);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
}

.session-grid-body {
  display: grid;
  gap: 10px;
}

.session-row {
  text-decoration: none;
  color: inherit;
  padding: 14px 16px;
  border-radius: 20px;
  background: linear-gradient(180deg, rgba(255,255,255,0.72), rgba(244, 201, 170, 0.12));
  border: 1px solid var(--line);
  box-shadow: var(--shadow);
  transition: transform 160ms ease, border-color 160ms ease;
}

.session-row:hover {
  transform: translateY(-1px);
  border-color: rgba(184, 92, 56, 0.35);
}

.session-row-main {
  min-width: 0;
}

.session-row-kicker {
  margin-bottom: 8px;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.16em;
  color: var(--accent-deep);
}

.session-row-title {
  font-size: 22px;
  line-height: 1.05;
  letter-spacing: -0.04em;
  font-weight: 700;
}

.session-row-subtitle {
  margin-top: 8px;
  color: var(--muted);
  font-size: 14px;
  line-height: 1.35;
}

.session-row-context {
  margin-top: 8px;
  color: var(--ink);
  font-size: 13px;
  line-height: 1.45;
  opacity: 0.82;
}

.session-row-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.session-badge {
  display: inline-flex;
  align-items: center;
  padding: 6px 9px;
  border-radius: 999px;
  background: rgba(29, 27, 22, 0.06);
  border: 1px solid var(--line);
  color: var(--muted);
  font-size: 11px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.session-badge.source {
  background: rgba(184, 92, 56, 0.12);
  color: var(--accent-deep);
  border-color: rgba(184, 92, 56, 0.22);
}

.session-badge.warning {
  background: rgba(110, 47, 26, 0.12);
  color: var(--accent-deep);
  border-color: rgba(110, 47, 26, 0.2);
}

.session-row-metric {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 68px;
  border-radius: 16px;
  border: 1px solid var(--line);
  background: rgba(255, 250, 241, 0.74);
  font-size: 28px;
  font-weight: 700;
  line-height: 1;
}

.session-row-metric-text {
  padding: 10px;
  text-align: center;
  font-size: 14px;
  line-height: 1.35;
  font-weight: 600;
}

.session-row-metric-stack {
  flex-direction: column;
  gap: 6px;
  padding: 10px;
}

.session-row-metric-stack strong {
  font-size: 22px;
  line-height: 1;
}

.session-row-metric-stack span {
  color: var(--muted);
  font-size: 12px;
  font-weight: 500;
  line-height: 1.2;
}

.tool-card {
  min-height: 132px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.callout-stack {
  display: grid;
  gap: 14px;
  min-width: 0;
}

.timeline {
  display: grid;
  gap: 12px;
}

.timeline-item {
  display: grid;
  grid-template-columns: 20px 1fr;
  gap: 10px;
  align-items: start;
}

.timeline-dot {
  width: 12px;
  height: 12px;
  margin-top: 6px;
  border-radius: 999px;
  background: linear-gradient(135deg, var(--accent), #e69262);
  box-shadow: 0 0 0 5px rgba(184, 92, 56, 0.12);
}

.timeline-content {
  padding: 14px 16px;
  border-radius: 16px;
  background: rgba(255, 250, 241, 0.72);
  border: 1px solid var(--line);
}

.timeline-meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.timeline-type {
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.timeline-label {
  line-height: 1.45;
}

.heat-grid {
  display: grid;
  gap: 12px;
}

.heat-card {
  padding: 14px;
  border-radius: 18px;
  border: 1px solid var(--line);
  background: rgba(255, 250, 241, 0.7);
}

.heat-card.edited {
  background: linear-gradient(180deg, rgba(255, 250, 241, 0.8), rgba(244, 201, 170, 0.28));
}

.heat-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: start;
}

.heat-path {
  font-family: "SFMono-Regular", "Consolas", "Liberation Mono", monospace;
  font-size: 12px;
  line-height: 1.45;
  word-break: break-word;
}

.heat-badge {
  white-space: nowrap;
  font-size: 12px;
  padding: 6px 8px;
  border-radius: 999px;
  background: rgba(29, 27, 22, 0.06);
}

.heat-bar {
  margin: 12px 0 10px;
  width: 100%;
  height: 14px;
  border-radius: 999px;
  overflow: hidden;
  background: rgba(29, 27, 22, 0.08);
}

.heat-bar span {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--accent-deep), var(--accent), #efab7b);
}

.heat-meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.callout {
  padding: 16px;
  border-radius: 20px;
  background: var(--surface-strong);
  border: 1px solid var(--line);
  min-width: 0;
  max-width: 100%;
}

.callout h3 {
  margin-bottom: 10px;
  font-size: 15px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--accent-deep);
}

.inline-list {
  margin: 0;
  padding-left: 18px;
  display: grid;
  gap: 6px;
  min-width: 0;
  max-width: 100%;
}

.inline-list li {
  min-width: 0;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.efficiency-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 10px;
}

.efficiency-item {
  display: flex;
  flex-direction: column;
  padding: 8px 10px;
  border-radius: 12px;
  background: rgba(255, 250, 241, 0.7);
  border: 1px solid var(--line);
}

.eff-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--muted);
}

.efficiency-item strong {
  margin-top: 4px;
  font-size: 20px;
  line-height: 1;
}

.panel.full-width {
  grid-column: 1 / -1;
}

.table-wrap {
  overflow: auto;
  border-radius: 20px;
  border: 1px solid var(--line);
}

table {
  width: 100%;
  border-collapse: collapse;
  background: rgba(255, 250, 241, 0.75);
}

thead {
  background: rgba(29, 27, 22, 0.04);
}

th, td {
  text-align: left;
  padding: 14px 16px;
  border-bottom: 1px solid var(--line);
  vertical-align: middle;
}

th {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--muted);
}

.path-cell {
  max-width: 420px;
  word-break: break-word;
  font-family: "SFMono-Regular", "Consolas", "Liberation Mono", monospace;
  font-size: 13px;
}

.coverage-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.coverage-bar {
  width: 120px;
  height: 10px;
  border-radius: 999px;
  overflow: hidden;
  background: rgba(29, 27, 22, 0.08);
}

.coverage-bar span {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--accent), #e69262);
}

.json-block {
  overflow: auto;
  max-height: 420px;
  margin: 0;
  padding: 18px;
  border-radius: 20px;
  background: #1d1b16;
  color: #f5efe3;
  line-height: 1.5;
  font-size: 13px;
}

@media (max-width: 980px) {
  .page-shell {
    grid-template-columns: 1fr;
    width: calc(100vw - 20px);
    max-width: calc(100vw - 20px);
    margin-left: 10px;
    padding-top: 18px;
  }

  .hero {
    grid-template-columns: 1fr;
  }

  .stats-grid, .panel-grid {
    grid-template-columns: 1fr;
  }

  .panel-grid > .panel {
    grid-column: span 1;
  }

  .tool-grid {
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  }

  .session-grid-head {
    display: none;
  }

  .session-row {
    grid-template-columns: 1fr 1fr 1fr;
  }

  .session-row-main {
    grid-column: 1 / -1;
  }

  .session-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .hero, .panel, .metric-card {
    border-radius: 22px;
  }
}
"""
