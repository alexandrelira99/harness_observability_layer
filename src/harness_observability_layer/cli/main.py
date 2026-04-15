"""CLI entrypoint for the Harness Observability Layer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from harness_observability_layer.plugin.api import (
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


def _print(result: Any, format: str | None = None) -> None:
    if isinstance(result, (dict, list)):
        print(json.dumps(result, indent=2))
        return
    if format == "json":
        print(json.dumps(result, indent=2))
        return
    print(result)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hol", description="Harness Observability Layer CLI")
    parser.add_argument("--project-root", default=".", help="Project root that contains hol-artifacts/")
    subparsers = parser.add_subparsers(dest="command", required=True)

    import_parser = subparsers.add_parser("import", help="Import archived or raw Codex sessions")
    import_sub = import_parser.add_subparsers(dest="import_command", required=True)
    import_session_parser = import_sub.add_parser("session", help="Import one raw Codex session")
    import_session_parser.add_argument("path")
    import_session_parser.add_argument("--output-dir", default=None)
    import_session_parser.add_argument("--no-raw-copy", action="store_true")
    import_session_parser.add_argument("--no-resolve-files", action="store_true")

    import_latest_parser = import_sub.add_parser("latest", help="Import the latest archived Codex session")
    import_latest_parser.add_argument("--archived-dir", default="~/.codex/archived_sessions")
    import_latest_parser.add_argument("--reimport", action="store_true")
    import_latest_parser.add_argument("--no-raw-copy", action="store_true")
    import_latest_parser.add_argument("--no-resolve-files", action="store_true")

    import_all_parser = import_sub.add_parser("all", help="Import all archived Codex sessions")
    import_all_parser.add_argument("--archived-dir", default="~/.codex/archived_sessions")
    import_all_parser.add_argument("--reimport", action="store_true")
    import_all_parser.add_argument("--no-raw-copy", action="store_true")
    import_all_parser.add_argument("--no-resolve-files", action="store_true")

    import_claude_session_parser = import_sub.add_parser("claude-session", help="Import one raw Claude Code session")
    import_claude_session_parser.add_argument("path")
    import_claude_session_parser.add_argument("--output-dir", default=None)
    import_claude_session_parser.add_argument("--no-raw-copy", action="store_true")
    import_claude_session_parser.add_argument("--no-resolve-files", action="store_true")

    import_claude_latest_parser = import_sub.add_parser("claude-latest", help="Import the latest archived Claude Code session")
    import_claude_latest_parser.add_argument("--archived-dir", default="~/.claude/projects")
    import_claude_latest_parser.add_argument("--reimport", action="store_true")
    import_claude_latest_parser.add_argument("--no-raw-copy", action="store_true")
    import_claude_latest_parser.add_argument("--no-resolve-files", action="store_true")

    import_claude_all_parser = import_sub.add_parser("claude-all", help="Import all archived Claude Code sessions")
    import_claude_all_parser.add_argument("--archived-dir", default="~/.claude/projects")
    import_claude_all_parser.add_argument("--reimport", action="store_true")
    import_claude_all_parser.add_argument("--no-raw-copy", action="store_true")
    import_claude_all_parser.add_argument("--no-resolve-files", action="store_true")

    analyze_parser = subparsers.add_parser("analyze", help="Analyze imported sessions")
    analyze_sub = analyze_parser.add_subparsers(dest="analyze_command", required=True)
    analyze_session_parser = analyze_sub.add_parser("session", help="Summarize one session")
    analyze_session_parser.add_argument("session")
    analyze_session_parser.add_argument("--format", choices=["text", "markdown", "json"], default="text")
    analyze_session_parser.add_argument("--no-resolve-files", action="store_true")
    analyze_session_parser.add_argument("--redact-sensitive", action="store_true")

    analyze_latest_parser = analyze_sub.add_parser("latest", help="Summarize the latest imported session")
    analyze_latest_parser.add_argument("--format", choices=["text", "markdown", "json"], default="text")
    analyze_latest_parser.add_argument("--no-resolve-files", action="store_true")
    analyze_latest_parser.add_argument("--redact-sensitive", action="store_true")

    analyze_compare_parser = analyze_sub.add_parser("compare", help="Compare two sessions")
    analyze_compare_parser.add_argument("a")
    analyze_compare_parser.add_argument("b")
    analyze_compare_parser.add_argument("--format", choices=["text", "markdown", "json"], default="markdown")
    analyze_compare_parser.add_argument("--redact-sensitive", action="store_true")

    report_parser = subparsers.add_parser("report", help="Generate reports")
    report_sub = report_parser.add_subparsers(dest="report_command", required=True)
    report_html_parser = report_sub.add_parser("html", help="Regenerate a session HTML report")
    report_html_parser.add_argument("session")
    report_html_parser.add_argument("--no-resolve-files", action="store_true")
    report_html_parser.add_argument("--redact-sensitive", action="store_true")

    report_md_parser = report_sub.add_parser("markdown", help="Generate markdown for one session")
    report_md_parser.add_argument("session")
    report_md_parser.add_argument("--verbosity", choices=["normal", "high"], default="normal")
    report_md_parser.add_argument("--no-resolve-files", action="store_true")
    report_md_parser.add_argument("--redact-sensitive", action="store_true")

    report_summary_parser = report_sub.add_parser("summary", help="Generate a short session summary")
    report_summary_parser.add_argument("session")
    report_summary_parser.add_argument("--format", choices=["text", "markdown", "json"], default="text")
    report_summary_parser.add_argument("--no-resolve-files", action="store_true")
    report_summary_parser.add_argument("--redact-sensitive", action="store_true")

    list_parser = subparsers.add_parser("list", help="List imported sessions")
    list_parser.add_argument("--limit", type=int, default=10)
    list_parser.add_argument("--sort-by", choices=["recent", "failures", "tool_calls"], default="recent")
    list_parser.add_argument("--format", choices=["text", "markdown", "json"], default="markdown")
    list_parser.add_argument("--redact-sensitive", action="store_true")

    failures_parser = subparsers.add_parser("failures", help="Find high-failure sessions")
    failures_parser.add_argument("--min-failures", type=int, default=1)
    failures_parser.add_argument("--limit", type=int, default=10)
    failures_parser.add_argument("--format", choices=["text", "markdown", "json"], default="markdown")
    failures_parser.add_argument("--redact-sensitive", action="store_true")

    portfolio_parser = subparsers.add_parser("portfolio", help="Generate a multi-session markdown portfolio")
    portfolio_parser.add_argument("--limit", type=int, default=10)
    portfolio_parser.add_argument("--sort-by", choices=["recent", "failures", "tool_calls"], default="recent")
    portfolio_parser.add_argument("--redact-sensitive", action="store_true")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    project_root = Path(args.project_root).resolve()

    if args.command == "import":
        if args.import_command == "session":
            _print(
                import_session(
                    args.path,
                    output_dir=args.output_dir,
                    project_root=project_root,
                    copy_raw=not args.no_raw_copy,
                    resolve_file_stats=not args.no_resolve_files,
                )
            )
            return
        if args.import_command == "latest":
            _print(
                import_latest_session(
                    args.archived_dir,
                    reimport=args.reimport,
                    project_root=project_root,
                    copy_raw=not args.no_raw_copy,
                    resolve_file_stats=not args.no_resolve_files,
                )
            )
            return
        if args.import_command == "all":
            _print(
                import_all_sessions(
                    args.archived_dir,
                    reimport=args.reimport,
                    project_root=project_root,
                    copy_raw=not args.no_raw_copy,
                    resolve_file_stats=not args.no_resolve_files,
                )
            )
            return
        if args.import_command == "claude-session":
            _print(
                import_session(
                    args.path,
                    output_dir=args.output_dir,
                    project_root=project_root,
                    source="claude",
                    copy_raw=not args.no_raw_copy,
                    resolve_file_stats=not args.no_resolve_files,
                )
            )
            return
        if args.import_command == "claude-latest":
            _print(
                import_latest_session(
                    args.archived_dir,
                    reimport=args.reimport,
                    project_root=project_root,
                    source="claude",
                    copy_raw=not args.no_raw_copy,
                    resolve_file_stats=not args.no_resolve_files,
                )
            )
            return
        if args.import_command == "claude-all":
            _print(
                import_all_sessions(
                    args.archived_dir,
                    reimport=args.reimport,
                    project_root=project_root,
                    source="claude",
                    copy_raw=not args.no_raw_copy,
                    resolve_file_stats=not args.no_resolve_files,
                )
            )
            return

    if args.command == "analyze":
        if args.analyze_command == "session":
            _print(
                summarize_session(
                    session_id=args.session,
                    format=args.format,
                    project_root=project_root,
                    resolve_file_stats=None if not args.no_resolve_files else False,
                    redact_sensitive=args.redact_sensitive,
                )
            )
            return
        if args.analyze_command == "latest":
            sessions = list_sessions(limit=1, sort_by="recent", format="json", project_root=project_root)
            if not sessions:
                raise SystemExit("No imported sessions found.")
            _print(
                summarize_session(
                    session_id=sessions[0]["session_id"],
                    format=args.format,
                    project_root=project_root,
                    resolve_file_stats=None if not args.no_resolve_files else False,
                    redact_sensitive=args.redact_sensitive,
                )
            )
            return
        if args.analyze_command == "compare":
            _print(compare_sessions(args.a, args.b, format=args.format, project_root=project_root, redact_sensitive=args.redact_sensitive))
            return

    if args.command == "report":
        if args.report_command == "html":
            _print(
                generate_session_html(
                    args.session,
                    project_root=project_root,
                    resolve_file_stats=None if not args.no_resolve_files else False,
                    redact_sensitive=args.redact_sensitive,
                )
            )
            return
        if args.report_command == "markdown":
            _print(
                generate_session_markdown(
                    args.session,
                    verbosity=args.verbosity,
                    project_root=project_root,
                    resolve_file_stats=None if not args.no_resolve_files else False,
                    redact_sensitive=args.redact_sensitive,
                )
            )
            return
        if args.report_command == "summary":
            _print(
                summarize_session(
                    session_id=args.session,
                    format=args.format,
                    project_root=project_root,
                    resolve_file_stats=None if not args.no_resolve_files else False,
                    redact_sensitive=args.redact_sensitive,
                )
            )
            return

    if args.command == "list":
        _print(
            list_sessions(
                limit=args.limit,
                sort_by=args.sort_by,
                format=args.format,
                project_root=project_root,
                redact_sensitive=args.redact_sensitive,
            )
        )
        return

    if args.command == "failures":
        _print(
            find_high_failure_sessions(
                min_failures=args.min_failures,
                limit=args.limit,
                format=args.format,
                project_root=project_root,
                redact_sensitive=args.redact_sensitive,
            )
        )
        return

    if args.command == "portfolio":
        _print(
            generate_portfolio_markdown(
                limit=args.limit,
                sort_by=args.sort_by,
                project_root=project_root,
                redact_sensitive=args.redact_sensitive,
            )
        )
        return

    raise SystemExit(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    main()
