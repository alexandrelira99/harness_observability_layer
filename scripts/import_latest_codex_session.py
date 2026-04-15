"""Import the most recent archived Codex session into project-local artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path

from harness_observability_layer.plugin.api import import_latest_session


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import the most recent archived Codex session.")
    parser.add_argument(
        "--archived-dir",
        default="~/.codex/archived_sessions",
        help="Directory containing archived Codex rollout JSONL files.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional explicit output directory.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    result = import_latest_session(args.archived_dir, project_root=project_root)
    if result.get("skipped"):
        print(f"skipped_session={result['session_id']}")
        print(f"session_dir={result['paths']['session_dir']}")
        return

    print(f"imported_session={result['session_id']}")
    print(f"html_report={result['paths']['html']}")
    print(f"sessions_index={result['paths']['index']}")


if __name__ == "__main__":
    main()
