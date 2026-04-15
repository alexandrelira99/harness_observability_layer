"""Observable shell execution tools."""

from __future__ import annotations

import subprocess

from observer.events import Event
from observer.logger import JsonlEventLogger
from observer.schemas import TOOL_CALL_FAILED, TOOL_CALL_FINISHED, TOOL_CALL_STARTED


class ShellToolAdapter:
    """A very small shell tool wrapper that emits tool call events."""

    def __init__(self, logger: JsonlEventLogger, session_id: str, task_id: str, agent_id: str = "main"):
        self.logger = logger
        self.session_id = session_id
        self.task_id = task_id
        self.agent_id = agent_id

    def run(self, cmd: str) -> str:
        """Run a shell command and emit success/failure events."""
        self.logger.log(
            Event(
                event_type=TOOL_CALL_STARTED,
                source="tool_adapter",
                session_id=self.session_id,
                task_id=self.task_id,
                agent_id=self.agent_id,
                payload={"tool_name": "shell.run", "cmd": cmd},
            )
        )
        completed = subprocess.run(cmd, shell=True, check=False, capture_output=True, text=True)
        payload = {
            "tool_name": "shell.run",
            "cmd": cmd,
            "returncode": completed.returncode,
            "stdout_preview": completed.stdout[:200],
            "stderr_preview": completed.stderr[:200],
        }
        event_type = TOOL_CALL_FINISHED if completed.returncode == 0 else TOOL_CALL_FAILED
        self.logger.log(
            Event(
                event_type=event_type,
                source="tool_adapter",
                session_id=self.session_id,
                task_id=self.task_id,
                agent_id=self.agent_id,
                payload=payload,
            )
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or f"Command failed: {cmd}")
        return completed.stdout

