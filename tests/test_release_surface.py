from __future__ import annotations

import contextlib
import http.client
import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import tomllib
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from harness_observability_layer.cli.main import build_parser, main
from harness_observability_layer.plugin.api import load_live_dashboard_data
from harness_observability_layer.server import create_server


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

    def _write_codex_session(self, root: Path, project_root: Path, name: str, message: str) -> Path:
        path = root / f"{name}.jsonl"
        path.write_text(
            json.dumps(
                {
                    "type": "session_meta",
                    "timestamp": "2026-04-20T00:00:00Z",
                    "payload": {"id": name, "cwd": str(project_root), "source": "codex"},
                }
            )
            + "\n"
            + json.dumps(
                {
                    "type": "event_msg",
                    "timestamp": "2026-04-20T00:00:01Z",
                    "payload": {"type": "user_message", "message": message},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return path

    def _write_claude_session(
        self, root: Path, project_root: Path, project_name: str, name: str, message: str
    ) -> Path:
        project_dir = root / project_name
        project_dir.mkdir(parents=True, exist_ok=True)
        path = project_dir / f"{name}.jsonl"
        path.write_text(
            json.dumps(
                {
                    "sessionId": name,
                    "cwd": str(project_root),
                    "timestamp": "2026-04-20T00:00:00Z",
                    "type": "user",
                    "message": {"content": [{"type": "text", "text": message}]},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return path

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
        self.assertEqual(
            data["tool"]["setuptools"]["packages"]["find"]["include"],
            ["harness_observability_layer*"],
        )

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

    def test_build_parser_exposes_simple_init_and_data_commands(self) -> None:
        parser = build_parser()
        actions = [action for action in parser._actions if getattr(action, "choices", None)]
        command_action = actions[-1]
        self.assertEqual(sorted(command_action.choices.keys()), ["data", "init"])

    def test_live_dashboard_data_loads_codex_and_claude_without_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            project_root = tmp_path / "project"
            codex_root = tmp_path / "codex-archive"
            claude_root = tmp_path / "claude-projects"
            project_root.mkdir()
            codex_root.mkdir()
            claude_root.mkdir()
            self._write_codex_session(codex_root, project_root, "rollout-a", "hello codex")
            self._write_claude_session(
                claude_root, project_root, "project", "claude-a", "hello claude"
            )

            with mock.patch.dict(
                os.environ,
                {
                    "HOL_CODEX_ARCHIVED_DIR": str(codex_root),
                    "HOL_CLAUDE_ARCHIVED_DIR": str(claude_root),
                },
                clear=False,
            ):
                aggregate = load_live_dashboard_data(project_root)

            self.assertEqual(aggregate["totals"]["sessions"], 2)
            self.assertFalse((project_root / "hol-artifacts").exists())
            sources = {item["source_name"] for item in aggregate["session_rankings"]}
            self.assertIn("Codex", sources)
            self.assertIn("Claude Code", sources)

    def test_cli_data_outputs_live_aggregate_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            project_root = tmp_path / "project"
            codex_root = tmp_path / "codex-archive"
            project_root.mkdir()
            codex_root.mkdir()
            self._write_codex_session(codex_root, project_root, "rollout-a", "hello codex")

            with mock.patch.dict(
                os.environ,
                {"HOL_CODEX_ARCHIVED_DIR": str(codex_root)},
                clear=False,
            ):
                output = self._run_cli(["data"], cwd=project_root)

            parsed = json.loads(output)
            self.assertEqual(parsed["totals"]["sessions"], 1)
            self.assertIn("top_prompt_groups", parsed)
            self.assertFalse((project_root / "hol-artifacts").exists())

    def test_server_exposes_html_and_json_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            project_root = tmp_path / "project"
            codex_root = tmp_path / "codex-archive"
            project_root.mkdir()
            codex_root.mkdir()
            self._write_codex_session(codex_root, project_root, "rollout-a", "hello codex")

            with mock.patch.dict(
                os.environ,
                {"HOL_CODEX_ARCHIVED_DIR": str(codex_root)},
                clear=False,
            ):
                server = create_server(
                    host="127.0.0.1",
                    port=0,
                    project_root=str(project_root),
                    resolve_file_stats=False,
                )
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                    conn.request("GET", "/")
                    response = conn.getresponse()
                    html = response.read().decode("utf-8")
                    self.assertEqual(response.status, 200)
                    self.assertIn("Project Dashboard", html)
                    self.assertIn("/api/data", html)
                    conn.close()

                    conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                    conn.request("GET", "/api/data")
                    response = conn.getresponse()
                    payload = json.loads(response.read().decode("utf-8"))
                    self.assertEqual(response.status, 200)
                    self.assertEqual(payload["totals"]["sessions"], 1)
                    conn.close()

                    conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                    conn.request("GET", "/api/refresh")
                    response = conn.getresponse()
                    payload = json.loads(response.read().decode("utf-8"))
                    self.assertEqual(response.status, 200)
                    self.assertTrue(payload["ok"])
                    self.assertEqual(payload["sessions"], 1)
                    conn.close()
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()

