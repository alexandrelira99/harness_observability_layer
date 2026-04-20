"""Live session detail dashboard for HOL server."""

from __future__ import annotations

import json
from html import escape
from typing import Any, Dict, List

from .guided_insights import (
    build_session_insights,
    build_session_executive_summary,
)


def _format_int(value: Any) -> str:
    return f"{int(value or 0):,}"


def _format_tokens(value: Any) -> str:
    count = int(value or 0)
    if count >= 1_000_000:
        return f"{count / 1_000_000:.2f}M"
    if count >= 1_000:
        return f"{count / 1_000:.1f}K"
    return str(count)


def _format_cost(value: Any) -> str:
    amount = float(value or 0)
    if amount < 0.01:
        return f"${amount:.4f}"
    return f"${amount:.2f}"


def _format_pct(value: Any) -> str:
    return f"{float(value or 0):.1f}%"


def _format_duration(seconds: float) -> str:
    seconds = float(seconds or 0)
    if seconds <= 0:
        return "0s"
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes = seconds / 60
    if minutes < 60:
        return f"{minutes:.1f}m"
    hours = minutes / 60
    return f"{hours:.1f}h"


def _kpi(label: str, value: str, sub: str) -> str:
    return f"""
      <article class="project-kpi-card">
        <div class="project-kpi-label">{escape(label)}</div>
        <div class="project-kpi-value">{escape(value)}</div>
        <div class="project-kpi-sub">{escape(sub)}</div>
      </article>
    """


def _model_class(model: str) -> str:
    lowered = model.lower()
    if "opus" in lowered or "gpt-5.4" in lowered or "gpt-4o" in lowered:
        return "model-opus"
    if "sonnet" in lowered or "gpt-5" in lowered or "gpt-4.1" in lowered:
        return "model-sonnet"
    if "haiku" in lowered or "mini" in lowered or "o4-mini" in lowered:
        return "model-haiku"
    return "model-unknown"


def _tool_rows(summary: Dict[str, Any]) -> str:
    tool_counts = summary.get("tool_calls_by_name") or {}
    tool_failures = summary.get("tool_failures_by_name") or {}
    tool_durations = summary.get("avg_tool_duration_by_name") or {}
    tool_failure_rates = summary.get("tool_failure_rate_by_name") or {}
    if not tool_counts and not tool_failures:
        return '<div class="empty-state">No tool calls detected.</div>'
    all_tools = sorted(
        set(tool_counts) | set(tool_failures),
        key=lambda t: (-(tool_counts.get(t, 0) + tool_failures.get(t, 0)), t),
    )
    rows = []
    for tool in all_tools:
        calls = tool_counts.get(tool, 0)
        fails = tool_failures.get(tool, 0)
        total = calls + fails
        avg_dur = tool_durations.get(tool)
        dur_text = f"{float(avg_dur):.2f}s" if avg_dur is not None else "—"
        fail_rate = tool_failure_rates.get(tool, 0)
        fail_class = (
            "fail-high" if fail_rate >= 20 else ("fail-mid" if fail_rate >= 5 else "")
        )
        rows.append(
            f"""
            <article class="rank-card">
              <div class="rank-card-main">
                <div class="rank-card-title">{escape(tool)}</div>
              </div>
              <div class="rank-card-meta">
                <div class="rank-metric">
                  <span class="rank-metric-label">Calls</span>
                  <span class="rank-metric-value">{calls}</span>
                </div>
                <div class="rank-metric">
                  <span class="rank-metric-label">Failures</span>
                  <span class="rank-metric-value {fail_class}">{fails}</span>
                </div>
                <div class="rank-metric">
                  <span class="rank-metric-label">Fail Rate</span>
                  <span class="rank-metric-value">{float(fail_rate):.1f}%</span>
                </div>
                <div class="rank-metric">
                  <span class="rank-metric-label">Avg Duration</span>
                  <span class="rank-metric-value">{dur_text}</span>
                </div>
              </div>
            </article>
            """
        )
    return "\n".join(rows)


