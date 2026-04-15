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


if __name__ == "__main__":
    unittest.main()
