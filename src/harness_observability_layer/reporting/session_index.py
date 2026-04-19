"""HTML index page for imported session artifacts."""

from __future__ import annotations

from html import escape
from typing import Any, Dict, Iterable

from .guided_site import TRANSLATIONS, _js_object_literal


def _text(key: str) -> str:
    return TRANSLATIONS["eng"].get(key, key)


def _i18n_attrs(key: str, default: str | None = None) -> str:
    fallback = default if default is not None else _text(key)
    return (
        f' data-i18n="{escape(key, quote=True)}"'
        f' data-i18n-default="{escape(fallback, quote=True)}"'
    )

def _format_rate(value: Any) -> str:
    if value in (None, ""):
        return "0.00%"
    return f"{float(value):.2f}%"


def _format_duration(seconds: float) -> str:
    if seconds <= 0:
        return "—"
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes = seconds / 60
    if minutes < 60:
        return f"{minutes:.1f}m"
    hours = minutes / 60
    return f"{hours:.1f}h"


def _format_cost(cost: Any) -> str:
    if cost is None:
        return "—"
    c = float(cost)
    if c < 0.01:
        return f"${c:.4f}"
    return f"${c:.2f}"


def _format_cost_cell(summary: Dict[str, Any]) -> str:
    plan = summary.get("plan_type")
    cost = summary.get("estimated_cost_usd")
    if plan:
        label = plan.capitalize()
        if cost is not None:
            return (
                f"<strong>{label}</strong><span>API-equiv {_format_cost(cost)}</span>"
            )
        return (
            f"<strong>{label}</strong>"
            f'<span{_i18n_attrs("metrics.cost")}>{escape(_text("metrics.cost").lower())}</span>'
        )
    return (
        f"<strong>{_format_cost(cost)}</strong>"
        f'<span{_i18n_attrs("metrics.cost")}>{escape(_text("metrics.cost").lower())}</span>'
    )


def _format_tokens(count: Any) -> str:
    c = int(count or 0)
    if c >= 1_000_000:
        return f"{c / 1_000_000:.1f}M"
    if c >= 1_000:
        return f"{c / 1_000:.1f}K"
    return str(c)


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
    efficiency = summary.get("efficiency_indicators", {})
    if efficiency.get("continuation_loops", 0) > 0:
        badges.append(_badge("continuation loops", "warning"))
    if efficiency.get("max_tokens_stops", 0) > 0:
        badges.append(_badge("max-token stops", "warning"))
    model = summary.get("model")
    if model:
        badges.append(_badge(model))
    return "".join(badges)


def _top_tool(summary: Dict[str, Any]) -> str:
    name = summary.get("top_tool_name")
    count = int(summary.get("top_tool_count", 0) or 0)
    if not name:
        return "—"
    return f"{name} ({count})"


def _index_script() -> str:
    translations = _js_object_literal(TRANSLATIONS)
    return f"""
  <script data-hol="index-ui">
    (() => {{
      const messages = {translations};
      const localeKey = "hol:locale";
      const themeKey = "hol:theme";
      const root = document.documentElement;
      const defaultLocale = root.dataset.locale || "eng";
      const defaultTheme = root.dataset.theme || "dark";

      const getMessages = (locale) => messages[locale] || messages.eng || {{}};
      const t = (locale, key) => getMessages(locale)[key] || (messages.eng || {{}})[key] || key;

      const applyLocale = (locale) => {{
        root.dataset.locale = locale;
        root.lang = locale === "pt" ? "pt-BR" : locale === "es" ? "es" : "en";
        document.querySelectorAll("[data-i18n]").forEach((node) => {{
          node.textContent = t(locale, node.dataset.i18n);
        }});
        document.querySelectorAll("[data-locale-option]").forEach((node) => {{
          node.classList.toggle("is-active", node.dataset.localeOption === locale);
        }});
        localStorage.setItem(localeKey, locale);
      }};

      const applyTheme = (theme) => {{
        root.dataset.theme = theme;
        document.querySelectorAll("[data-theme-option]").forEach((node) => {{
          node.classList.toggle("is-active", node.dataset.themeOption === theme);
        }});
        localStorage.setItem(themeKey, theme);
      }};

      applyTheme(localStorage.getItem("hol:theme") || defaultTheme);
      applyLocale(localStorage.getItem("hol:locale") || defaultLocale);

      document.querySelectorAll("[data-locale-option]").forEach((node) => {{
        node.addEventListener("click", () => applyLocale(node.dataset.localeOption));
      }});
      document.querySelectorAll("[data-theme-option]").forEach((node) => {{
        node.addEventListener("click", () => applyTheme(node.dataset.themeOption));
      }});
    }})();
  </script>
"""


