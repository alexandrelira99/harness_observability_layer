"""Public package for the Harness Observability Layer."""

from .plugin.api import (
    compare_sessions,
    find_high_failure_sessions,
    generate_portfolio_markdown,
    generate_session_html,
    generate_session_markdown,
    import_all_sessions,
    import_latest_session,
    import_session,
    list_sessions,
    summarize_session,
)

__all__ = [
    "compare_sessions",
    "find_high_failure_sessions",
    "generate_portfolio_markdown",
    "generate_session_html",
    "generate_session_markdown",
    "import_all_sessions",
    "import_latest_session",
    "import_session",
    "list_sessions",
    "summarize_session",
]

__version__ = "1.0.0"
