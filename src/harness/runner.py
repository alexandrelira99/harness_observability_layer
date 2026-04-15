"""Minimal harness runner that emits canonical events."""

from __future__ import annotations

from dataclasses import dataclass

from observer.events import Event
from observer.logger import JsonlEventLogger
from observer.schemas import AGENT_MESSAGE, SESSION_FINISHED, SESSION_STARTED, TASK_FINISHED, TASK_STARTED


@dataclass(slots=True)
class RunContext:
    """A small execution context for a single task."""

    session_id: str
    task_id: str
    agent_id: str = "main"


class HarnessRunner:
    """A small runner that emits basic lifecycle and message events."""

    def __init__(self, logger: JsonlEventLogger):
        self.logger = logger

    def start_session(self, ctx: RunContext) -> None:
        self.logger.log(Event(event_type=SESSION_STARTED, source="harness", session_id=ctx.session_id, task_id=ctx.task_id, agent_id=ctx.agent_id))

    def finish_session(self, ctx: RunContext) -> None:
        self.logger.log(Event(event_type=SESSION_FINISHED, source="harness", session_id=ctx.session_id, task_id=ctx.task_id, agent_id=ctx.agent_id))

    def start_task(self, ctx: RunContext, prompt: str) -> None:
        self.logger.log(Event(event_type=TASK_STARTED, source="harness", session_id=ctx.session_id, task_id=ctx.task_id, agent_id=ctx.agent_id, payload={"prompt": prompt}))

    def finish_task(self, ctx: RunContext, outcome: str) -> None:
        self.logger.log(Event(event_type=TASK_FINISHED, source="harness", session_id=ctx.session_id, task_id=ctx.task_id, agent_id=ctx.agent_id, payload={"outcome": outcome}))

    def agent_message(self, ctx: RunContext, message: str) -> None:
        self.logger.log(Event(event_type=AGENT_MESSAGE, source="harness", session_id=ctx.session_id, task_id=ctx.task_id, agent_id=ctx.agent_id, payload={"message": message}))

