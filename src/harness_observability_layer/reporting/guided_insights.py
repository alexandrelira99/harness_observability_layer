"""Deterministic insight derivation for guided session reporting."""

from __future__ import annotations

from typing import Any, Dict, List


def _card(title: str, interpretation: str, evidence: str) -> Dict[str, str]:
    return {
        "title": title,
        "interpretation": interpretation,
        "evidence": f"Evidence: {evidence}",
    }


def build_overview_insights(summary: Dict[str, Any]) -> List[Dict[str, str]]:
    cards: List[Dict[str, str]] = []
    edited_without_read = int(summary.get("edited_without_prior_read_count", 0) or 0)
    distinct_files_edited = int(summary.get("distinct_files_edited", 0) or 0)
    failure_rate = float(summary.get("failure_rate_pct", 0) or 0)
    continuation_loops = int(summary.get("continuation_loops", 0) or 0)
    cache_tokens = int(summary.get("total_cache_read_tokens", 0) or 0)
    input_tokens = int(summary.get("total_input_tokens", 0) or 0)
    total_tokens = int(summary.get("total_tokens", 0) or 0)

    if edited_without_read:
        cards.append(
            _card(
                "Low Edit Discipline",
                "The session edited files without consistently reading them first.",
                f"{edited_without_read} of {max(distinct_files_edited, edited_without_read)} edited files had no prior read",
            )
        )
    if failure_rate >= 10:
        cards.append(
            _card(
                "High Execution Volatility",
                "The session showed unstable tool execution and deserves review.",
                f"failure rate {failure_rate:.1f}%",
            )
        )
    if continuation_loops:
        cards.append(
            _card(
                "Continuation-Heavy Run",
                "The session hit repeated continuation patterns that may indicate drift or excessive context pressure.",
                f"{continuation_loops} continuation loops detected",
            )
        )
    if cache_tokens > input_tokens and cache_tokens > 0:
        cards.append(
            _card(
                "Cache-Dominant Token Profile",
                "Most token volume came from cached context reuse rather than fresh input.",
                f"{cache_tokens:,} cache tokens vs {input_tokens:,} fresh input tokens",
            )
        )
    if total_tokens >= 1_000_000:
        cards.append(
            _card(
                "Long-Running Session",
                "The session accumulated substantial context and activity over time.",
                f"{total_tokens:,} cumulative tokens",
            )
        )
    attribution_shares = summary.get("attribution_shares", {}) or {}
    skill_token_pct = float(attribution_shares.get("skill_attributed_token_pct", 0) or 0)
    distinct_skills = int(summary.get("distinct_skills_loaded", 0) or 0)
    unattributed_tokens = int(
        (summary.get("unattributed_activity") or {}).get("total_tokens", 0) or 0
    )
    skill_attribution = summary.get("skill_attribution", {}) or {}
    if skill_token_pct >= 70:
        cards.append(
            _card(
                "Skill-Driven Session",
                "Most of the session's token volume was attributable to loaded skills.",
                f"{skill_token_pct:.1f}% of tokens attributed to skills",
            )
        )
    elif distinct_skills and unattributed_tokens > 0:
        cards.append(
            _card(
                "Mixed Guidance Footprint",
                "The session combined skill-led work with a meaningful amount of unattributed agent activity.",
                f"{unattributed_tokens:,} unattributed tokens alongside {distinct_skills} loaded skills",
            )
        )
    if skill_attribution:
        top_skill, top_stats = sorted(
            skill_attribution.items(),
            key=lambda item: (
                -(item[1].get("total_tokens", 0) or 0),
                item[0],
            ),
        )[0]
        top_tokens = int(top_stats.get("total_tokens", 0) or 0)
        total_skill_tokens = sum(
            int(bucket.get("total_tokens", 0) or 0)
            for bucket in skill_attribution.values()
        )
        if top_tokens and total_skill_tokens and (top_tokens / total_skill_tokens) >= 0.7:
            cards.append(
                _card(
                    "Single Skill Dominance",
                    "One skill accounted for most of the attributed session activity.",
                    f"{top_skill} contributed {top_tokens:,} of {total_skill_tokens:,} attributed tokens",
                )
            )
        elif len(skill_attribution) > 1:
            cards.append(
                _card(
                    "Multi-Skill Session",
                    "Session activity was distributed across more than one skill window.",
                    f"{len(skill_attribution)} skills carried attributed activity",
                )
            )
    return cards[:5]


