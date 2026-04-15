"""Helpers to normalize raw tool activity into canonical payloads."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict


def normalize_path(path: str | Path) -> str:
    """Return a normalized string path."""
    return str(Path(path))


def make_file_read_payload(
    path: str | Path,
    line_start: int,
    line_end: int,
    read_method: str,
    bytes_read: int,
) -> Dict[str, Any]:
    """Create a canonical file read payload."""
    return {
        "path": normalize_path(path),
        "line_start": line_start,
        "line_end": line_end,
        "read_method": read_method,
        "bytes": bytes_read,
    }


def make_file_edit_payload(
    path: str | Path,
    edit_method: str,
    added_lines: int,
    removed_lines: int,
) -> Dict[str, Any]:
    """Create a canonical file edit payload."""
    return {
        "path": normalize_path(path),
        "edit_method": edit_method,
        "added_lines": added_lines,
        "removed_lines": removed_lines,
    }

