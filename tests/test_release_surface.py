from __future__ import annotations

import contextlib
import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from harness_observability_layer.cli.main import main
from harness_observability_layer.plugin.api import import_all_sessions, import_latest_session


class ReleaseSurfaceTests(unittest.TestCase):
    def _run_cli(self, argv: list[str], *, cwd: Path) -> str:
        stdout = io.StringIO()
        old_argv = sys.argv[:]
        try:
            sys.argv = ["hol", "--project-root", str(cwd), *argv]
            with contextlib.redirect_stdout(stdout):
                main()
        finally:
            sys.argv = old_argv
        return stdout.getvalue()

    def test_pyproject_has_public_release_metadata(self) -> None:
        data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        project = data["project"]
        self.assertEqual(project["name"], "harness-observability-layer")
        self.assertTrue(project["license"]["file"])
        self.assertIn("classifiers", project)
        self.assertIn("keywords", project)
        self.assertIn("urls", project)
        self.assertIn("dev", project["optional-dependencies"])
        self.assertIn("hol", project["scripts"])
        self.assertEqual(data["tool"]["setuptools"]["packages"]["find"]["include"], ["harness_observability_layer*"])

    def test_package_import_has_no_side_effect_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env = os.environ.copy()
            env["PYTHONPATH"] = str(SRC)
            subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "import harness_observability_layer; "
                    "from harness_observability_layer.cli.main import build_parser; "
                    "build_parser()",
                ],
                cwd=tmp_path,
                env=env,
                check=True,
            )
            self.assertEqual(list(tmp_path.iterdir()), [])

    def test_cli_import_analyze_and_report_work_offline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            raw_session = tmp_path / "rollout-offline.jsonl"
            raw_session.write_text(
                json.dumps(
                    {
                        "type": "session_meta",
                        "timestamp": "2026-04-15T00:00:00Z",
                        "payload": {"id": "sess_offline", "cwd": str(tmp_path), "source": "test"},
                    }
                )
                + "\n"
                + json.dumps(
                    {
                        "type": "event_msg",
                        "timestamp": "2026-04-15T00:00:01Z",
                        "payload": {"type": "user_message", "message": "offline check"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            def fail_network(*args, **kwargs):  # type: ignore[no-untyped-def]
                raise AssertionError("network access is not expected in offline CLI flows")

            with mock.patch.object(socket, "create_connection", side_effect=fail_network), mock.patch.object(
                socket.socket,
                "connect",
                autospec=True,
                side_effect=fail_network,
            ):
                import_output = self._run_cli(["import", "session", str(raw_session), "--no-resolve-files"], cwd=tmp_path)
                analyze_output = self._run_cli(
                    ["analyze", "session", "rollout-offline", "--format", "markdown", "--no-resolve-files"],
                    cwd=tmp_path,
                )
                report_output = self._run_cli(
                    ["report", "summary", "rollout-offline", "--format", "json", "--no-resolve-files"],
                    cwd=tmp_path,
                )

            self.assertIn('"session_id": "rollout-offline"', import_output)
            self.assertIn("- Tool calls: 0", analyze_output)
            self.assertIn('"session_id": "rollout-offline"', report_output)
            self.assertTrue((tmp_path / "hol-artifacts" / "sessions" / "rollout-offline" / "report.html").exists())

    def test_import_all_only_imports_sessions_for_current_project_or_without_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            archive_root = tmp_path / "archive"
            project_root = tmp_path / "project-a"
            other_root = tmp_path / "project-b"
            archive_root.mkdir()
            project_root.mkdir()
            other_root.mkdir()

            matching = archive_root / "rollout-matching.jsonl"
            matching.write_text(
                json.dumps(
                    {
                        "type": "session_meta",
                        "timestamp": "2026-04-16T00:00:00Z",
                        "payload": {"id": "sess_match", "cwd": str(project_root), "source": "codex"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            other = archive_root / "rollout-other.jsonl"
            other.write_text(
                json.dumps(
                    {
                        "type": "session_meta",
                        "timestamp": "2026-04-16T00:00:00Z",
                        "payload": {"id": "sess_other", "cwd": str(other_root), "source": "codex"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            missing_cwd = archive_root / "rollout-missing-cwd.jsonl"
            missing_cwd.write_text(
                json.dumps(
                    {
                        "type": "session_meta",
                        "timestamp": "2026-04-16T00:00:00Z",
                        "payload": {"id": "sess_unknown", "source": "codex"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            result = import_all_sessions(str(archive_root), project_root=project_root, resolve_file_stats=False)

            self.assertEqual(result["imported_count"], 2)
            self.assertEqual(
                sorted(result["imported_sessions"]),
                ["rollout-matching", "rollout-missing-cwd"],
            )
            self.assertFalse((project_root / "hol-artifacts" / "sessions" / "rollout-other").exists())

    def test_import_latest_skips_newer_other_project_session_but_keeps_missing_cwd_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            archive_root = tmp_path / "archive"
            project_root = tmp_path / "project-a"
            other_root = tmp_path / "project-b"
            archive_root.mkdir()
            project_root.mkdir()
            other_root.mkdir()

            matching = archive_root / "rollout-matching.jsonl"
            matching.write_text(
                json.dumps(
                    {
                        "type": "session_meta",
                        "timestamp": "2026-04-16T00:00:00Z",
                        "payload": {"id": "sess_match", "cwd": str(project_root), "source": "codex"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            missing_cwd = archive_root / "rollout-missing-cwd.jsonl"
            missing_cwd.write_text(
                json.dumps(
                    {
                        "type": "session_meta",
                        "timestamp": "2026-04-16T00:00:00Z",
                        "payload": {"id": "sess_unknown", "source": "codex"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            other = archive_root / "rollout-other.jsonl"
            other.write_text(
                json.dumps(
                    {
                        "type": "session_meta",
                        "timestamp": "2026-04-16T00:00:00Z",
                        "payload": {"id": "sess_other", "cwd": str(other_root), "source": "codex"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            os.utime(matching, (1, 1))
            os.utime(missing_cwd, (2, 2))
            os.utime(other, (3, 3))

            result = import_latest_session(str(archive_root), project_root=project_root, resolve_file_stats=False)

            self.assertEqual(result["session_id"], "rollout-missing-cwd")
            self.assertTrue((project_root / "hol-artifacts" / "sessions" / "rollout-missing-cwd").exists())
            self.assertFalse((project_root / "hol-artifacts" / "sessions" / "rollout-other").exists())

    def test_claude_imports_only_current_project_sessions_or_missing_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            archive_root = tmp_path / "claude-projects"
            project_root = tmp_path / "project-a"
            other_root = tmp_path / "project-b"
            archive_root.mkdir()
            project_root.mkdir()
            other_root.mkdir()

            matching = archive_root / "project-a" / "matching.jsonl"
            matching.parent.mkdir(parents=True)
            matching.write_text(
                json.dumps(
                    {
                        "sessionId": "claude-match",
                        "cwd": str(project_root),
                        "timestamp": "2026-04-16T00:00:00Z",
                        "type": "user",
                        "message": {"content": [{"type": "text", "text": "hello"}]},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            missing_cwd = archive_root / "project-a" / "missing-cwd.jsonl"
            missing_cwd.write_text(
                json.dumps(
                    {
                        "sessionId": "claude-unknown",
                        "timestamp": "2026-04-16T00:00:00Z",
                        "type": "user",
                        "message": {"content": [{"type": "text", "text": "hello"}]},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            other = archive_root / "project-b" / "other.jsonl"
            other.parent.mkdir(parents=True)
            other.write_text(
                json.dumps(
                    {
                        "sessionId": "claude-other",
                        "cwd": str(other_root),
                        "timestamp": "2026-04-16T00:00:00Z",
                        "type": "user",
                        "message": {"content": [{"type": "text", "text": "hello"}]},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            all_result = import_all_sessions(
                str(archive_root),
                project_root=project_root,
                source="claude",
                resolve_file_stats=False,
            )
            latest_result = import_latest_session(
                str(archive_root),
                project_root=project_root,
                source="claude",
                resolve_file_stats=False,
            )

            self.assertEqual(all_result["imported_count"], 2)
            self.assertEqual(
                sorted(all_result["imported_sessions"]),
                ["claude-matching", "claude-missing-cwd"],
            )
            self.assertIn(latest_result["session_id"], {"claude-matching", "claude-missing-cwd"})
            self.assertFalse((project_root / "hol-artifacts" / "sessions" / "claude-other").exists())


if __name__ == "__main__":
    unittest.main()
