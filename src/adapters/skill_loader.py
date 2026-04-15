"""Observable skill loading."""

from __future__ import annotations

from observer.events import Event
from observer.logger import JsonlEventLogger
from observer.schemas import PLUGIN_INVOKED, SKILL_LOADED


class SkillLoader:
    """Emit canonical events when a skill or plugin is activated."""

    def __init__(self, logger: JsonlEventLogger, session_id: str, task_id: str, agent_id: str = "main"):
        self.logger = logger
        self.session_id = session_id
        self.task_id = task_id
        self.agent_id = agent_id

    def load_skill(self, skill_name: str, skill_path: str) -> None:
        """Record skill activation."""
        self.logger.log(
            Event(
                event_type=SKILL_LOADED,
                source="harness",
                session_id=self.session_id,
                task_id=self.task_id,
                agent_id=self.agent_id,
                payload={"skill_name": skill_name, "skill_path": skill_path},
            )
        )

    def invoke_plugin(self, plugin_name: str, action: str) -> None:
        """Record plugin usage."""
        self.logger.log(
            Event(
                event_type=PLUGIN_INVOKED,
                source="harness",
                session_id=self.session_id,
                task_id=self.task_id,
                agent_id=self.agent_id,
                payload={"plugin_name": plugin_name, "action": action},
            )
        )

