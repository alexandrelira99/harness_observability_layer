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

from harness_observability_layer.reporting.session_artifacts import import_codex_session_to_dir


class GuidedReportingTests(unittest.TestCase):
    def test_import_generates_guided_session_site(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            raw_session = tmp_path / "rollout-guided.jsonl"
            raw_session.write_text(
                json.dumps(
                    {
                        "type": "session_meta",
                        "timestamp": "2026-04-19T00:00:00Z",
                        "payload": {
                            "id": "sess_guided",
                            "cwd": str(tmp_path),
                            "source": "codex",
                        },
                    }
                )
                + "\n"
                + json.dumps(
                    {
                        "type": "event_msg",
                        "timestamp": "2026-04-19T00:00:01Z",
                        "payload": {
                            "type": "user_message",
                            "message": "guided site check",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            session_dir = tmp_path / "hol-artifacts" / "sessions" / "rollout-guided"
            result = import_codex_session_to_dir(
                input_path=raw_session,
                output_dir=session_dir,
                project_root=tmp_path,
                resolve_file_stats=False,
            )

            guided_root = (
                tmp_path / "hol-artifacts" / "page" / "sessions" / "rollout-guided"
            )
            self.assertTrue(guided_root.exists())
            self.assertTrue((guided_root / "index.html").exists())
            self.assertTrue((guided_root / "qa-report.html").exists())
            self.assertTrue((guided_root / "cost-efficiency.html").exists())
            self.assertTrue((guided_root / "workflow-trace.html").exists())
            self.assertTrue((guided_root / "raw-metrics.html").exists())
            self.assertIn("guided_site_root", result)

    def test_overview_insights_include_evidence_lines(self) -> None:
        from harness_observability_layer.reporting.guided_insights import (
            build_overview_insights,
        )

        summary = {
            "edited_without_prior_read_count": 4,
            "distinct_files_edited": 5,
            "reread_file_count": 3,
            "failure_rate_pct": 12.5,
            "continuation_loops": 2,
            "max_tokens_stops": 1,
            "total_tokens": 2_250_000,
            "estimated_cost_usd": 3.42,
            "session_duration_seconds": 420,
            "total_cache_read_tokens": 1_500_000,
            "total_input_tokens": 700_000,
            "total_output_tokens": 50_000,
            "tool_failure_rate_by_name": {"exec_command": 22.22},
            "efficiency_indicators": {"reread_ratio": 60.0},
        }

        cards = build_overview_insights(summary)
        self.assertTrue(cards)
        self.assertTrue(all(card["title"] for card in cards))
        self.assertTrue(all(card["evidence"].startswith("Evidence:") for card in cards))

    def test_guided_overview_contains_navigation_to_all_pages(self) -> None:
        from harness_observability_layer.reporting.guided_site import (
            build_guided_session_site,
        )

        output = build_guided_session_site(
            session_name="rollout-guided",
            summary={
                "total_tokens": 10,
                "tool_calls_by_name": {},
                "tool_failures_by_name": {},
                "files": {},
            },
            metadata={
                "display_title": "Guided Session",
                "display_subtitle": "Local only",
                "source_name": "Codex",
            },
            normalized_events_file="normalized.events.jsonl",
            events=[],
        )

        overview_html = output["index.html"]
        workflow_html = output["workflow-trace.html"]
        self.assertIn("workflow-trace.html", overview_html)
        self.assertIn("qa-report.html", workflow_html)
        self.assertIn("cost-efficiency.html", workflow_html)
        self.assertIn("raw-metrics.html", workflow_html)
        self.assertIn("glossary.html", workflow_html)
        self.assertNotIn(">Overview<", workflow_html)
        self.assertIn("Guided Session", workflow_html)
        self.assertIn('data-locale-switcher', workflow_html)
        self.assertIn('data-theme-switcher', workflow_html)
        self.assertIn('data-i18n="nav.workflow"', workflow_html)

    def test_generated_guided_pages_include_raw_metrics_page(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            raw_session = tmp_path / "rollout-pages.jsonl"
            raw_session.write_text(
                json.dumps(
                    {
                        "type": "session_meta",
                        "timestamp": "2026-04-19T00:00:00Z",
                        "payload": {
                            "id": "sess_pages",
                            "cwd": str(tmp_path),
                            "source": "codex",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            session_dir = tmp_path / "hol-artifacts" / "sessions" / "rollout-pages"
            import_codex_session_to_dir(
                raw_session, session_dir, tmp_path, resolve_file_stats=False
            )
            raw_metrics_html = (
                tmp_path
                / "hol-artifacts"
                / "page"
                / "sessions"
                / "rollout-pages"
                / "raw-metrics.html"
            ).read_text(encoding="utf-8")
            self.assertIn("Raw Metrics", raw_metrics_html)
            self.assertIn("summary.json", raw_metrics_html)

    def test_generated_guided_pages_include_glossary_page(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            raw_session = tmp_path / "rollout-glossary.jsonl"
            raw_session.write_text(
                json.dumps(
                    {
                        "type": "session_meta",
                        "timestamp": "2026-04-19T00:00:00Z",
                        "payload": {
                            "id": "sess_glossary",
                            "cwd": str(tmp_path),
                            "source": "codex",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            session_dir = tmp_path / "hol-artifacts" / "sessions" / "rollout-glossary"
            import_codex_session_to_dir(
                raw_session, session_dir, tmp_path, resolve_file_stats=False
            )
            glossary_html = (
                tmp_path
                / "hol-artifacts"
                / "page"
                / "sessions"
                / "rollout-glossary"
                / "glossary.html"
            ).read_text(encoding="utf-8")
            self.assertIn("Glossary", glossary_html)
            self.assertIn("Skill Segment", glossary_html)

    def test_guided_overview_renders_skill_attribution_summary(self) -> None:
        from harness_observability_layer.reporting.guided_site import (
            build_guided_session_site,
        )

        output = build_guided_session_site(
            session_name="rollout-guided",
            summary={
                "total_tokens": 5000,
                "tool_calls_by_name": {},
                "tool_failures_by_name": {},
                "files": {},
                "distinct_skills_loaded": 2,
                "attribution_shares": {
                    "skill_attributed_tool_call_pct": 75.0,
                    "skill_attributed_token_pct": 82.5,
                    "skill_attributed_file_edit_pct": 66.7,
                    "skill_attributed_duration_pct": 80.0,
                },
                "skill_attribution": {
                    "brainstorming": {"tool_call_count": 4, "total_tokens": 3500},
                    "writing-plans": {"tool_call_count": 1, "total_tokens": 625},
                },
                "unattributed_activity": {"total_tokens": 875, "tool_call_count": 2},
            },
            metadata={"display_title": "Guided Session", "display_subtitle": "Local only"},
            normalized_events_file="normalized.events.jsonl",
            events=[],
        )

        html = output["workflow-trace.html"]
        self.assertIn("Skills Loaded", html)
        self.assertIn("Skill-Attributed Tokens", html)
        self.assertIn("Unattributed Tokens", html)
        self.assertIn("brainstorming", html)
        self.assertIn("Workflow Trace", html)

    def test_cost_page_renders_skill_token_breakdown_chart_container(self) -> None:
        from harness_observability_layer.reporting.guided_site import (
            build_guided_session_site,
        )

        output = build_guided_session_site(
            session_name="rollout-guided",
            summary={
                "total_tokens": 5000,
                "tool_calls_by_name": {},
                "tool_failures_by_name": {},
                "files": {},
                "model": "gpt-5.4",
                "plan_type": "plus",
                "skill_attribution": {
                    "brainstorming": {
                        "tool_call_count": 4,
                        "input_tokens": 500,
                        "cache_read_tokens": 2500,
                        "output_tokens": 300,
                        "total_tokens": 3300,
                    }
                },
                "unattributed_activity": {"total_tokens": 1700, "tool_call_count": 2},
                "attribution_shares": {
                    "skill_attributed_token_pct": 66.0,
                    "skill_attributed_tool_call_pct": 66.0,
                    "skill_attributed_file_edit_pct": 0.0,
                    "skill_attributed_duration_pct": 0.0,
                },
            },
            metadata={"display_title": "Guided Session", "display_subtitle": "Local only"},
            normalized_events_file="normalized.events.jsonl",
            events=[],
        )

        html = output["cost-efficiency.html"]
        self.assertIn("skill-token-chart", html)
        self.assertIn("brainstorming", html)
        self.assertIn("Unattributed", html)
        self.assertIn("API Cost", html)
        self.assertIn("Subscription", html)
        self.assertIn("Included in Plus", html)
        self.assertIn("$", html)

    def test_qa_page_removes_redundant_skill_table(self) -> None:
        from harness_observability_layer.reporting.guided_site import (
            build_guided_session_site,
        )

        output = build_guided_session_site(
            session_name="rollout-guided",
            summary={
                "total_tokens": 5000,
                "tool_calls_by_name": {},
                "tool_failures_by_name": {},
                "files": {},
                "skill_attribution": {
                    "brainstorming": {"tool_call_count": 4, "total_tokens": 3500}
                },
                "edited_without_prior_read": [],
            },
            metadata={"display_title": "Guided Session", "display_subtitle": "Local only"},
            normalized_events_file="normalized.events.jsonl",
            events=[],
        )

        html = output["qa-report.html"]
        self.assertNotIn("QA by Skill", html)

    def test_glossary_page_explains_segments_boundaries_and_tool_calls(self) -> None:
        from harness_observability_layer.reporting.guided_site import (
            build_guided_session_site,
        )

        output = build_guided_session_site(
            session_name="rollout-guided",
            summary={
                "total_tokens": 5000,
                "tool_calls_by_name": {
                    "exec_command": 4,
                    "apply_patch": 1,
                    "write_stdin": 2,
                },
                "tool_failures_by_name": {},
                "files": {},
                "attribution_segments": [
                    {
                        "driver_name": "brainstorming",
                        "driver_type": "skill",
                        "tool_call_count": 2,
                        "total_tokens": 1200,
                        "duration_seconds": 12.5,
                        "boundary_reason": "next_skill_loaded",
                    },
                    {
                        "driver_name": "unattributed",
                        "driver_type": "unattributed",
                        "tool_call_count": 1,
                        "total_tokens": 300,
                        "duration_seconds": 5.0,
                        "boundary_reason": "user_message",
                    },
                    {
                        "driver_name": "writing-plans",
                        "driver_type": "skill",
                        "tool_call_count": 1,
                        "total_tokens": 600,
                        "duration_seconds": 8.0,
                        "boundary_reason": "end_of_stream",
                    },
                ],
            },
            metadata={"display_title": "Guided Session", "display_subtitle": "Local only"},
            normalized_events_file="normalized.events.jsonl",
            events=[],
        )

        glossary_html = output["glossary.html"]
        workflow_html = output["workflow-trace.html"]
        self.assertIn("glossary.html", workflow_html)
        self.assertIn("Skill Segment", glossary_html)
        self.assertIn("Boundary Types", glossary_html)
        self.assertIn("Tool Calling Types", glossary_html)
        self.assertIn("next_skill_loaded", glossary_html)
        self.assertIn("user_message", glossary_html)
        self.assertIn("end_of_stream", glossary_html)
        self.assertIn("exec_command", glossary_html)
        self.assertIn("apply_patch", glossary_html)
        self.assertIn("write_stdin", glossary_html)

    def test_guided_pages_include_dashboard_theme_and_i18n_bootstrap(self) -> None:
        from harness_observability_layer.reporting.guided_site import (
            build_guided_session_site,
            report_css,
        )

        output = build_guided_session_site(
            session_name="rollout-guided",
            summary={
                "total_tokens": 5000,
                "tool_calls_by_name": {"exec_command": 4},
                "tool_failures_by_name": {},
                "files": {},
            },
            metadata={"display_title": "Guided Session", "display_subtitle": "Local only"},
            normalized_events_file="normalized.events.jsonl",
            events=[],
        )

        html = output["workflow-trace.html"]
        css = report_css()
        self.assertIn('localStorage.getItem("hol:locale")', html)
        self.assertIn('localStorage.getItem("hol:theme")', html)
        self.assertIn('data-theme="dark"', html)
        self.assertIn('data-locale="eng"', html)
        self.assertIn("ENG", html)
        self.assertIn("PT", html)
        self.assertIn("ES", html)
        self.assertIn("Dark", html)
        self.assertIn("Light", html)
        self.assertIn('"nav.cost":"Cost \\u0026 Efficiency"', html)
        self.assertNotIn('"nav.cost":"Cost &amp; Efficiency"', html)
        self.assertIn("--bg: #0b0f14;", css)
        self.assertIn("[data-theme=\"light\"]", css)


if __name__ == "__main__":
    unittest.main()
