"""Run a mocked task to generate observability events."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from uuid import uuid4

from adapters.file_tools import FileToolAdapter
from adapters.shell_tools import ShellToolAdapter
from adapters.skill_loader import SkillLoader
from harness.runner import HarnessRunner, RunContext
from observer.analyzer import analyze_jsonl
from observer.logger import JsonlEventLogger


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    default_data_dir = Path("/tmp/harness_observability_layer")
    data_dir = Path(os.getenv("HOBS_DATA_DIR", str(default_data_dir)))
    data_dir.mkdir(parents=True, exist_ok=True)
    sample_fixture = root / "examples" / "sample_repo" / "app.py"
    session_id = f"sess_{uuid4().hex[:8]}"
    task_id = f"task_{uuid4().hex[:8]}"
    output_path = data_dir / f"{session_id}.events.jsonl"
    sample_file = data_dir / f"{session_id}.app.py"
    shutil.copyfile(sample_fixture, sample_file)

    logger = JsonlEventLogger(output_path)
    runner = HarnessRunner(logger)
    ctx = RunContext(session_id=session_id, task_id=task_id)

    runner.start_session(ctx)
    runner.start_task(ctx, "Inspect app.py and append a TODO marker.")
    runner.agent_message(ctx, "Loading a Python-focused skill and checking the sample file.")

    skills = SkillLoader(logger, session_id, task_id)
    skills.load_skill("python-editing", "skills/python-editing/SKILL.md")
    skills.invoke_plugin("local-files", "read-write")

    file_tools = FileToolAdapter(logger, session_id, task_id)
    shell_tools = ShellToolAdapter(logger, session_id, task_id)

    _ = file_tools.read_lines(sample_file, 1, 3)
    _ = shell_tools.run(f"wc -l {sample_file}")
    file_tools.append_text(sample_file, "\n# TODO: add richer observability hooks\n")

    runner.agent_message(ctx, "Task complete; summarizing events.")
    runner.finish_task(ctx, "success")
    runner.finish_session(ctx)

    summary = analyze_jsonl(output_path)
    print(json.dumps(summary, indent=2))
    print(f"\nevents_file={output_path}")


if __name__ == "__main__":
    main()
