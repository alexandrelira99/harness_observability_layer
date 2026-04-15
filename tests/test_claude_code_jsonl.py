from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from integrations.claude_code_jsonl import normalize_claude_code_records
from observer.metrics import compute_metrics


class ClaudeCodeJsonlNormalizationTests(unittest.TestCase):
    def test_observed_primary_session_blocks_become_tool_calls(self) -> None:
        records = [
            {
                "type": "user",
                "timestamp": "2026-04-15T12:29:10.596Z",
                "sessionId": "claude-observer-1",
                "message": {
                    "role": "user",
                    "content": (
                        "<observed_from_primary_session>\n"
                        "  <what_happened>exec_command</what_happened>\n"
                        "  <occurred_at>2026-04-15T12:29:00.521Z</occurred_at>\n"
                        "  <parameters>\"{\\\"cmd\\\":\\\"sed -n '1,80p' requirements.txt\\\",\\\"workdir\\\":\\\"/tmp/project\\\"}\"</parameters>\n"
                        "  <outcome>\"\\\"Chunk ID: abc123\\\\nWall time: 0.0000 seconds\\\\nProcess exited with code 0\\\\nOriginal token count: 2\\\\nOutput:\\\\na\\\\nb\\\\n\\\"\"</outcome>\n"
                        "</observed_from_primary_session>\n"
                        "<observed_from_primary_session>\n"
                        "  <what_happened>exec_command</what_happened>\n"
                        "  <occurred_at>2026-04-15T12:30:28.876Z</occurred_at>\n"
                        "  <parameters>\"{\\\"cmd\\\":\\\"rg -n \\\\\\\"fullchain.pem\\\\\\\" -S backend/ops\\\"}\"</parameters>\n"
                        "  <outcome>\"\\\"Chunk ID: def456\\\\nWall time: 0.1192 seconds\\\\nProcess exited with code 0\\\\nOriginal token count: 10\\\\nOutput:\\\\nbackend/ops/lightsail-deploy.sh:206:if [[ -f /etc/letsencrypt/live/$DOMAIN_NAME/fullchain.pem ]]; then\\\\n\\\"\"</outcome>\n"
                        "</observed_from_primary_session>\n"
                        "<observed_from_primary_session>\n"
                        "  <what_happened>write_stdin</what_happened>\n"
                        "  <occurred_at>2026-04-15T12:29:07.277Z</occurred_at>\n"
                        "  <parameters>\"{\\\"session_id\\\":77660,\\\"chars\\\":\\\"\\\"}\"</parameters>\n"
                        "  <outcome>\"\\\"Chunk ID: ghi789\\\\nWall time: 0.0000 seconds\\\\nProcess exited with code 7\\\\nOriginal token count: 3\\\\nOutput:\\\\ncurl: (7) Failed to connect\\\\n\\\"\"</outcome>\n"
                        "</observed_from_primary_session>\n"
                    ),
                },
            }
        ]

        events = [event.to_dict() for event in normalize_claude_code_records(records)]
        summary = compute_metrics(events, resolve_file_stats=False)

        self.assertEqual(summary["tool_calls_by_name"]["exec_command"], 2)
        self.assertEqual(summary["tool_calls_by_name"]["write_stdin"], 1)
        self.assertEqual(summary["tool_failures_by_name"]["write_stdin"], 1)
        self.assertEqual(summary["distinct_files_read"], 1)
        self.assertEqual(summary["files"]["requirements.txt"]["union_lines_read"], 2)

    def test_observed_rg_generates_file_search_without_file_summary_entry(self) -> None:
        records = [
            {
                "type": "user",
                "timestamp": "2026-04-15T12:30:28.876Z",
                "sessionId": "claude-observer-2",
                "message": {
                    "role": "user",
                    "content": (
                        "<observed_from_primary_session>\n"
                        "  <what_happened>exec_command</what_happened>\n"
                        "  <occurred_at>2026-04-15T12:30:28.876Z</occurred_at>\n"
                        "  <parameters>\"{\\\"cmd\\\":\\\"rg -n \\\\\\\"fullchain.pem\\\\\\\" -S backend/ops\\\"}\"</parameters>\n"
                        "  <outcome>\"\\\"Chunk ID: def456\\\\nWall time: 0.1192 seconds\\\\nProcess exited with code 0\\\\nOriginal token count: 10\\\\nOutput:\\\\nbackend/ops/lightsail-deploy.sh:206:if [[ -f /etc/letsencrypt/live/$DOMAIN_NAME/fullchain.pem ]]; then\\\\n\\\"\"</outcome>\n"
                        "</observed_from_primary_session>\n"
                    ),
                },
            }
        ]

        events = [event.to_dict() for event in normalize_claude_code_records(records)]

        file_search_events = [event for event in events if event["event_type"] == "file_search"]
        self.assertEqual(len(file_search_events), 1)
        self.assertEqual(file_search_events[0]["payload"]["query"], "fullchain.pem")
        self.assertEqual(file_search_events[0]["payload"]["path"], "backend/ops")


if __name__ == "__main__":
    unittest.main()
