"""Observable file tools."""

from __future__ import annotations

from pathlib import Path

from observer.events import Event
from observer.logger import JsonlEventLogger
from observer.normalizers import make_file_edit_payload, make_file_read_payload
from observer.schemas import FILE_EDIT, FILE_READ, TOOL_CALL_FINISHED, TOOL_CALL_STARTED


class FileToolAdapter:
    """A tiny file adapter that emits canonical read and edit events."""

    def __init__(self, logger: JsonlEventLogger, session_id: str, task_id: str, agent_id: str = "main"):
        self.logger = logger
        self.session_id = session_id
        self.task_id = task_id
        self.agent_id = agent_id

    def read_lines(self, path: str | Path, line_start: int, line_end: int) -> str:
        """Read a line span and emit tool and file read events."""
        file_path = Path(path)
        self.logger.log(
            Event(
                event_type=TOOL_CALL_STARTED,
                source="tool_adapter",
                session_id=self.session_id,
                task_id=self.task_id,
                agent_id=self.agent_id,
                payload={"tool_name": "read_lines", "path": str(file_path), "line_start": line_start, "line_end": line_end},
            )
        )
        lines = file_path.read_text(encoding="utf-8").splitlines()
        selected = lines[max(line_start - 1, 0):line_end]
        content = "\n".join(selected)
        self.logger.log(
            Event(
                event_type=FILE_READ,
                source="tool_adapter",
                session_id=self.session_id,
                task_id=self.task_id,
                agent_id=self.agent_id,
                payload=make_file_read_payload(file_path, line_start, line_end, "read_lines", len(content.encode("utf-8"))),
            )
        )
        self.logger.log(
            Event(
                event_type=TOOL_CALL_FINISHED,
                source="tool_adapter",
                session_id=self.session_id,
                task_id=self.task_id,
                agent_id=self.agent_id,
                payload={"tool_name": "read_lines", "path": str(file_path)},
            )
        )
        return content

    def append_text(self, path: str | Path, text: str) -> None:
        """Append text to a file and emit canonical edit events."""
        file_path = Path(path)
        self.logger.log(
            Event(
                event_type=TOOL_CALL_STARTED,
                source="tool_adapter",
                session_id=self.session_id,
                task_id=self.task_id,
                agent_id=self.agent_id,
                payload={"tool_name": "append_text", "path": str(file_path)},
            )
        )
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with file_path.open("a", encoding="utf-8") as handle:
            handle.write(text)
        added_lines = len(text.splitlines())
        self.logger.log(
            Event(
                event_type=FILE_EDIT,
                source="tool_adapter",
                session_id=self.session_id,
                task_id=self.task_id,
                agent_id=self.agent_id,
                payload=make_file_edit_payload(file_path, "append_text", added_lines, 0),
            )
        )
        self.logger.log(
            Event(
                event_type=TOOL_CALL_FINISHED,
                source="tool_adapter",
                session_id=self.session_id,
                task_id=self.task_id,
                agent_id=self.agent_id,
                payload={"tool_name": "append_text", "path": str(file_path)},
            )
        )

