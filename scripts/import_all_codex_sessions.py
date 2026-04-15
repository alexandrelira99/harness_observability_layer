"""Import all archived Codex sessions into project-local artifacts."""

from __future__ import annotations

import argparse

from pathlib import Path

from harness_observability_layer.plugin.api import import_all_sessions


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import all archived Codex sessions.")
    parser.add_argument(
        "--archived-dir",
        default="~/.codex/archived_sessions",
        help="Directory containing archived Codex rollout JSONL files.",
    )
    parser.add_argument(
        "--reimport",
        action="store_true",
        help="Reimport sessions even if their artifact directory already exists.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    result = import_all_sessions(args.archived_dir, reimport=args.reimport, project_root=project_root)
    for session_id in result["imported_sessions"]:
        print(f"imported={session_id}")
    for session_id in result["skipped_sessions"]:
        print(f"skipped={session_id}")
    print(f"imported_count={result['imported_count']}")
    print(f"skipped_count={result['skipped_count']}")
    print(f"sessions_index={result['index_path']}")


if __name__ == "__main__":
    main()
