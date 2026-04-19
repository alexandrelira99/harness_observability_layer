from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from harness_observability_layer.plugin.api import generate_session_html, import_session, summarize_session
from harness_observability_layer.security import redact_path, sanitize_session_id
from harness_observability_layer.reporting.guided_site import build_guided_session_site
from observer.analyzer import analyze_jsonl
from reporting.html_report import build_session_report_html, report_css


class SecurityPrivacyTests(unittest.TestCase):
    def test_sanitize_session_id_blocks_path_traversal(self) -> None:
        self.assertEqual(sanitize_session_id("../evil/session"), "session")
        self.assertEqual(sanitize_session_id("..\\evil"), "evil")

    def test_redact_path_keeps_only_tail(self) -> None:
        self.assertEqual(redact_path("/tmp/project/app.py"), ".../app.py")

    def test_analyze_jsonl_can_disable_file_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source_file = tmp_path / "sample.py"
            source_file.write_text("a\nb\nc\n", encoding="utf-8")
            events_path = tmp_path / "events.jsonl"
            events_path.write_text(
                json.dumps(
                    {
                        "event_type": "file_read",
                        "payload": {"path": str(source_file), "line_start": 1, "line_end": 2},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            summary = analyze_jsonl(events_path, resolve_file_stats=False)
            meta = summary["files"][str(source_file)]
            self.assertIsNone(meta["total_lines"])
            self.assertEqual(meta["total_lines_status"], "disabled")
            self.assertEqual(summary["file_stats_resolution"], "disabled")

    def test_import_session_can_skip_raw_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            raw_session = tmp_path / "rollout-safe.jsonl"
            raw_session.write_text(
                json.dumps(
                    {
                        "type": "session_meta",
                        "timestamp": "2026-04-14T00:00:00Z",
                        "payload": {"id": "sess_1", "cwd": str(tmp_path), "source": "test"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            raw_session.write_text(
                raw_session.read_text(encoding="utf-8")
                + json.dumps(
                    {
                        "type": "event_msg",
                        "timestamp": "2026-04-14T00:00:01Z",
                        "payload": {"type": "user_message", "message": "super sensitive prompt"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            result = import_session(
                str(raw_session),
                project_root=tmp_path,
                copy_raw=False,
                resolve_file_stats=False,
            )
            session_dir = Path(result["paths"]["session_dir"])
            self.assertFalse((session_dir / "raw.codex.jsonl").exists())
            self.assertIsNone(result["paths"]["raw"])

    def test_redacted_summary_hides_prompt_and_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            raw_session = tmp_path / "rollout-sensitive.jsonl"
            raw_session.write_text(
                json.dumps(
                    {
                        "type": "session_meta",
                        "timestamp": "2026-04-14T00:00:00Z",
                        "payload": {"id": "sess_2", "cwd": "/home/user/project", "source": "test"},
                    }
                )
                + "\n"
                + json.dumps(
                    {
                        "type": "event_msg",
                        "timestamp": "2026-04-14T00:00:01Z",
                        "payload": {"type": "user_message", "message": "my credit card is 1234"},
                    }
                )
                + "\n"
                + json.dumps(
                    {
                        "type": "event_msg",
                        "timestamp": "2026-04-14T00:00:02Z",
                        "payload": {
                            "type": "exec_command_end",
                            "exit_code": 0,
                            "parsed_cmd": [{"type": "read", "cmd": "sed -n '1,2p' /home/user/project/app.py", "path": "/home/user/project/app.py"}],
                            "aggregated_output": "x\ny\n",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            result = import_session(str(raw_session), project_root=tmp_path, resolve_file_stats=False)
            redacted = summarize_session(
                session_id=result["session_id"],
                format="markdown",
                project_root=tmp_path,
                redact_sensitive=True,
            )
            self.assertIn("Redacted Session", redacted)
            self.assertNotIn("credit card", redacted)
            self.assertNotIn("/home/user/project", redacted)

    def test_html_report_uses_no_remote_assets(self) -> None:
        html = build_session_report_html(
            session_label="sess",
            summary={"tool_calls_by_name": {}, "tool_failures_by_name": {}, "files": {}, "edited_without_prior_read": [], "skill_loads_by_name": {}, "plugin_invocations_by_name": {}},
            normalized_events_file="/tmp/events.jsonl",
            events=[],
            session_metadata={"display_title": "Session", "display_subtitle": "Local only", "technical_id": "sess"},
        )
        self.assertNotIn("fonts.googleapis.com", html)
        self.assertNotIn("fonts.gstatic.com", html)

    def test_html_report_escapes_user_derived_content(self) -> None:
        html = build_session_report_html(
            session_label="sess",
            summary={
                "tool_calls_by_name": {"<script>alert(1)</script>": 1},
                "tool_failures_by_name": {},
                "files": {"</td><script>x</script>": {"union_lines_read": 1, "total_lines": None, "read_coverage_pct": None, "edit_count": 0, "added_lines": 0, "removed_lines": 0}},
                "edited_without_prior_read": [],
                "skill_loads_by_name": {},
                "plugin_invocations_by_name": {},
            },
            normalized_events_file="/tmp/events.jsonl",
            events=[],
            session_metadata={"display_title": "<b>unsafe</b>", "display_subtitle": "Local only", "technical_id": "sess"},
        )
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;b&gt;unsafe&lt;/b&gt;", html)

    def test_html_report_css_keeps_layout_left_aligned_and_prevents_callout_overflow(self) -> None:
        css = report_css()
        self.assertIn("width: min(1680px, calc(100vw - 48px));", css)
        self.assertIn("margin: 0 0 0 24px;", css)
        self.assertIn("max-width: calc(100vw - 48px);", css)
        self.assertIn("min-width: 0;", css)
        self.assertIn("overflow-wrap: anywhere;", css)

    def test_guided_site_escapes_user_derived_content(self) -> None:
        rendered = build_guided_session_site(
            session_name="sess",
            summary={
                "total_tokens": 1,
                "tool_calls_by_name": {},
                "tool_failures_by_name": {},
                "files": {},
            },
            metadata={"display_title": "<b>unsafe</b>", "display_subtitle": "Local only"},
            normalized_events_file='"><script>x</script>',
            events=[],
        )
        self.assertNotIn("<script>", rendered["index.html"])
        self.assertIn("&lt;b&gt;unsafe&lt;/b&gt;", rendered["index.html"])

    def test_guided_site_chart_payload_does_not_emit_script_tags(self) -> None:
        rendered = build_guided_session_site(
            session_name="sess",
            summary={
                "total_tokens": 1,
                "tool_calls_by_name": {},
                "tool_failures_by_name": {},
                "files": {},
                "skill_attribution": {
                    '"><script>x</script>': {"total_tokens": 1, "tool_call_count": 1}
                },
                "unattributed_activity": {"total_tokens": 0, "tool_call_count": 0},
                "attribution_shares": {},
            },
            metadata={"display_title": "Session", "display_subtitle": "Local only"},
            normalized_events_file="events.jsonl",
            events=[],
        )
        self.assertNotIn("<script>x</script>", rendered["cost-efficiency.html"])

    def test_redacted_html_hides_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            raw_session = tmp_path / "rollout-html.jsonl"
            raw_session.write_text(
                json.dumps(
                    {
                        "type": "session_meta",
                        "timestamp": "2026-04-14T00:00:00Z",
                        "payload": {"id": "sess_html", "cwd": "/very/secret/project", "source": "test"},
                    }
                )
                + "\n"
                + json.dumps(
                    {
                        "type": "event_msg",
                        "timestamp": "2026-04-14T00:00:01Z",
                        "payload": {
                            "type": "exec_command_end",
                            "exit_code": 0,
                            "parsed_cmd": [{"type": "read", "cmd": "sed -n '1,1p' /very/secret/project/app.py", "path": "/very/secret/project/app.py"}],
                            "aggregated_output": "x\n",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            result = import_session(str(raw_session), project_root=tmp_path, resolve_file_stats=False)
            generate_session_html(result["session_id"], project_root=tmp_path, redact_sensitive=True)
            html = (Path(result["paths"]["session_dir"]) / "report.html").read_text(encoding="utf-8")
            self.assertNotIn("/very/secret/project", html)
            self.assertIn("[redacted]", html)

    def test_import_ignores_malformed_jsonl_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            raw_session = tmp_path / "rollout-malformed.jsonl"
            raw_session.write_text(
                '{"type":"session_meta","timestamp":"2026-04-14T00:00:00Z","payload":{"id":"sess_bad","cwd":"/tmp","source":"test"}}\n'
                + 'not-json-at-all\n'
                + '{"type":"event_msg","timestamp":"2026-04-14T00:00:01Z","payload":{"type":"user_message","message":"ok"}}\n',
                encoding="utf-8",
            )
            result = import_session(str(raw_session), project_root=tmp_path, copy_raw=False, resolve_file_stats=False)
            summary = json.loads(Path(result["paths"]["summary"]).read_text(encoding="utf-8"))
            self.assertGreaterEqual(summary["total_events"], 2)


if __name__ == "__main__":
    unittest.main()
