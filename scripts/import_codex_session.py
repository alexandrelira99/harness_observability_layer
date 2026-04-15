"""Import a Codex session JSONL file into canonical observability events."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from harness_observability_layer.plugin.api import import_session


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import a Codex JSONL session into canonical events.")
    parser.add_argument("input", help="Path to the raw Codex JSONL session file.")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Session artifact directory. Defaults to artifacts/sessions/<session-name>/.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input).expanduser().resolve()
    project_root = Path(__file__).resolve().parents[1]
    result = import_session(str(input_path), output_dir=args.output_dir, project_root=project_root)

    print(json.dumps(result["summary"], indent=2))
    print(f"\nraw_session_copy={result['paths']['raw']}")
    print(f"normalized_events_file={result['paths']['normalized']}")
    print(f"summary_file={result['paths']['summary']}")
    print(f"html_report={result['paths']['html']}")
    print(f"sessions_index={result['paths']['index']}")


if __name__ == "__main__":
    main()
