"""Run `codex exec --json` and persist both raw and normalized streams."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from harness_observability_layer.integrations.codex_exec import run_codex_exec_observed
from harness_observability_layer.observer.analyzer import analyze_jsonl, load_events
from harness_observability_layer.reporting.html_report import build_session_report_html, report_css
from harness_observability_layer.reporting.session_artifacts import ensure_project_artifact_dirs, refresh_sessions_index


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Codex with observability capture.")
    parser.add_argument("prompt", help="Prompt to send to `codex exec`.")
    parser.add_argument(
        "--cwd",
        default=".",
        help="Working directory to pass to `codex exec -C`.",
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Directory for raw and normalized event output. Defaults to artifacts/live_runs/run_001-style folders.",
    )
    parser.add_argument(
        "--codex-arg",
        action="append",
        default=[],
        help="Extra argument to forward to `codex exec`. Repeatable.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    paths = ensure_project_artifact_dirs(project_root)
    if args.data_dir:
        data_dir = Path(args.data_dir).expanduser()
    else:
        live_root = paths["live_runs_root"]
        existing = sorted(path for path in live_root.iterdir() if path.is_dir())
        data_dir = live_root / f"run_{len(existing) + 1:03d}"
    data_dir.mkdir(parents=True, exist_ok=True)

    raw_path = data_dir / "codex.raw.jsonl"
    normalized_path = data_dir / "codex.normalized.events.jsonl"
    summary_path = data_dir / "summary.json"
    report_html_path = data_dir / "report.html"
    report_css_path = data_dir / "report.css"

    returncode = run_codex_exec_observed(
        prompt=args.prompt,
        cwd=args.cwd,
        raw_output_path=raw_path,
        normalized_output_path=normalized_path,
        extra_args=args.codex_arg,
    )

    print(f"codex_returncode={returncode}")
    print(f"raw_output_file={raw_path}")
    print(f"normalized_events_file={normalized_path}")

    if normalized_path.exists():
        summary = analyze_jsonl(normalized_path)
        events = load_events(normalized_path)
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        report_css_path.write_text(report_css(), encoding="utf-8")
        report_html_path.write_text(
            build_session_report_html(
                session_label=data_dir.name,
                summary=summary,
                normalized_events_file=str(normalized_path),
                events=events,
            ),
            encoding="utf-8",
        )
        index_path = refresh_sessions_index(project_root)
        print(f"summary_file={summary_path}")
        print(f"html_report={report_html_path}")
        print(f"sessions_index={index_path}")
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