def build_sessions_index_html(entries: Iterable[Dict[str, Any]]) -> str:
    """Build a styled index page listing imported sessions."""
    entries = list(entries)
    rows = []
    for entry in entries:
        summary = entry["summary"]
        metadata = entry.get("metadata") or {}
        failures = sum(
            int(v) for v in summary.get("tool_failures_by_name", {}).values()
        )
        rows.append(
            f"""
            <a class="session-row" href="{escape(entry["report_relpath"])}">
              <div class="session-row-main">
                <div class="session-row-kicker">{escape(str(metadata.get("source_name") or "Imported Session"))}</div>
                <div class="session-row-title">{escape(str(metadata.get("display_title") or entry["session_name"]))}</div>
                <div class="session-row-subtitle">{escape(str(metadata.get("display_subtitle") or entry["session_name"]))}</div>
                <div class="session-row-context">{escape(str(metadata.get("prompt_excerpt") or ""))}</div>
                <div class="session-row-badges">{_runtime_badges(metadata, summary)}</div>
              </div>
              <div class="session-row-metric">{summary.get("total_tool_calls", 0)}</div>
              <div class="session-row-metric session-row-metric-text">{escape(_top_tool(summary))}</div>
              <div class="session-row-metric">{summary.get("distinct_files_read", 0)}</div>
              <div class="session-row-metric">{summary.get("distinct_files_edited", 0)}</div>
              <div class="session-row-metric session-row-metric-stack"><strong>{_format_tokens(summary.get("total_tokens", 0))}</strong><span>tokens</span></div>
              <div class="session-row-metric session-row-metric-stack">{_format_cost_cell(summary)}</div>
              <div class="session-row-metric session-row-metric-stack"><strong>{_format_duration(summary.get("session_duration_seconds", 0))}</strong><span>duration</span></div>
              <div class="session-row-metric session-row-metric-stack"><strong>{_format_rate(summary.get("failure_rate_pct", 0))}</strong><span>{failures} failures</span></div>
            </a>
            """
        )

    rows_markup = (
        "\n".join(rows)
        if rows
        else f'<div class="empty-state"{_i18n_attrs("index.empty")}>No imported sessions found yet.</div>'
    )

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark" data-locale="eng">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Imported Sessions · Harness Observability</title>
  <link rel="stylesheet" href="./report.css" />
</head>
<body>
  <main class="page-shell">
    <section class="hero">
      <div class="hero-topbar">
        <div class="hero-heading">
          <p class="eyebrow"{_i18n_attrs("brand.eyebrow")}>{escape(_text("brand.eyebrow"))}</p>
          <h1 data-i18n="index.title">Imported Sessions</h1>
          <p class="hero-text" data-i18n="index.subtitle">
            Browse imported agent sessions for this project and open guided, session-specific reports with QA, cost, workflow, and raw metric views.
          </p>
        </div>
        <div class="hero-controls">
          <div class="control-group" data-locale-switcher>
            <span class="control-label"{_i18n_attrs("controls.language")}>{escape(_text("controls.language"))}</span>
            <button type="button" class="control-chip" data-locale-option="eng">{escape(_text("controls.eng"))}</button>
            <button type="button" class="control-chip" data-locale-option="pt">{escape(_text("controls.pt"))}</button>
            <button type="button" class="control-chip" data-locale-option="es">{escape(_text("controls.es"))}</button>
          </div>
          <div class="control-group" data-theme-switcher>
            <span class="control-label"{_i18n_attrs("controls.theme")}>{escape(_text("controls.theme"))}</span>
            <button type="button" class="control-chip" data-theme-option="dark">{escape(_text("controls.dark"))}</button>
            <button type="button" class="control-chip" data-theme-option="light">{escape(_text("controls.light"))}</button>
          </div>
        </div>
      </div>
      <div class="hero-panel">
        <div class="artifact-label" data-i18n="index.indexed">Sessions indexed</div>
        <code>{len(entries)}</code>
      </div>
    </section>

    <section class="page-section session-grid">
      <div class="session-grid-head">
        <div data-i18n="index.session_description">Session Description</div>
        <div data-i18n="index.tools">Tools</div>
        <div data-i18n="index.top_tool">Top Tool</div>
        <div data-i18n="index.read">Read</div>
        <div data-i18n="index.edited">Edited</div>
        <div data-i18n="metrics.tokens">Tokens</div>
        <div data-i18n="metrics.cost">Cost</div>
        <div data-i18n="metrics.duration">Duration</div>
        <div data-i18n="index.failure_rate">Failure Rate</div>
      </div>
      <div class="session-grid-body">
        {rows_markup}
      </div>
    </section>
  </main>
{_index_script()}
</body>
</html>
"""
