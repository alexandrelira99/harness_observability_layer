"""Registry for loaded skills."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SkillRef:
    """Simple skill reference."""

    name: str
    path: str