def _skill_rows(summary: Dict[str, Any]) -> str:
    skill_loads = summary.get("skill_loads_by_name") or {}
    skill_attribution = summary.get("skill_attribution") or {}
    skills_without_followup = set(summary.get("skills_without_followup") or [])
    if not skill_loads:
        return '<div class="empty-state">No skills loaded in this session.</div>'
    rows = []
    for name, count in sorted(
        skill_loads.items(), key=lambda item: (-item[1], item[0])
    ):
        attr = skill_attribution.get(name) or {}
        tokens = int(attr.get("total_tokens", 0) or 0)
        tool_calls = int(attr.get("tool_call_count", 0) or 0)
        files_edited = int(attr.get("file_edit_count", 0) or 0)
        warning = " (no follow-up)" if name in skills_without_followup else ""
        rows.append(
            f"""
            <article class="rank-card">
              <div class="rank-card-main">
                <div class="rank-card-title">{escape(name)}{escape(warning)}</div>
              </div>
              <div class="rank-card-meta">
                <div class="rank-metric">
                  <span class="rank-metric-label">Loads</span>
                  <span class="rank-metric-value">{count}</span>
                </div>
                <div class="rank-metric">
                  <span class="rank-metric-label">Tokens</span>
                  <span class="rank-metric-value">{_format_tokens(tokens)}</span>
                </div>
                <div class="rank-metric">
                  <span class="rank-metric-label">Tool Calls</span>
                  <span class="rank-metric-value">{_format_int(tool_calls)}</span>
                </div>
                <div class="rank-metric">
                  <span class="rank-metric-label">Files Edited</span>
                  <span class="rank-metric-value">{_format_int(files_edited)}</span>
                </div>
              </div>
            </article>
            """
        )
    return "\n".join(rows)


def _prompt_group_rows(items: List[Dict[str, Any]]) -> str:
    if not items:
        return '<div class="empty-state">No prompt groups recorded.</div>'
    rows = []
    for item in items:
        prompt = str(item.get("prompt_excerpt") or item.get("prompt") or "")[:120]
        driver = str(item.get("driver_name") or "unattributed")
        rows.append(
            f"""
            <article class="rank-card">
              <div class="rank-card-index">{int(item.get("ordinal", 0) or 0)}</div>
              <div class="rank-card-main">
                <div class="rank-card-title">{escape(prompt)}</div>
                <div class="rank-card-subtitle">driver: {escape(driver)}</div>
              </div>
              <div class="rank-card-meta">
                <div class="rank-metric">
                  <span class="rank-metric-label">Tokens</span>
                  <span class="rank-metric-value">{_format_tokens(item.get("total_tokens"))}</span>
                </div>
                <div class="rank-metric">
                  <span class="rank-metric-label">Cost</span>
                  <span class="rank-metric-value">{_format_cost(item.get("estimated_cost_usd"))}</span>
                </div>
                <div class="rank-metric">
                  <span class="rank-metric-label">Tools</span>
                  <span class="rank-metric-value">{_format_int(item.get("tool_call_count"))}</span>
                </div>
                <div class="rank-metric">
                  <span class="rank-metric-label">Duration</span>
                  <span class="rank-metric-value">{_format_duration(item.get("duration_seconds"))}</span>
                </div>
              </div>
            </article>
            """
        )
    return "\n".join(rows)


def _turn_rows(items: List[Dict[str, Any]]) -> str:
    if not items:
        return '<div class="empty-state">No turns recorded.</div>'
    rows = []
    for item in items:
        prompt = str(item.get("prompt_excerpt") or item.get("prompt") or "")[:120]
        driver = str(item.get("driver_name") or "unattributed")
        rows.append(
            f"""
            <article class="rank-card">
              <div class="rank-card-index">{int(item.get("ordinal", 0) or 0)}</div>
              <div class="rank-card-main">
                <div class="rank-card-title">{escape(prompt)}</div>
                <div class="rank-card-subtitle">driver: {escape(driver)}</div>
              </div>
              <div class="rank-card-meta">
                <div class="rank-metric">
                  <span class="rank-metric-label">Tokens</span>
                  <span class="rank-metric-value">{_format_tokens(item.get("total_tokens"))}</span>
                </div>
                <div class="rank-metric">
                  <span class="rank-metric-label">Cost</span>
                  <span class="rank-metric-value">{_format_cost(item.get("estimated_cost_usd"))}</span>
                </div>
                <div class="rank-metric">
                  <span class="rank-metric-label">Tools</span>
                  <span class="rank-metric-value">{_format_int(item.get("tool_call_count"))}</span>
                </div>
                <div class="rank-metric">
                  <span class="rank-metric-label">Failures</span>
                  <span class="rank-metric-value">{_format_int(item.get("tool_failure_count"))}</span>
                </div>
              </div>
            </article>
            """
        )
    return "\n".join(rows)


