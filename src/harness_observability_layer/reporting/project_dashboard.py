"""Static project dashboard for HOL imported sessions."""

from __future__ import annotations

import re
from html import escape
from typing import Any, Dict, List

from .guided_insights import (
    build_project_cost_insights,
    build_project_overview_insights,
    build_project_prompt_insights,
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


def _clean_prompt(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(
        r"^file://\S+?(?:\.html?|\.md|\.json|\.jsonl|\.py|\.txt)\b\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\s+", " ", text).strip()
    return text or "(no prompt)"


def _model_class(model: str) -> str:
    lowered = model.lower()
    if "opus" in lowered or "gpt-5.4" in lowered or "gpt-4o" in lowered:
        return "model-opus"
    if "sonnet" in lowered or "gpt-5" in lowered or "gpt-4.1" in lowered:
        return "model-sonnet"
    if "haiku" in lowered or "mini" in lowered or "o4-mini" in lowered:
        return "model-haiku"
    return "model-unknown"


def _kpi(label: str, value: str, sub: str) -> str:
    return f"""
      <article class="project-kpi-card">
        <div class="project-kpi-label">{escape(label)}</div>
        <div class="project-kpi-value">{escape(value)}</div>
        <div class="project-kpi-sub">{escape(sub)}</div>
      </article>
    """


def _insight_card(card: Dict[str, str]) -> str:
    severity = escape(card.get("severity") or "medium")
    recommendation = card.get("recommendation")
    recommendation_markup = (
        f'<p class="project-insight-recommendation"><strong>Recommendation:</strong> {escape(recommendation)}</p>'
        if recommendation
        else ""
    )
    return f"""
      <article class="project-insight-card severity-{severity}">
        <div class="project-insight-kicker">{escape(severity.title())} priority</div>
        <h3>{escape(card.get("title") or "")}</h3>
        <p>{escape(card.get("interpretation") or "")}</p>
        <p class="project-insight-evidence">{escape(card.get("evidence") or "")}</p>
        {recommendation_markup}
      </article>
    """


def _top_rows(
    items: List[Dict[str, Any]], *, heading_kind: str, show_actions: bool = True
) -> str:
    rows = []
    for item in items[:10]:
        prompt = _clean_prompt(item.get("prompt_excerpt") or item.get("prompt"))
        session_name = str(item.get("session_name") or "")
        session_relpath = f"./../sessions/{session_name}/index.html"
        model = str(item.get("model") or "unknown")
        prompt_title = escape(prompt, quote=True)
        session_title = escape(session_name, quote=True)
        action_href = escape(session_relpath, quote=True) if session_relpath else ""
        action_markup = (
            f'<div class="rank-card-action"><a class="table-link action-link" href="{action_href}">Open</a></div>'
            if action_href and show_actions
            else ""
        )
        rows.append(
            f"""
            <article class="rank-card">
              <div class="rank-card-index">{int(item.get('ordinal', 0) or 0)}</div>
              <div class="rank-card-main">
                <div class="rank-card-title" title="{prompt_title}">{escape(prompt)}</div>
                <div class="rank-card-subtitle" title="{session_title}">{escape(session_name)}</div>
              </div>
              <div class="rank-card-meta">
                <span class="model-badge {_model_class(model)}"><span class="model-dot"></span>{escape(model)}</span>
                <div class="rank-metric">
                  <span class="rank-metric-label">Tokens</span>
                  <span class="rank-metric-value">{_format_tokens(item.get('total_tokens'))}</span>
                </div>
                <div class="rank-metric">
                  <span class="rank-metric-label">Cost</span>
                  <span class="rank-metric-value">{_format_cost(item.get('estimated_cost_usd'))}</span>
                </div>
                <div class="rank-metric">
                  <span class="rank-metric-label">Tools</span>
                  <span class="rank-metric-value">{_format_int(item.get('tool_call_count'))}</span>
                </div>
              </div>
              {action_markup}
            </article>
            """
        )
    if rows:
        return "\n".join(rows)
    return f'<div class="empty-state">No ranked {escape(heading_kind)} data yet.</div>'


def _session_rows(items: List[Dict[str, Any]], *, show_actions: bool = True) -> str:
    rows = []
    for item in items[:8]:
        action_href = escape(str(item.get("guided_report_relpath") or ""), quote=True)
        action_markup = (
            f'<div class="rank-card-action"><a class="table-link action-link" href="{action_href}">Inspect</a></div>'
            if action_href and show_actions
            else ""
        )
        rows.append(
            f"""
            <article class="session-card">
              <div class="session-card-main">
                <div class="rank-card-title" title="{escape(str(item.get('display_title') or item.get('session_name') or 'Session'), quote=True)}">{escape(str(item.get('display_title') or item.get('session_name') or 'Session'))}</div>
                <div class="rank-card-subtitle" title="{escape(str(item.get('display_subtitle') or item.get('session_name') or ''), quote=True)}">{escape(str(item.get('display_subtitle') or item.get('session_name') or ''))}</div>
              </div>
              <div class="rank-card-meta">
                <span class="model-badge model-unknown"><span class="model-dot"></span>{escape(str(item.get('source_name') or 'Imported'))}</span>
                <div class="rank-metric">
                  <span class="rank-metric-label">Cost</span>
                  <span class="rank-metric-value">{_format_cost(item.get('estimated_cost_usd'))}</span>
                </div>
                <div class="rank-metric">
                  <span class="rank-metric-label">Tokens</span>
                  <span class="rank-metric-value">{_format_tokens(item.get('total_tokens'))}</span>
                </div>
                <div class="rank-metric">
                  <span class="rank-metric-label">Failures</span>
                  <span class="rank-metric-value">{_format_pct(item.get('failure_rate_pct'))}</span>
                </div>
                <div class="rank-metric">
                  <span class="rank-metric-label">Loops / Stops</span>
                  <span class="rank-metric-value">{int(item.get('continuation_loops', 0) or 0)} / {int(item.get('max_tokens_stops', 0) or 0)}</span>
                </div>
              </div>
              {action_markup}
            </article>
            """
        )
    if rows:
        return "\n".join(rows)
    return '<div class="empty-state">No imported sessions found yet.</div>'


def build_project_dashboard_html(
    aggregate: Dict[str, Any], *, live_mode: bool = False
) -> str:
    """Render a static project dashboard page."""
    totals = aggregate.get("totals") or {}
    overview_insights = build_project_overview_insights(aggregate)
    cost_insights = build_project_cost_insights(aggregate)
    prompt_insights = build_project_prompt_insights(aggregate)
    all_insights = overview_insights + cost_insights + prompt_insights
    trends = aggregate.get("trends") or {}
    daily = trends.get("daily") or []
    date_range = aggregate.get("date_range") or {}
    model_breakdown = aggregate.get("model_breakdown") or []
    top_prompt_groups = aggregate.get("top_prompt_groups") or []
    top_turns = aggregate.get("top_turns") or []
    session_rankings = aggregate.get("session_rankings") or []

    trend_markup = (
        "\n".join(
            f'<div class="trend-pill"><strong>{escape(item.get("date") or "")}</strong><span>{_format_cost(item.get("cost"))} · {_format_tokens(item.get("tokens"))} tokens</span></div>'
            for item in daily[:10]
        )
        or '<div class="empty-state">No daily trend data yet.</div>'
    )
    model_markup = (
        "\n".join(
            f'<div class="trend-pill"><strong>{escape(str(item.get("model") or "unknown"))}</strong><span>{_format_cost(item.get("cost"))} · {_format_tokens(item.get("tokens"))} tokens</span></div>'
            for item in model_breakdown[:8]
        )
        or '<div class="empty-state">No model breakdown available yet.</div>'
    )
    insight_markup = "\n".join(_insight_card(card) for card in all_insights) or (
        '<div class="empty-state">No project-level insights were triggered yet.</div>'
    )
    primary_nav = (
        """
          <a class="primary" href="#" onclick="window.location.reload(); return false;">Refresh View</a>
          <a href="/api/data">API Data</a>
          <a href="/api/refresh">Refresh API</a>
        """
        if live_mode
        else """
          <a class="primary" href="./index.html">Project Dashboard</a>
          <a href="../../sessions/index.html">Session Index</a>
          <a href="../../project/summary.json">Project Aggregate JSON</a>
        """
    )

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Project Dashboard · Harness Observability</title>
  <style>
    :root {{
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
    }}
    * {{
      box-sizing: border-box;
    }}
    html, body {{
      margin: 0;
      min-height: 100%;
      background:
        radial-gradient(circle at top left, rgba(59,130,246,0.10), transparent 30%),
        radial-gradient(circle at top right, rgba(45,212,191,0.08), transparent 28%),
        linear-gradient(180deg, #08101a 0%, #0b0f14 100%);
      color: var(--text);
      font-family: var(--font-sans);
    }}
    body {{
      line-height: 1.5;
    }}
    a {{
      color: inherit;
    }}
    code {{
      font-family: var(--font-mono);
      color: var(--text-strong);
      font-size: 0.95rem;
    }}
    .eyebrow {{
      margin: 0 0 10px;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 0.8rem;
      font-weight: 700;
    }}
    h1, h2, h3, p {{
      margin-top: 0;
    }}
    h1 {{
      font-size: clamp(2.2rem, 4vw, 3.6rem);
      line-height: 1.02;
      letter-spacing: -0.05em;
      margin-bottom: 18px;
      color: var(--text-strong);
    }}
    h2 {{
      color: var(--text-strong);
    }}
    h3 {{
      color: var(--text-strong);
    }}
    .hero-text {{
      color: var(--text);
      max-width: 72ch;
      line-height: 1.6;
    }}
    .artifact-label {{
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 0.78rem;
      font-weight: 700;
      margin-bottom: 10px;
    }}
    .empty-state {{
      color: var(--text-muted);
      padding: 18px;
      border: 1px dashed rgba(148,163,184,0.16);
      border-radius: 16px;
      background: rgba(255,255,255,0.02);
    }}
    .project-shell {{
      max-width: min(1760px, calc(100vw - 40px));
      margin: 0 auto;
      padding: 32px 24px 64px;
    }}
    .project-hero {{
      display: grid;
      grid-template-columns: minmax(0, 1.8fr) minmax(280px, 0.9fr);
      gap: 18px;
      margin-bottom: 28px;
    }}
    .project-hero-card {{
      background: var(--panel);
      border: 1px solid var(--panel-border);
      border-radius: 24px;
      padding: 24px;
      box-shadow: var(--shadow);
    }}
    .project-nav {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-top: 18px;
    }}
    .project-nav a {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 140px;
      padding: 10px 14px;
      border-radius: 999px;
      text-decoration: none;
      color: var(--text-strong);
      background: rgba(255,255,255,0.04);
      border: 1px solid rgba(255,255,255,0.08);
    }}
    .project-nav a.primary {{
      background: linear-gradient(135deg, rgba(96,165,250,0.25), rgba(45,212,191,0.18));
      border-color: rgba(125,211,252,0.28);
    }}
    .project-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
      margin-bottom: 26px;
    }}
    .project-kpi-card {{
      background: linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.02));
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 22px;
      padding: 18px 18px 16px;
      min-height: 132px;
      box-shadow: var(--shadow);
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      overflow: hidden;
    }}
    .project-kpi-label {{
      font-size: 0.82rem;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: var(--text-muted);
      margin-bottom: 10px;
    }}
    .project-kpi-value {{
      font-size: clamp(1.55rem, 2vw, 2.4rem);
      line-height: 1;
      font-weight: 800;
      letter-spacing: -0.04em;
      color: var(--text-strong);
      margin-bottom: 10px;
      overflow-wrap: anywhere;
    }}
    .project-kpi-sub {{
      color: var(--text-muted);
      line-height: 1.45;
      max-width: 28ch;
    }}
    .project-section {{
      background: var(--panel);
      border: 1px solid var(--panel-border);
      border-radius: 24px;
      padding: 22px;
      box-shadow: var(--shadow);
      margin-bottom: 24px;
    }}
    .project-section h2 {{
      margin: 0 0 14px;
      font-size: 1.1rem;
    }}
    .project-section-copy {{
      color: var(--text-muted);
      margin: 0 0 14px;
      max-width: 62ch;
      line-height: 1.5;
    }}
    .project-insight-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
    }}
    .project-insight-card {{
      border-radius: 18px;
      padding: 16px;
      border: 1px solid rgba(255,255,255,0.08);
      background: rgba(255,255,255,0.025);
    }}
    .project-insight-card.severity-high {{
      border-color: rgba(251,191,36,0.4);
      background: linear-gradient(135deg, rgba(251,191,36,0.12), rgba(248,113,113,0.07));
    }}
    .project-insight-card.severity-medium {{
      border-color: rgba(96,165,250,0.22);
    }}
    .project-insight-card.severity-info {{
      border-color: rgba(45,212,191,0.22);
    }}
    .project-insight-kicker {{
      color: var(--text-muted);
      font-size: 0.8rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 8px;
    }}
    .project-insight-card h3 {{
      margin: 0 0 10px;
      font-size: 1rem;
    }}
    .project-insight-card p {{
      margin: 0 0 10px;
      color: var(--text-muted);
    }}
    .project-insight-evidence {{
      color: var(--text-strong) !important;
    }}
    .project-insight-recommendation {{
      margin-bottom: 0 !important;
    }}
    .trend-list {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }}
    .trend-pill {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 12px 14px;
      border-radius: 16px;
      background: rgba(255,255,255,0.03);
      border: 1px solid rgba(255,255,255,0.06);
    }}
    .trend-pill span {{
      color: var(--text-muted);
    }}
    .rank-list,
    .session-list {{
      display: flex;
      flex-direction: column;
      gap: 12px;
    }}
    .rank-card,
    .session-card {{
      display: grid;
      grid-template-columns: 52px minmax(0, 1.35fr) minmax(280px, 0.95fr) auto;
      gap: 16px;
      align-items: center;
      padding: 16px 18px;
      border-radius: 18px;
      border: 1px solid rgba(255,255,255,0.06);
      background: rgba(255,255,255,0.02);
      overflow: hidden;
    }}
    .rank-card-index {{
      color: var(--text-muted);
      font-size: 1.05rem;
      font-weight: 700;
      font-variant-numeric: tabular-nums;
      text-align: center;
    }}
    .prompt-preview {{
      display: none;
    }}
    .rank-card-main,
    .session-card-main {{
      min-width: 0;
      overflow: hidden;
    }}
    .rank-card-title {{
      font-size: 1rem;
      font-weight: 650;
      line-height: 1.4;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .rank-card-subtitle {{
      margin-top: 6px;
      font-size: 0.82rem;
      color: var(--text-muted);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .rank-card-meta {{
      min-width: 0;
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 10px;
      flex-wrap: wrap;
    }}
    .rank-metric {{
      min-width: 72px;
      padding: 8px 10px;
      border-radius: 12px;
      background: rgba(255,255,255,0.03);
      border: 1px solid rgba(255,255,255,0.05);
    }}
    .rank-metric-label {{
      display: block;
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: var(--text-muted);
      margin-bottom: 4px;
    }}
    .rank-metric-value {{
      display: block;
      font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, monospace);
      font-size: 13px;
      font-weight: 700;
      white-space: nowrap;
      font-variant-numeric: tabular-nums;
    }}
    .model-badge {{
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 3px 10px;
      border-radius: 20px;
      font-size: 12px;
      font-weight: 600;
      white-space: nowrap;
    }}
    .model-opus {{
      background: rgba(59,130,246,0.14);
      color: #93c5fd;
      border: 1px solid rgba(59,130,246,0.22);
    }}
    .model-sonnet {{
      background: rgba(16,185,129,0.12);
      color: #86efac;
      border: 1px solid rgba(16,185,129,0.20);
    }}
    .model-haiku {{
      background: rgba(249,115,22,0.12);
      color: #fdba74;
      border: 1px solid rgba(249,115,22,0.20);
    }}
    .model-unknown {{
      background: rgba(148,163,184,0.12);
      color: #cbd5e1;
      border: 1px solid rgba(148,163,184,0.18);
    }}
    .model-dot {{
      width: 6px;
      height: 6px;
      border-radius: 50%;
      flex-shrink: 0;
      background: currentColor;
      opacity: 0.9;
    }}
    .rank-card-action {{
      display: flex;
      justify-content: flex-end;
      align-items: center;
      white-space: nowrap;
    }}
    .table-link {{
      color: var(--accent);
      text-decoration: none;
      font-weight: 600;
    }}
    .action-link {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 76px;
      padding: 8px 10px;
      border-radius: 999px;
      background: rgba(249,115,22,0.08);
      border: 1px solid rgba(249,115,22,0.18);
    }}
    .project-split {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
      gap: 18px;
    }}
    @media (max-width: 1100px) {{
      .project-insight-grid {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
      .project-hero, .project-split {{
        grid-template-columns: 1fr;
      }}
    }}
    @media (max-width: 720px) {{
      .project-grid, .project-insight-grid, .trend-list {{
        grid-template-columns: 1fr;
      }}
      .project-shell {{
        padding-inline: 16px;
        max-width: calc(100vw - 16px);
      }}
      .rank-card,
      .session-card {{
        grid-template-columns: 40px minmax(0, 1fr);
        align-items: start;
      }}
      .rank-card-meta,
      .rank-card-action {{
        grid-column: 2;
        justify-content: flex-start;
      }}
      .rank-card-action {{
        margin-top: -2px;
      }}
      .rank-card-meta {{
        gap: 8px;
      }}
    }}
  </style>
</head>
<body>
  <main class="project-shell">
    <section class="project-hero">
      <div class="project-hero-card">
        <p class="eyebrow">Harness Observability Layer</p>
        <h1>Project Dashboard</h1>
        <p class="hero-text">
          Zero-friction view of aggregate spend, ranked prompt and turn costs, and prescriptive actions for context pressure, model choice, and startup overhead.
        </p>
        <div class="project-nav">
          {primary_nav}
        </div>
      </div>
      <div class="project-hero-card">
        <div class="artifact-label">Coverage</div>
        <code>{escape(str(date_range.get('from') or 'n/a'))} → {escape(str(date_range.get('to') or 'n/a'))}</code>
        <p class="hero-text" style="margin-top:12px;">
          {int(totals.get('sessions', 0) or 0)} imported sessions, {int(totals.get('prompt_groups', 0) or 0)} prompt groups, {int(totals.get('turns', 0) or 0)} turns.
        </p>
      </div>
    </section>

    <section class="project-grid">
      {_kpi("Total Spend", _format_cost(totals.get("estimated_cost_usd")), "API-equivalent across imported sessions")}
      {_kpi("Total Tokens", _format_tokens(totals.get("total_tokens")), f"{_format_tokens(totals.get('total_cache_read_tokens'))} cache-read")}
      {_kpi("Prompt Groups", _format_int(totals.get("prompt_groups")), "Grouped by user prompt plus continuations")}
      {_kpi("Turns", _format_int(totals.get("turns")), "Ranked for /clear and long-context analysis")}
    </section>

    <section class="project-section">
      <h2>Prescriptive Insights</h2>
      <p class="project-section-copy">
        Recommendations are derived from imported session summaries plus prompt-group and turn-level project aggregation.
      </p>
      <div class="project-insight-grid">
        {insight_markup}
      </div>
    </section>

    <section class="project-split">
      <section class="project-section">
        <h2>Daily Trend</h2>
        <p class="project-section-copy">Quick scan of project cost and token accumulation over time.</p>
        <div class="trend-list">
          {trend_markup}
        </div>
      </section>

      <section class="project-section">
        <h2>Model Mix</h2>
        <p class="project-section-copy">Model usage ranked by project cost contribution.</p>
        <div class="trend-list">
          {model_markup}
        </div>
      </section>
    </section>

    <section class="project-split">
      <section class="project-section">
        <h2>Most Expensive Prompt Groups</h2>
        <p class="project-section-copy">Grouped by prompt.</p>
        <div class="rank-list">
          {_top_rows(top_prompt_groups, heading_kind="prompt-group", show_actions=not live_mode)}
        </div>
      </section>

      <section class="project-section">
        <h2>Most Expensive Turns</h2>
        <p class="project-section-copy">Ranked by turn cost.</p>
        <div class="rank-list">
          {_top_rows(top_turns, heading_kind="turn", show_actions=not live_mode)}
        </div>
      </section>
    </section>

    <section class="project-section">
      <h2>Sessions Requiring Attention</h2>
      <p class="project-section-copy">
        Ordered by attention score so cost, failure pressure, continuation loops, and max-token stops surface quickly.
      </p>
      <div class="session-list">
        {_session_rows(session_rankings, show_actions=not live_mode)}
      </div>
    </section>
  </main>
</body>
</html>
"""
