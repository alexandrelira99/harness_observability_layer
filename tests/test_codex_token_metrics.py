from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from harness_observability_layer.integrations.codex_jsonl import normalize_codex_records
from harness_observability_layer.observer.metrics import compute_metrics
from harness_observability_layer.observer.schemas import FILE_READ, SKILL_LOADED
from harness_observability_layer.reporting.html_report import build_session_report_html


class CodexTokenMetricsTests(unittest.TestCase):
    def _sample_records(self) -> list[dict]:
        return [
            {
                "timestamp": "2026-04-14T00:26:20.467Z",
                "type": "session_meta",
                "payload": {
                    "id": "codex-session-1",
                    "cwd": "/tmp/project",
                },
            },
            {
                "timestamp": "2026-04-14T00:26:20.474Z",
                "type": "turn_context",
                "payload": {"model": "gpt-5.4"},
            },
            {
                "timestamp": "2026-04-14T00:26:20.475Z",
                "type": "turn.started",
            },
            {
                "timestamp": "2026-04-14T01:14:04.166Z",
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "info": {
                        "total_token_usage": {
                            "input_tokens": 4_436_546,
                            "cached_input_tokens": 3_951_232,
                            "output_tokens": 32_159,
                            "total_tokens": 4_468_705,
                        }
                    },
                    "rate_limits": {"plan_type": "plus"},
                },
            },
            {
                "timestamp": "2026-04-14T01:14:04.500Z",
                "type": "item.completed",
                "item": {
                    "type": "agent_message",
                    "text": "done",
                },
            },
            {
                "timestamp": "2026-04-14T01:14:05.000Z",
                "type": "turn.completed",
                "usage": {},
            },
        ]

    def test_codex_cached_input_is_not_double_counted(self) -> None:
        events = [event.to_dict() for event in normalize_codex_records(self._sample_records())]

        summary = compute_metrics(events, resolve_file_stats=False)

        self.assertEqual(summary["total_input_tokens"], 485_314)
        self.assertEqual(summary["total_cache_read_tokens"], 3_951_232)
        self.assertEqual(summary["total_output_tokens"], 32_159)
        self.assertEqual(summary["total_tokens"], 4_468_705)
        self.assertAlmostEqual(summary["cache_hit_rate_pct"], 89.06, places=2)
        self.assertAlmostEqual(summary["estimated_cost_usd"], 2.6835, places=4)

    def test_html_report_shows_cache_tokens_when_present(self) -> None:
        html = build_session_report_html(
            session_label="codex-session-1",
            summary={
                "total_tool_calls": 0,
                "distinct_files_read": 0,
                "distinct_files_edited": 0,
                "total_tokens": 4_468_705,
                "total_input_tokens": 485_314,
                "total_output_tokens": 32_159,
                "total_cache_read_tokens": 3_951_232,
                "estimated_cost_usd": 2.6835,
                "cache_hit_rate_pct": 89.06,
                "session_duration_seconds": 1,
                "turns_per_session": 1,
                "max_concurrent_tool_calls": 0,
                "model": "gpt-5.4",
                "tool_calls_by_name": {},
                "tool_failures_by_name": {},
                "files": {},
                "edited_without_prior_read": [],
                "read_without_edit": [],
                "reread_files": [],
                "skill_loads_by_name": {},
                "plugin_invocations_by_name": {},
                "efficiency_indicators": {},
                "stop_reasons": {},
                "bash_command_categories": {},
                "skills_without_followup": [],
                "tool_failure_rate_by_name": {},
            },
            normalized_events_file="/tmp/normalized.events.jsonl",
        )

        self.assertIn("485.3K in / 4.0M cache / 32.2K out", html)

    def test_codex_skill_file_reads_emit_skill_loaded_events(self) -> None:
        records = [
            {
                "timestamp": "2026-04-19T15:13:01.302Z",
                "type": "session_meta",
                "payload": {
                    "id": "codex-skill-session",
                    "cwd": "/tmp/project",
                },
            },
            {
                "timestamp": "2026-04-19T15:13:11.119Z",
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "name": "exec_command",
                    "arguments": "{\"cmd\":\"sed -n '1,220p' /home/alexandre/.codex/superpowers/skills/using-superpowers/SKILL.md\"}",
                    "call_id": "call_skill_read",
                },
            },
            {
                "timestamp": "2026-04-19T15:13:11.269Z",
                "type": "event_msg",
                "payload": {
                    "type": "exec_command_end",
                    "call_id": "call_skill_read",
                    "turn_id": "turn-1",
                    "exit_code": 0,
                    "parsed_cmd": [
                        {
                            "type": "read",
                            "cmd": "sed -n '1,220p' /home/alexandre/.codex/superpowers/skills/using-superpowers/SKILL.md",
                            "name": "SKILL.md",
                            "path": "/home/alexandre/.codex/superpowers/skills/using-superpowers/SKILL.md",
                        }
                    ],
                    "aggregated_output": "---\nname: using-superpowers\n---\n",
                },
            },
        ]

        events = [event.to_dict() for event in normalize_codex_records(records)]

        file_reads = [event for event in events if event["event_type"] == FILE_READ]
        skill_loads = [event for event in events if event["event_type"] == SKILL_LOADED]

        self.assertEqual(len(file_reads), 1)
        self.assertEqual(len(skill_loads), 1)
        self.assertEqual(skill_loads[0]["payload"]["skill_name"], "using-superpowers")

    def test_codex_task_usage_uses_incremental_token_deltas(self) -> None:
        records = [
            {
                "timestamp": "2026-04-19T15:13:01.302Z",
                "type": "session_meta",
                "payload": {"id": "codex-deltas", "cwd": "/tmp/project"},
            },
            {
                "timestamp": "2026-04-19T15:13:01.306Z",
                "type": "event_msg",
                "payload": {
                    "type": "task_started",
                    "turn_id": "task-1",
                    "model_context_window": 258400,
                    "collaboration_mode_kind": "default",
                },
            },
            {
                "timestamp": "2026-04-19T15:13:01.307Z",
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "name": "exec_command",
                    "arguments": "{\"cmd\":\"sed -n '1,120p' /home/alexandre/.codex/superpowers/skills/brainstorming/SKILL.md\"}",
                    "call_id": "call_skill_1",
                },
            },
            {
                "timestamp": "2026-04-19T15:13:01.400Z",
                "type": "event_msg",
                "payload": {
                    "type": "exec_command_end",
                    "call_id": "call_skill_1",
                    "turn_id": "task-1",
                    "exit_code": 0,
                    "parsed_cmd": [
                        {
                            "type": "read",
                            "cmd": "sed -n '1,120p' /home/alexandre/.codex/superpowers/skills/brainstorming/SKILL.md",
                            "name": "SKILL.md",
                            "path": "/home/alexandre/.codex/superpowers/skills/brainstorming/SKILL.md",
                        }
                    ],
                    "aggregated_output": "---\nname: brainstorming\n---\n",
                },
            },
            {
                "timestamp": "2026-04-19T15:13:05.000Z",
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "info": {
                        "total_token_usage": {
                            "input_tokens": 1000,
                            "cached_input_tokens": 700,
                            "output_tokens": 100,
                            "total_tokens": 1100,
                        }
                    },
                },
            },
            {
                "timestamp": "2026-04-19T15:13:05.100Z",
                "type": "event_msg",
                "payload": {
                    "type": "task_complete",
                    "turn_id": "task-1",
                    "last_agent_message": "done 1",
                },
            },
            {
                "timestamp": "2026-04-19T15:14:01.306Z",
                "type": "event_msg",
                "payload": {
                    "type": "task_started",
                    "turn_id": "task-2",
                    "model_context_window": 258400,
                    "collaboration_mode_kind": "default",
                },
            },
            {
                "timestamp": "2026-04-19T15:14:01.307Z",
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "name": "exec_command",
                    "arguments": "{\"cmd\":\"sed -n '1,120p' /home/alexandre/.codex/superpowers/skills/writing-plans/SKILL.md\"}",
                    "call_id": "call_skill_2",
                },
            },
            {
                "timestamp": "2026-04-19T15:14:01.400Z",
                "type": "event_msg",
                "payload": {
                    "type": "exec_command_end",
                    "call_id": "call_skill_2",
                    "turn_id": "task-2",
                    "exit_code": 0,
                    "parsed_cmd": [
                        {
                            "type": "read",
                            "cmd": "sed -n '1,120p' /home/alexandre/.codex/superpowers/skills/writing-plans/SKILL.md",
                            "name": "SKILL.md",
                            "path": "/home/alexandre/.codex/superpowers/skills/writing-plans/SKILL.md",
                        }
                    ],
                    "aggregated_output": "---\nname: writing-plans\n---\n",
                },
            },
            {
                "timestamp": "2026-04-19T15:14:05.000Z",
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "info": {
                        "total_token_usage": {
                            "input_tokens": 1800,
                            "cached_input_tokens": 1200,
                            "output_tokens": 180,
                            "total_tokens": 1980,
                        }
                    },
                },
            },
            {
                "timestamp": "2026-04-19T15:14:05.100Z",
                "type": "event_msg",
                "payload": {
                    "type": "task_complete",
                    "turn_id": "task-2",
                    "last_agent_message": "done 2",
                },
            },
        ]

        events = [event.to_dict() for event in normalize_codex_records(records)]
        summary = compute_metrics(events, resolve_file_stats=False)

        self.assertEqual(summary["skill_attribution"]["brainstorming"]["total_tokens"], 1100)
        self.assertEqual(summary["skill_attribution"]["writing-plans"]["total_tokens"], 880)
        self.assertEqual(summary["total_tokens"], 1980)

    def test_codex_token_counts_are_attributed_within_a_task(self) -> None:
        records = [
            {
                "timestamp": "2026-04-19T15:13:01.302Z",
                "type": "session_meta",
                "payload": {"id": "codex-segment-deltas", "cwd": "/tmp/project"},
            },
            {
                "timestamp": "2026-04-19T15:13:01.306Z",
                "type": "event_msg",
                "payload": {
                    "type": "task_started",
                    "turn_id": "task-1",
                    "model_context_window": 258400,
                    "collaboration_mode_kind": "default",
                },
            },
            {
                "timestamp": "2026-04-19T15:13:01.307Z",
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "name": "exec_command",
                    "arguments": "{\"cmd\":\"sed -n '1,120p' /home/alexandre/.codex/superpowers/skills/brainstorming/SKILL.md\"}",
                    "call_id": "call_skill_1",
                },
            },
            {
                "timestamp": "2026-04-19T15:13:01.400Z",
                "type": "event_msg",
                "payload": {
                    "type": "exec_command_end",
                    "call_id": "call_skill_1",
                    "turn_id": "task-1",
                    "exit_code": 0,
                    "parsed_cmd": [
                        {
                            "type": "read",
                            "cmd": "sed -n '1,120p' /home/alexandre/.codex/superpowers/skills/brainstorming/SKILL.md",
                            "name": "SKILL.md",
                            "path": "/home/alexandre/.codex/superpowers/skills/brainstorming/SKILL.md",
                        }
                    ],
                    "aggregated_output": "---\nname: brainstorming\n---\n",
                },
            },
            {
                "timestamp": "2026-04-19T15:13:05.000Z",
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "info": {
                        "total_token_usage": {
                            "input_tokens": 1000,
                            "cached_input_tokens": 700,
                            "output_tokens": 100,
                            "total_tokens": 1100,
                        }
                    },
                },
            },
            {
                "timestamp": "2026-04-19T15:13:06.307Z",
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "name": "exec_command",
                    "arguments": "{\"cmd\":\"sed -n '1,120p' /home/alexandre/.codex/superpowers/skills/writing-plans/SKILL.md\"}",
                    "call_id": "call_skill_2",
                },
            },
            {
                "timestamp": "2026-04-19T15:13:06.400Z",
                "type": "event_msg",
                "payload": {
                    "type": "exec_command_end",
                    "call_id": "call_skill_2",
                    "turn_id": "task-1",
                    "exit_code": 0,
                    "parsed_cmd": [
                        {
                            "type": "read",
                            "cmd": "sed -n '1,120p' /home/alexandre/.codex/superpowers/skills/writing-plans/SKILL.md",
                            "name": "SKILL.md",
                            "path": "/home/alexandre/.codex/superpowers/skills/writing-plans/SKILL.md",
                        }
                    ],
                    "aggregated_output": "---\nname: writing-plans\n---\n",
                },
            },
            {
                "timestamp": "2026-04-19T15:13:10.000Z",
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "info": {
                        "total_token_usage": {
                            "input_tokens": 1800,
                            "cached_input_tokens": 1200,
                            "output_tokens": 180,
                            "total_tokens": 1980,
                        }
                    },
                },
            },
            {
                "timestamp": "2026-04-19T15:13:10.100Z",
                "type": "event_msg",
                "payload": {
                    "type": "task_complete",
                    "turn_id": "task-1",
                    "last_agent_message": "done",
                },
            },
        ]

        events = [event.to_dict() for event in normalize_codex_records(records)]
        summary = compute_metrics(events, resolve_file_stats=False)

        self.assertEqual(summary["skill_attribution"]["brainstorming"]["total_tokens"], 1100)
        self.assertEqual(summary["skill_attribution"]["writing-plans"]["total_tokens"], 880)


if __name__ == "__main__":
    unittest.main()