def _insight_card(card: Dict[str, str]) -> str:
    severity = escape(card.get("severity") or "medium")
    recommendation = card.get("recommendation")
    rec_markup = (
        f'<p class="insight-recommendation"><strong>Action:</strong> {escape(recommendation)}</p>'
        if recommendation
        else ""
    )
    return f"""
      <article class="insight-card severity-{severity}">
        <div class="insight-kicker">{severity.title()} priority</div>
        <h3>{escape(card.get("title") or "")}</h3>
        <p>{escape(card.get("interpretation") or "")}</p>
        <p class="insight-evidence">{escape(card.get("evidence") or "")}</p>
        {rec_markup}
      </article>
    """


def _file_rows(summary: Dict[str, Any]) -> str:
    files = summary.get("files") or {}
    if not files:
        return '<div class="empty-state">No file activity detected.</div>'
    sorted_files = sorted(
        files.items(),
        key=lambda item: (
            -(item[1].get("edit_count") or 0),
            -(item[1].get("union_lines_read") or 0),
            item[0],
        ),
    )[:20]
    rows = []
    for path, meta in sorted_files:
        edits = int(meta.get("edit_count") or 0)
        lines_read = int(meta.get("union_lines_read") or 0)
        coverage = meta.get("read_coverage_pct")
        coverage_text = "—" if coverage is None else f"{float(coverage):.1f}%"
        added = int(meta.get("added_lines") or 0)
        removed = int(meta.get("removed_lines") or 0)
        edited_badge = "edited" if edits > 0 else ""
        rows.append(
            f"""
            <article class="rank-card file-row {edited_badge}">
              <div class="rank-card-main">
                <div class="rank-card-title file-path">{escape(path)}</div>
              </div>
              <div class="rank-card-meta">
                <div class="rank-metric">
                  <span class="rank-metric-label">Lines Read</span>
                  <span class="rank-metric-value">{_format_int(lines_read)}</span>
                </div>
                <div class="rank-metric">
                  <span class="rank-metric-label">Coverage</span>
                  <span class="rank-metric-value">{coverage_text}</span>
                </div>
                <div class="rank-metric">
                  <span class="rank-metric-label">Edits</span>
                  <span class="rank-metric-value">{edits}</span>
                </div>
                <div class="rank-metric">
                  <span class="rank-metric-label">+/- Lines</span>
                  <span class="rank-metric-value">+{added}/-{removed}</span>
                </div>
              </div>
            </article>
            """
        )
    return "\n".join(rows)


def _token_breakdown_bar(summary: Dict[str, Any]) -> str:
    input_t = int(summary.get("total_input_tokens", 0) or 0)
    output_t = int(summary.get("total_output_tokens", 0) or 0)
    cache_r = int(summary.get("total_cache_read_tokens", 0) or 0)
    cache_w = int(summary.get("total_cache_creation_tokens", 0) or 0)
    total = input_t + output_t + cache_r + cache_w
    if total == 0:
        return '<div class="empty-state">No token usage recorded.</div>'
    pct_input = (input_t / total) * 100
    pct_output = (output_t / total) * 100
    pct_cache_r = (cache_r / total) * 100
    pct_cache_w = (cache_w / total) * 100
    return f"""
    <div class="token-bar-container">
      <div class="token-bar">
        <div class="token-segment seg-input" style="width:{pct_input:.1f}%"><span>Input {_format_tokens(input_t)}</span></div>
        <div class="token-segment seg-output" style="width:{pct_output:.1f}%"><span>Output {_format_tokens(output_t)}</span></div>
        <div class="token-segment seg-cache-read" style="width:{pct_cache_r:.1f}%"><span>Cache R {_format_tokens(cache_r)}</span></div>
        <div class="token-segment seg-cache-write" style="width:{pct_cache_w:.1f}%"><span>Cache W {_format_tokens(cache_w)}</span></div>
      </div>
      <div class="token-bar-legend">
        <span class="legend-item"><span class="legend-dot seg-input"></span>Input {pct_input:.1f}%</span>
        <span class="legend-item"><span class="legend-dot seg-output"></span>Output {pct_output:.1f}%</span>
        <span class="legend-item"><span class="legend-dot seg-cache-read"></span>Cache Read {pct_cache_r:.1f}%</span>
        <span class="legend-item"><span class="legend-dot seg-cache-write"></span>Cache Write {pct_cache_w:.1f}%</span>
      </div>
    </div>
    """


