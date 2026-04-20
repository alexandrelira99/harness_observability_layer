"""CLI entrypoint for the Harness Observability Layer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from harness_observability_layer.plugin.api import load_live_dashboard_data
from harness_observability_layer.server import serve_dashboard


def _print(result: Any) -> None:
    if isinstance(result, (dict, list)):
        print(json.dumps(result, indent=2))
        return
    print(result)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hol",
        description="Harness Observability Layer localhost dashboard",
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="Project root used to match archived sessions to the current repository.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser(
        "init",
        help="Start the HOL localhost dashboard for the current project.",
    )
    init_parser.add_argument(
        "--port", type=int, default=3845, help="Port to run the dashboard on."
    )
    init_parser.add_argument(
        "--host", default="127.0.0.1", help="Host interface to bind the server to."
    )
    init_parser.add_argument(
        "--no-open", action="store_true", help="Do not auto-open the browser."
    )
    init_parser.add_argument(
        "--resolve-files",
        action="store_true",
        help="Resolve file stats while aggregating data.",
    )

    data_parser = subparsers.add_parser(
        "data",
        help="Print the live aggregate JSON used by the dashboard.",
    )
    data_parser.add_argument(
        "--resolve-files",
        action="store_true",
        help="Resolve file stats while aggregating data.",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    project_root = Path(args.project_root).resolve()

    if args.command == "init":
        serve_dashboard(
            host=args.host,
            port=args.port,
            project_root=str(project_root),
            no_open=args.no_open,
            resolve_file_stats=args.resolve_files,
        )
        return

    if args.command == "data":
        _print(
            load_live_dashboard_data(
                project_root,
                resolve_file_stats=args.resolve_files,
            )
        )
        return


if __name__ == "__main__":
    main()

