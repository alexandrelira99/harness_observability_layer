"""Registry for wrapped tool callables."""

from __future__ import annotations

from typing import Callable, Dict


class ToolRegistry:
    """Store named callables representing tools."""

    def __init__(self):
        self._tools: Dict[str, Callable] = {}

    def register(self, name: str, tool: Callable) -> None:
        self._tools[name] = tool

    def get(self, name: str) -> Callable:
        return self._tools[name]

