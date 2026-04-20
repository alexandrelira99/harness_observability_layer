"""Reporting namespace."""

from .markdown_report import build_portfolio_markdown, build_session_markdown
from .text_report import build_session_text
from .html_report import build_session_report_html, report_css
from .guided_site import build_guided_session_site
from .project_aggregate import (
    build_project_aggregate,
    build_project_aggregate_from_sessions,
    group_events_into_prompt_turns,
)
from .project_dashboard import build_project_dashboard_html
from .session_dashboard import build_session_dashboard_html
from .session_artifacts import (
    ensure_project_artifact_dirs,
    import_claude_code_session_to_dir,
    import_codex_session_to_dir,
    import_session_to_dir,
    refresh_sessions_index,
)

__all__ = [
    "build_portfolio_markdown",
    "build_guided_session_site",
    "build_project_aggregate",
    "build_project_aggregate_from_sessions",
    "build_project_dashboard_html",
    "build_session_dashboard_html",
    "build_session_markdown",
    "build_session_report_html",
    "build_session_text",
    "ensure_project_artifact_dirs",
    "import_claude_code_session_to_dir",
    "import_codex_session_to_dir",
    "import_session_to_dir",
    "refresh_sessions_index",
    "group_events_into_prompt_turns",
    "report_css",
]