def _event_timeline(events: List[Dict[str, Any]], limit: int = 40) -> str:
    if not events:
        return '<div class="empty-state">No events recorded.</div>'
    selected = events[:limit]
    items = []
    for event in selected:
        event_type = str(event.get("event_type", "unknown"))
        ts = str(event.get("ts", ""))
        payload = event.get("payload") or {}
        if event_type in {
            "tool_call_started",
            "tool_call_finished",
            "tool_call_failed",
        }:
            label = str(payload.get("tool_name") or event_type)
        elif event_type == "file_read":
            label = str(payload.get("path") or event_type)
        elif event_type == "file_edit":
            label = str(payload.get("path") or event_type)
        elif event_type == "agent_message":
            label = "assistant message"
        elif event_type == "user_message":
            label = "user message"
        elif event_type == "skill_loaded":
            label = f"skill: {payload.get('skill_name', 'unknown')}"
        else:
            label = event_type
        etype_class = event_type.replace("_", "-")
        items.append(
            f"""
            <article class="timeline-item">
              <div class="timeline-dot type-{etype_class}"></div>
              <div class="timeline-content">
                <div class="timeline-meta">
                  <span class="timeline-type">{escape(event_type)}</span>
                  <span class="timeline-ts">{escape(ts)}</span>
                </div>
                <div class="timeline-label">{escape(label)}</div>
              </div>
            </article>
            """
        )
    return "\n".join(items)