def build_qa_insights(summary: Dict[str, Any]) -> List[Dict[str, str]]:
    cards: List[Dict[str, str]] = []
    edited_without_read = int(summary.get("edited_without_prior_read_count", 0) or 0)
    reread_count = int(summary.get("reread_file_count", 0) or 0)
    failure_rate = float(summary.get("failure_rate_pct", 0) or 0)
    continuation_loops = int(summary.get("continuation_loops", 0) or 0)
    max_tokens_stops = int(summary.get("max_tokens_stops", 0) or 0)
    tool_failure_rates = summary.get("tool_failure_rate_by_name", {}) or {}

    if edited_without_read:
        cards.append(
            _card(
                "Edit-Without-Read Risk",
                "Several files were modified without an observed prior read event.",
                f"{edited_without_read} files edited without prior read",
            )
        )
    if reread_count:
        cards.append(
            _card(
                "Rework Signals",
                "The session revisited files repeatedly, which may indicate uncertainty or iterative debugging.",
                f"{reread_count} files were re-read",
            )
        )
    if failure_rate > 0:
        cards.append(
            _card(
                "Tool Failure Pressure",
                "Tool failures introduced avoidable execution friction.",
                f"overall failure rate {failure_rate:.1f}%",
            )
        )
    if continuation_loops or max_tokens_stops:
        cards.append(
            _card(
                "Context Pressure",
                "The session encountered continuation behavior associated with long-running context.",
                f"{continuation_loops} continuation loops, {max_tokens_stops} max-token stops",
            )
        )
    if tool_failure_rates:
        tool_name, tool_rate = sorted(
            tool_failure_rates.items(), key=lambda item: (-item[1], item[0])
        )[0]
        if float(tool_rate) > 0:
            cards.append(
                _card(
                    "Most Fragile Tool",
                    "One tool accounted for the highest observed failure pressure in the session.",
                    f"{tool_name} failure rate {float(tool_rate):.1f}%",
                )
            )
    return cards[:5]


def build_cost_efficiency_insights(summary: Dict[str, Any]) -> List[Dict[str, str]]:
    cards: List[Dict[str, str]] = []
    total_tokens = int(summary.get("total_tokens", 0) or 0)
    cache_tokens = int(summary.get("total_cache_read_tokens", 0) or 0)
    output_tokens = int(summary.get("total_output_tokens", 0) or 0)
    cost = summary.get("estimated_cost_usd")
    duration_seconds = float(summary.get("session_duration_seconds", 0) or 0)
    tools_per_min = float(
        (summary.get("efficiency_indicators") or {}).get("tool_calls_per_minute", 0) or 0
    )
    edits_per_min = float(
        (summary.get("efficiency_indicators") or {}).get("edits_per_minute", 0) or 0
    )

    if total_tokens:
        cards.append(
            _card(
                "Cumulative Token Footprint",
                "This report reflects cumulative session usage rather than a single context window.",
                f"{total_tokens:,} total tokens, including cache reuse",
            )
        )
    if cache_tokens:
        cards.append(
            _card(
                "High Context Reuse",
                "A large share of token volume came from cached context reads.",
                f"{cache_tokens:,} cache tokens and {output_tokens:,} output tokens",
            )
        )
    if cost is not None:
        cards.append(
            _card(
                "Estimated API-Equivalent Cost",
                "The session has a measurable compute profile even when run in an interactive coding workflow.",
                f"estimated cost ${float(cost):.2f}",
            )
        )
    if duration_seconds > 0:
        cards.append(
            _card(
                "Throughput Snapshot",
                "The session can be interpreted through both elapsed time and operational density.",
                f"{tools_per_min:.1f} tools/min, {edits_per_min:.1f} edits/min over {duration_seconds:.0f}s",
            )
        )
    attribution_shares = summary.get("attribution_shares", {}) or {}
    skill_token_pct = float(attribution_shares.get("skill_attributed_token_pct", 0) or 0)
    unattributed_tokens = int(
        (summary.get("unattributed_activity") or {}).get("total_tokens", 0) or 0
    )
    if skill_token_pct >= 70:
        cards.append(
            _card(
                "Skill-Led Token Spend",
                "Most token volume accumulated while a skill attribution window was active.",
                f"{skill_token_pct:.1f}% of tokens were skill-attributed",
            )
        )
    elif unattributed_tokens > 0:
        cards.append(
            _card(
                "Unattributed Token Share",
                "A noticeable slice of token volume occurred outside any active skill window.",
                f"{unattributed_tokens:,} unattributed tokens",
            )
        )
    return cards[:5]
