"""Run Codex CLI and capture normalized observability events."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Iterable, List

from observer.events import Event
from observer.logger import JsonlEventLogger

from .codex_jsonl import normalize_codex_records


def run_codex_exec_observed(
    prompt: str,
    cwd: str | Path,
    raw_output_path: str | Path,
    normalized_output_path: str | Path,
    extra_args: Iterable[str] | None = None,
) -> int:
    """Run `codex exec --json` and persist raw plus normalized event streams."""
    args: List[str] = [
        "codex",
        "exec",
        "--json",
        "--skip-git-repo-check",
        "-C",
        str(cwd),
    ]
    if extra_args:
        args.extend(list(extra_args))
    args.append(prompt)

    raw_path = Path(raw_output_path)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    normalized_path = Path(normalized_output_path)
    if raw_path.exists():
        raw_path.unlink()
    if normalized_path.exists():
        normalized_path.unlink()
    normalized_logger = JsonlEventLogger(normalized_path)

    raw_records = []
    with subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    ) as process:
        assert process.stdout is not None
        with raw_path.open("w", encoding="utf-8") as raw_handle:
            for line in process.stdout:
                raw_handle.write(line)
                raw_handle.flush()
                try:
                    raw_records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        returncode = process.wait()

    for event in normalize_codex_records(raw_records):
        normalized_logger.log(event)

    return returncode