def _shared_dashboard_css() -> str:
    return """
    :root {
      color-scheme: dark;
      --bg: #0b0f14;
      --bg-elevated: #111827;
      --panel: rgba(15, 23, 42, 0.88);
      --panel-border: rgba(148, 163, 184, 0.14);
      --text-strong: #f8fafc;
      --text: #e2e8f0;
      --text-muted: #94a3b8;
      --accent: #f97316;
      --accent-soft: rgba(249, 115, 22, 0.12);
      --shadow: 0 18px 50px rgba(2, 6, 23, 0.35);
      --radius: 24px;
      --font-sans: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      --font-mono: "SFMono-Regular", "JetBrains Mono", ui-monospace, monospace;
    }
    * { box-sizing: border-box; }
    html, body {
      margin: 0;
      min-height: 100%;
      background:
        radial-gradient(circle at top left, rgba(59,130,246,0.10), transparent 30%),
        radial-gradient(circle at top right, rgba(45,212,191,0.08), transparent 28%),
        linear-gradient(180deg, #08101a 0%, #0b0f14 100%);
      color: var(--text);
      font-family: var(--font-sans);
    }
    body { line-height: 1.5; }
    a { color: inherit; }
    code { font-family: var(--font-mono); color: var(--text-strong); font-size: 0.95rem; }
    h1, h2, h3, p { margin-top: 0; }
    h1 { font-size: clamp(2.2rem, 4vw, 3.6rem); line-height: 1.02; letter-spacing: -0.05em; margin-bottom: 18px; color: var(--text-strong); }
    h2 { color: var(--text-strong); }
    h3 { color: var(--text-strong); }
    .eyebrow { margin: 0 0 10px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.08em; font-size: 0.8rem; font-weight: 700; }
    .hero-text { color: var(--text); max-width: 72ch; line-height: 1.6; }
    .artifact-label { color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.08em; font-size: 0.78rem; font-weight: 700; margin-bottom: 10px; }
    .empty-state { color: var(--text-muted); padding: 18px; border: 1px dashed rgba(148,163,184,0.16); border-radius: 16px; background: rgba(255,255,255,0.02); }
    .project-shell { max-width: min(1760px, calc(100vw - 40px)); margin: 0 auto; padding: 32px 24px 64px; }
    .project-hero { display: grid; grid-template-columns: minmax(0, 1.8fr) minmax(280px, 0.9fr); gap: 18px; margin-bottom: 28px; }
    .project-hero-card { background: var(--panel); border: 1px solid var(--panel-border); border-radius: 24px; padding: 24px; box-shadow: var(--shadow); }
    .project-nav { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 18px; }
    .project-nav a { display: inline-flex; align-items: center; justify-content: center; min-width: 140px; padding: 10px 14px; border-radius: 999px; text-decoration: none; color: var(--text-strong); background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); }
    .project-nav a.primary { background: linear-gradient(135deg, rgba(96,165,250,0.25), rgba(45,212,191,0.18)); border-color: rgba(125,211,252,0.28); }
    .project-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 26px; }
    .project-kpi-card { background: linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.02)); border: 1px solid rgba(255,255,255,0.08); border-radius: 22px; padding: 18px 18px 16px; min-height: 132px; box-shadow: var(--shadow); display: flex; flex-direction: column; justify-content: space-between; overflow: hidden; }
    .project-kpi-label { font-size: 0.82rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: var(--text-muted); margin-bottom: 10px; }
    .project-kpi-value { font-size: clamp(1.55rem, 2vw, 2.4rem); line-height: 1; font-weight: 800; letter-spacing: -0.04em; color: var(--text-strong); margin-bottom: 10px; overflow-wrap: anywhere; }
    .project-kpi-sub { color: var(--text-muted); line-height: 1.45; max-width: 28ch; }
    .project-section { background: var(--panel); border: 1px solid var(--panel-border); border-radius: 24px; padding: 22px; box-shadow: var(--shadow); margin-bottom: 24px; }
    .project-section h2 { margin: 0 0 14px; font-size: 1.1rem; }
    .project-section-copy { color: var(--text-muted); margin: 0 0 14px; max-width: 62ch; line-height: 1.5; }
    .project-insight-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px; }
    .project-insight-card { border-radius: 18px; padding: 16px; border: 1px solid rgba(255,255,255,0.08); background: rgba(255,255,255,0.025); }
    .project-insight-card h3 { margin: 0 0 10px; font-size: 1rem; }
    .project-insight-card p { margin: 0 0 10px; color: var(--text-muted); }
    .project-insight-evidence { color: var(--text-strong) !important; }
    .rank-list, .session-list { display: flex; flex-direction: column; gap: 12px; }
    .rank-card, .session-card {
      display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(320px, 1.2fr); gap: 16px; align-items: center;
      padding: 16px 18px; border-radius: 18px; border: 1px solid rgba(255,255,255,0.06); background: rgba(255,255,255,0.02); overflow: hidden;
    }
    .rank-card.indexed { grid-template-columns: 52px minmax(0, 1.35fr) minmax(320px, 1.2fr); }
    .rank-card-index { color: var(--text-muted); font-size: 1.05rem; font-weight: 700; font-variant-numeric: tabular-nums; text-align: center; }
    .rank-card-main { min-width: 0; overflow: hidden; }
    .rank-card-title { font-size: 1rem; font-weight: 650; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; text-overflow: ellipsis; }
    .rank-card-subtitle { margin-top: 6px; font-size: 0.82rem; color: var(--text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .rank-card-meta { min-width: 0; display: flex; align-items: center; justify-content: flex-end; gap: 10px; flex-wrap: wrap; }
    .rank-metric { min-width: 72px; padding: 8px 10px; border-radius: 12px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.05); }
    .rank-metric-label { display: block; font-size: 10px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: var(--text-muted); margin-bottom: 4px; }
    .rank-metric-value { display: block; font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, monospace); font-size: 13px; font-weight: 700; white-space: nowrap; font-variant-numeric: tabular-nums; }
    .fail-high { color: #f87171; }
    .fail-mid { color: #fbbf24; }
    .file-path { font-family: var(--font-mono); font-size: 0.88rem; }
    .file-row.edited { border-left: 3px solid rgba(16,185,129,0.5); }
    .model-badge { display: inline-flex; align-items: center; gap: 5px; padding: 3px 10px; border-radius: 20px; font-size: 12px; font-weight: 600; white-space: nowrap; }
    .model-opus { background: rgba(59,130,246,0.14); color: #93c5fd; border: 1px solid rgba(59,130,246,0.22); }
    .model-sonnet { background: rgba(16,185,129,0.12); color: #86efac; border: 1px solid rgba(16,185,129,0.20); }
    .model-haiku { background: rgba(249,115,22,0.12); color: #fdba74; border: 1px solid rgba(249,115,22,0.20); }
    .model-unknown { background: rgba(148,163,184,0.12); color: #cbd5e1; border: 1px solid rgba(148,163,184,0.18); }
    .model-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; background: currentColor; opacity: 0.9; }
    .project-split { display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 18px; }
    .token-bar-container { margin-top: 8px; }
    .token-bar { display: flex; height: 32px; border-radius: 12px; overflow: hidden; background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.06); }
    .token-segment { display: flex; align-items: center; justify-content: center; overflow: hidden; padding: 0 8px; font-size: 11px; font-weight: 600; color: var(--text-strong); white-space: nowrap; }
    .seg-input { background: rgba(59,130,246,0.35); }
    .seg-output { background: rgba(16,185,129,0.35); }
    .seg-cache-read { background: rgba(168,85,247,0.35); }
    .seg-cache-write { background: rgba(251,191,36,0.35); }
    .token-bar-legend { display: flex; gap: 16px; margin-top: 10px; flex-wrap: wrap; font-size: 12px; color: var(--text-muted); }
    .legend-item { display: inline-flex; align-items: center; gap: 6px; }
    .legend-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
    .timeline { display: grid; gap: 10px; max-height: 640px; overflow-y: auto; padding-right: 8px; }
    .timeline-item { display: grid; grid-template-columns: 20px 1fr; gap: 10px; align-items: start; }
    .timeline-dot { width: 12px; height: 12px; margin-top: 6px; border-radius: 999px; background: linear-gradient(135deg, var(--accent), #e69262); box-shadow: 0 0 0 5px rgba(249,115,22,0.12); }
    .timeline-dot.type-tool-call-started { background: linear-gradient(135deg, #60a5fa, #3b82f6); box-shadow: 0 0 0 5px rgba(59,130,246,0.12); }
    .timeline-dot.type-tool-call-finished { background: linear-gradient(135deg, #10b981, #059669); box-shadow: 0 0 0 5px rgba(16,185,129,0.12); }
    .timeline-dot.type-tool-call-failed { background: linear-gradient(135deg, #f87171, #ef4444); box-shadow: 0 0 0 5px rgba(248,113,113,0.12); }
    .timeline-dot.type-file-read { background: linear-gradient(135deg, #a78bfa, #7c3aed); box-shadow: 0 0 0 5px rgba(167,139,250,0.12); }
    .timeline-dot.type-file-edit { background: linear-gradient(135deg, #fbbf24, #d97706); box-shadow: 0 0 0 5px rgba(251,191,36,0.12); }
    .timeline-dot.type-skill-loaded { background: linear-gradient(135deg, #2dd4bf, #14b8a6); box-shadow: 0 0 0 5px rgba(45,212,191,0.12); }
    .timeline-content { padding: 12px 14px; border-radius: 14px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); }
    .timeline-meta { display: flex; justify-content: space-between; gap: 12px; margin-bottom: 6px; }
    .timeline-type { text-transform: uppercase; letter-spacing: 0.08em; font-size: 11px; font-weight: 700; color: var(--text-muted); }
    .timeline-ts { font-family: var(--font-mono); font-size: 11px; color: var(--text-muted); }
    .timeline-label { line-height: 1.45; font-size: 0.92rem; }
    .efficiency-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 10px; }
    .efficiency-item { display: flex; flex-direction: column; padding: 10px 12px; border-radius: 12px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.05); }
    .eff-label { font-size: 11px; text-transform: uppercase; letter-spacing: 0.1em; color: var(--text-muted); }
    .efficiency-item strong { margin-top: 4px; font-size: 20px; line-height: 1; }
    .eff-good { border-color: rgba(16,185,129,0.35); background: rgba(16,185,129,0.06); }
    .eff-good strong { color: #86efac; }
    .eff-warn { border-color: rgba(251,191,36,0.35); background: rgba(251,191,36,0.06); }
    .eff-warn strong { color: #fbbf24; }
    .eff-bad { border-color: rgba(248,113,113,0.35); background: rgba(248,113,113,0.06); }
    .eff-bad strong { color: #f87171; }
    .eff-good-label { color: #86efac; }
    .eff-warn-label { color: #fbbf24; }
    .eff-bad-label { color: #f87171; }
    .insight-card { border-radius: 18px; padding: 16px; border: 1px solid rgba(255,255,255,0.08); background: rgba(255,255,255,0.025); }
    .insight-card.severity-high { border-color: rgba(248,113,113,0.4); background: linear-gradient(135deg, rgba(248,113,113,0.10), rgba(251,191,36,0.05)); }
    .insight-card.severity-medium { border-color: rgba(251,191,36,0.3); background: rgba(251,191,36,0.04); }
    .insight-card.severity-info { border-color: rgba(96,165,250,0.22); }
    .insight-card.severity-low { border-color: rgba(16,185,129,0.22); }
    .insight-kicker { color: var(--text-muted); font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px; font-weight: 700; }
    .insight-card h3 { margin: 0 0 10px; font-size: 1rem; }
    .insight-card p { margin: 0 0 10px; color: var(--text-muted); }
    .insight-evidence { color: var(--text-strong) !important; }
    .insight-recommendation { margin-bottom: 0 !important; color: var(--text) !important; }
    .executive-summary { font-size: 1.05rem; line-height: 1.55; color: var(--text-strong); }
    @media (max-width: 1100px) {
      .project-hero, .project-split { grid-template-columns: 1fr; }
    }
    @media (max-width: 720px) {
      .project-grid { grid-template-columns: 1fr; }
      .project-shell { padding-inline: 16px; max-width: calc(100vw - 16px); }
      .rank-card, .session-card { grid-template-columns: minmax(0, 1fr); align-items: start; }
      .rank-card-meta { justify-content: flex-start; }
    }
    """


