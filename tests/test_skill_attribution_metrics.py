from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from harness_observability_layer.observer.metrics import compute_metrics


class SkillAttributionMetricsTests(unittest.TestCase):
    def test_compute_metrics_derives_skill_and_unattributed_segments(self) -> None:
        events = [
            {
                "event_type": "user_message",
                "ts": "2026-04-19T00:00:00Z",
                "payload": {"message": "do work"},
            },
            {
                "event_type": "skill_loaded",
                "ts": "2026-04-19T00:00:01Z",
                "payload": {"skill_name": "brainstorming"},
            },
            {
                "event_type": "tool_call_started",
                "ts": "2026-04-19T00:00:02Z",
                "payload": {"tool_name": "exec_command", "call_id": "1", "arguments": {}},
            },
            {
                "event_type": "tool_call_finished",
                "ts": "2026-04-19T00:00:03Z",
                "payload": {"tool_name": "exec_command", "call_id": "1"},
            },
            {
                "event_type": "agent_message",
                "ts": "2026-04-19T00:00:04Z",
                "payload": {
                    "message": "done",
                    "usage": {
                        "input_tokens": 100,
                        "output_tokens": 25,
                        "cache_creation_input_tokens": 0,
                        "cache_read_input_tokens": 300,
                    },
                },
            },
            {
                "event_type": "user_message",
                "ts": "2026-04-19T00:00:05Z",
                "payload": {"message": "next"},
            },
        ]

        summary = compute_metrics(events, resolve_file_stats=False)

        self.assertIn("skill_attribution", summary)
        self.assertIn("brainstorming", summary["skill_attribution"])
        self.assertIn("unattributed_activity", summary)
        self.assertIn("attribution_segments", summary)
        self.assertGreaterEqual(len(summary["attribution_segments"]), 2)

    def test_compute_metrics_reports_skill_attributed_shares(self) -> None:
        events = [
            {
                "event_type": "skill_loaded",
                "ts": "2026-04-19T00:00:01Z",
                "payload": {"skill_name": "writing-plans"},
            },
            {
                "event_type": "tool_call_started",
                "ts": "2026-04-19T00:00:02Z",
                "payload": {"tool_name": "update_plan", "call_id": "p1", "arguments": {}},
            },
            {
                "event_type": "tool_call_finished",
                "ts": "2026-04-19T00:00:03Z",
                "payload": {"tool_name": "update_plan", "call_id": "p1"},
            },
            {
                "event_type": "task_finished",
                "ts": "2026-04-19T00:00:04Z",
                "task_id": "t1",
                "payload": {
                    "usage": {
                        "input_tokens": 200,
                        "output_tokens": 100,
                        "cache_creation_input_tokens": 0,
                        "cache_read_input_tokens": 400,
                    }
                },
            },
        ]

        summary = compute_metrics(events, resolve_file_stats=False)
        self.assertIn("attribution_shares", summary)
        self.assertGreater(summary["attribution_shares"]["skill_attributed_token_pct"], 0)

    def test_compute_metrics_keeps_all_activity_unattributed_when_no_skill_loaded(
        self,
    ) -> None:
        events = [
            {
                "event_type": "tool_call_started",
                "ts": "2026-04-19T00:00:01Z",
                "payload": {"tool_name": "exec_command", "call_id": "1", "arguments": {}},
            },
            {
                "event_type": "tool_call_finished",
                "ts": "2026-04-19T00:00:02Z",
                "payload": {"tool_name": "exec_command", "call_id": "1"},
            },
        ]
        summary = compute_metrics(events, resolve_file_stats=False)
        self.assertEqual(summary["skill_attribution"], {})
        self.assertEqual(summary["unattributed_activity"]["tool_call_count"], 1)


if __name__ == "__main__":
    unittest.main()