def _eff_item(label: str, value: str, *, severity: str = "neutral") -> str:
    return f'<div class="efficiency-item eff-{severity}"><span class="eff-label">{escape(label)}</span><strong>{escape(value)}</strong></div>'


def _eff_threshold(
    value: float, *, good_max: float, warn_max: float, inverted: bool = False
) -> str:
    if inverted:
        if value <= good_max:
            return "good"
        if value <= warn_max:
            return "warn"
        return "bad"
    if value >= warn_max:
        return "good"
    if value >= good_max:
        return "warn"
    return "bad"


def build_session_dashboard_html(
    session_name: str,
    session_data: Dict[str, Any],
) -> str:
    """Render a detailed session view page for the live server."""
    summary = session_data.get("summary") or {}
    metadata = session_data.get("metadata") or {}
    prompt_groups = session_data.get("prompt_groups") or []
    turns = session_data.get("turns") or []
    events = session_data.get("events") or []

    display_title = str(metadata.get("display_title") or session_name)
    display_subtitle = str(metadata.get("display_subtitle") or "")
    source_name = str(metadata.get("source_name") or "Imported")
    model = str(summary.get("model") or "unknown")
    started_at = str(metadata.get("started_at") or "")
    technical_id = str(metadata.get("technical_id") or session_name)

    executive_summary = build_session_executive_summary(summary)
    insights = build_session_insights(summary)

    insight_markup = "\n".join(_insight_card(card) for card in insights) or (
        '<div class="empty-state">No session insights triggered.</div>'
    )

    efficiency = summary.get("efficiency_indicators") or {}
    eff_ewr = float(efficiency.get("edited_without_read_ratio", 0) or 0)
    eff_reread = float(efficiency.get("reread_ratio", 0) or 0)
    eff_fail = float(efficiency.get("failure_rate_pct", 0) or 0)
    eff_loops = int(efficiency.get("continuation_loops", 0) or 0)
    eff_maxstop = int(efficiency.get("max_tokens_stops", 0) or 0)
    eff_tpm = float(efficiency.get("tool_calls_per_minute", 0) or 0)
    eff_epm = float(efficiency.get("edits_per_minute", 0) or 0)
    eff_conc = int(summary.get("max_concurrent_tool_calls", 0) or 0)

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(display_title)} · Session Detail · Harness Observability</title>
  <style>
    {_shared_dashboard_css()}
  </style>
</head>
<body>
  <main class="project-shell">
    <section class="project-hero">
      <div class="project-hero-card">
        <p class="eyebrow">Session Detail · {escape(source_name)}</p>
        <h1>{escape(display_title)}</h1>
        <p class="hero-text executive-summary">{escape(executive_summary)}</p>
        <p class="hero-text" style="color:var(--text-muted);margin-top:8px;">{escape(display_subtitle)}</p>
        <div class="project-nav">
          <a class="primary" href="/">Project Dashboard</a>
          <a href="/api/data">API Data</a>
        </div>
      </div>
      <div class="project-hero-card">
        <div class="artifact-label">Session</div>
        <code style="display:block;padding:12px;border-radius:12px;background:rgba(255,255,255,0.04);margin-bottom:12px;word-break:break-all;">{escape(technical_id)}</code>
        <div class="artifact-label">Model</div>
        <span class="model-badge {_model_class(model)}"><span class="model-dot"></span>{escape(model)}</span>
        <div style="margin-top:12px;">
          <div class="artifact-label">Started</div>
          <code>{escape(started_at or "unknown")}</code>
        </div>
      </div>
    </section>

    <section class="project-grid">
      {_kpi("Total Tokens", _format_tokens(summary.get("total_tokens")), f"input {_format_tokens(summary.get('total_input_tokens'))} / output {_format_tokens(summary.get('total_output_tokens'))}")}
      {_kpi("Estimated Cost", _format_cost(summary.get("estimated_cost_usd")), f"cache hit {_format_pct(summary.get('cache_hit_rate_pct'))}")}
      {_kpi("Tool Calls", _format_int(summary.get("total_tool_calls")), f"{_format_int(summary.get('total_failures'))} failures ({_format_pct(summary.get('failure_rate_pct'))})")}
      {_kpi("Duration", _format_duration(summary.get("session_duration_seconds")), f"{_format_int(summary.get('user_message_count'))} turns / {_format_int(summary.get('agent_message_count'))} responses")}
      {_kpi("Files Read", _format_int(summary.get("distinct_files_read")), f"{_format_int(summary.get('files_created'))} created / {_format_int(summary.get('files_modified'))} modified")}
      {_kpi("Skills Loaded", _format_int(summary.get("distinct_skills_loaded")), f"{_format_int(summary.get('skill_load_count'))} total loads")}
    </section>

    <section class="project-section">
      <h2>Token Breakdown</h2>
      <p class="project-section-copy">Distribution of token consumption across input, output, and cache categories.</p>
      {_token_breakdown_bar(summary)}
    </section>

    <section class="project-section">
      <h2>Event Timeline</h2>
      <p class="project-section-copy">Chronological flow of the first {min(len(events), 40)} events in this session.</p>
      <div class="timeline">
        {_event_timeline(events)}
      </div>
    </section>

    <section class="project-section">
      <h2>Insights</h2>
      <p class="project-section-copy">Prioritized observations about session behavior with recommended actions.</p>
      <div class="project-insight-grid">
        {insight_markup}
      </div>
    </section>

    <section class="project-section">
      <h2>Tool Calling Breakdown</h2>
      <p class="project-section-copy">Each tool used in this session with call count, failures, failure rate, and average duration.</p>
      <div class="rank-list">
        {_tool_rows(summary)}
      </div>
    </section>

    <section class="project-section">
      <h2>Efficiency Indicators</h2>
      <p class="project-section-copy">Composite signals of session health. Color indicates relative health: <span class="eff-good-label">good</span>, <span class="eff-warn-label">attention</span>, <span class="eff-bad-label">concerning</span>.</p>
      <div class="efficiency-grid">
        {_eff_item("Edited w/o Read", f"{eff_ewr:.1f}%", severity=_eff_threshold(eff_ewr, good_max=10, warn_max=30, inverted=True))}
        {_eff_item("Re-read Ratio", f"{eff_reread:.1f}%", severity=_eff_threshold(eff_reread, good_max=15, warn_max=40, inverted=True))}
        {_eff_item("Failure Rate", f"{eff_fail:.1f}%", severity=_eff_threshold(eff_fail, good_max=3, warn_max=10, inverted=True))}
        {_eff_item("Continuation Loops", str(eff_loops), severity="bad" if eff_loops >= 2 else ("warn" if eff_loops >= 1 else "good"))}
        {_eff_item("Max-Token Stops", str(eff_maxstop), severity="bad" if eff_maxstop >= 2 else ("warn" if eff_maxstop >= 1 else "good"))}
        {_eff_item("Tools/min", f"{eff_tpm:.1f}", severity=_eff_threshold(eff_tpm, good_max=1, warn_max=3))}
        {_eff_item("Edits/min", f"{eff_epm:.1f}", severity=_eff_threshold(eff_epm, good_max=0.5, warn_max=1.5))}
        {_eff_item("Max Concurrent", str(eff_conc), severity="neutral")}
      </div>
    </section>

    <section class="project-section">
      <h2>Skills Used</h2>
      <p class="project-section-copy">Skills loaded during this session with attributed tokens, tool calls, and file edits.</p>
      <div class="rank-list">
        {_skill_rows(summary)}
      </div>
    </section>

    <section class="project-section">
      <h2>File Activity</h2>
      <p class="project-section-copy">Files read and edited in this session, sorted by edit count then lines read.</p>
      <div class="rank-list">
        {_file_rows(summary)}
      </div>
    </section>

    <section class="project-split">
      <section class="project-section">
        <h2>Prompt Groups</h2>
        <p class="project-section-copy">User prompts grouped with their accumulated cost and tool activity.</p>
        <div class="rank-list">
          {_prompt_group_rows(prompt_groups)}
        </div>
      </section>

      <section class="project-section">
        <h2>Turns</h2>
        <p class="project-section-copy">Individual turns with cost and failure breakdown.</p>
        <div class="rank-list">
          {_turn_rows(turns)}
        </div>
      </section>
    </section>

  </main>
</body>
</html>
"""
