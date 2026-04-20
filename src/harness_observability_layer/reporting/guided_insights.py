"""Deterministic insight derivation for guided session reporting."""

from __future__ import annotations

from typing import Any, Dict, List


_SEVERITY_ORDER = {"high": 0, "medium": 1, "info": 2, "low": 3}


def _card(
    title: str,
    interpretation: str,
    evidence: str,
    *,
    severity: str = "medium",
    recommendation: str = "",
    topic: str = "",
) -> Dict[str, str]:
    return {
        "title": title,
        "interpretation": interpretation,
        "evidence": f"Evidence: {evidence}",
        "severity": severity,
        "recommendation": recommendation,
        "topic": topic or title,
    }


def build_session_insights(summary: Dict[str, Any]) -> List[Dict[str, str]]:
    cards: Dict[str, Dict[str, str]] = {}

    edited_without_read = int(summary.get("edited_without_prior_read_count", 0) or 0)
    distinct_files_edited = int(summary.get("distinct_files_edited", 0) or 0)
    failure_rate = float(summary.get("failure_rate_pct", 0) or 0)
    continuation_loops = int(summary.get("continuation_loops", 0) or 0)
    max_tokens_stops = int(summary.get("max_tokens_stops", 0) or 0)
    cache_tokens = int(summary.get("total_cache_read_tokens", 0) or 0)
    input_tokens = int(summary.get("total_input_tokens", 0) or 0)
    output_tokens = int(summary.get("total_output_tokens", 0) or 0)
    total_tokens = int(summary.get("total_tokens", 0) or 0)
    cost = summary.get("estimated_cost_usd")
    reread_count = int(summary.get("reread_file_count", 0) or 0)
    duration_seconds = float(summary.get("session_duration_seconds", 0) or 0)
    tools_per_min = float(
        (summary.get("efficiency_indicators") or {}).get("tool_calls_per_minute", 0)
        or 0
    )
    tool_failure_rates = summary.get("tool_failure_rate_by_name") or {}
    attribution_shares = summary.get("attribution_shares") or {}
    skill_token_pct = float(
        attribution_shares.get("skill_attributed_token_pct", 0) or 0
    )
    distinct_skills = int(summary.get("distinct_skills_loaded", 0) or 0)
    unattributed_tokens = int(
        (summary.get("unattributed_activity") or {}).get("total_tokens", 0) or 0
    )
    skill_attribution = summary.get("skill_attribution") or {}

    if edited_without_read:
        severity = (
            "high" if edited_without_read > distinct_files_edited / 2 else "medium"
        )
        cards["edit_without_read"] = _card(
            "Edit-Without-Read Risk",
            f"{edited_without_read} of {max(distinct_files_edited, edited_without_read)} edited files had no prior read. "
            "The agent modified files it never inspected, which increases the chance of incorrect assumptions about existing code.",
            f"{edited_without_read} of {max(distinct_files_edited, edited_without_read)} edited files had no prior read",
            severity=severity,
            recommendation="Review the edited files listed below and verify the changes align with the existing codebase structure.",
            topic="edit_without_read",
        )

    if failure_rate >= 10:
        cards["tool_failure"] = _card(
            "High Execution Volatility",
            f"Tool failure rate is {failure_rate:.1f}%, which means the session spent a significant share of effort on retries and error recovery instead of forward progress.",
            f"failure rate {failure_rate:.1f}%",
            severity="high",
            recommendation="Investigate the most fragile tool in the Tool Calling Breakdown below. Reducing retries will lower both cost and time.",
            topic="tool_failure",
        )
    elif failure_rate > 0:
        cards["tool_failure"] = _card(
            "Tool Failure Pressure",
            f"Tool failure rate is {failure_rate:.1f}%. Some tool calls failed, introducing avoidable friction.",
            f"overall failure rate {failure_rate:.1f}%",
            severity="medium",
            recommendation="Check the Tool Calling Breakdown for per-tool failure rates and focus on the highest-rate tool.",
            topic="tool_failure",
        )

    if tool_failure_rates:
        tool_name, tool_rate = sorted(
            tool_failure_rates.items(), key=lambda item: (-item[1], item[0])
        )[0]
        if float(tool_rate) > 0 and "tool_failure" not in cards:
            cards["fragile_tool"] = _card(
                "Most Fragile Tool",
                f"{tool_name} has the highest observed failure rate at {float(tool_rate):.1f}%.",
                f"{tool_name} failure rate {float(tool_rate):.1f}%",
                severity="medium",
                recommendation=f"Review the arguments and permissions for {tool_name} to reduce retry-driven cost.",
                topic="fragile_tool",
            )

    if continuation_loops or max_tokens_stops:
        severity = "high" if continuation_loops >= 2 else "medium"
        cards["context_pressure"] = _card(
            "Context Pressure",
            f"The session hit {continuation_loops} continuation loops and {max_tokens_stops} max-token stops. "
            "This indicates the context window was stretched, which degrades response quality and increases cost.",
            f"{continuation_loops} continuation loops, {max_tokens_stops} max-token stops",
            severity=severity,
            recommendation="Use /clear before task shifts. Split long exploratory sessions into focused shorter ones.",
            topic="context_pressure",
        )

    if cache_tokens > input_tokens and cache_tokens > 0:
        cards["cache_dominance"] = _card(
            "Cache-Dominant Token Profile",
            f"Cache-read tokens ({cache_tokens:,}) exceed fresh input tokens ({input_tokens:,}). "
            "Most token volume is context replay rather than new information.",
            f"{cache_tokens:,} cache tokens vs {input_tokens:,} fresh input tokens",
            severity="medium",
            recommendation="Consider resetting context when the task changes to reduce stale context replay cost.",
            topic="cache_dominance",
        )

    if total_tokens >= 1_000_000:
        cards["long_session"] = _card(
            "Long-Running Session",
            f"This session accumulated {total_tokens:,} tokens, which is a substantial context footprint.",
            f"{total_tokens:,} cumulative tokens",
            severity="info",
            recommendation="Large sessions benefit from periodic context resets to maintain response quality.",
            topic="long_session",
        )

    if reread_count:
        cards["rework"] = _card(
            "Rework Signals",
            f"{reread_count} files were re-read, which may indicate uncertainty or iterative debugging.",
            f"{reread_count} files were re-read",
            severity="info",
            recommendation="If re-reads cluster around specific files, those files may need better initial documentation or more focused queries.",
            topic="rework",
        )

    if duration_seconds > 0 and tools_per_min > 0:
        edits_per_min = float(
            (summary.get("efficiency_indicators") or {}).get("edits_per_minute", 0) or 0
        )
        cards["throughput"] = _card(
            "Throughput Snapshot",
            f"The session ran for {duration_seconds:.0f}s with {tools_per_min:.1f} tool calls/min and {edits_per_min:.1f} edits/min.",
            f"{tools_per_min:.1f} tools/min, {edits_per_min:.1f} edits/min over {duration_seconds:.0f}s",
            severity="info",
            recommendation="Compare against project average to identify sessions that are disproportionately slow or fast.",
            topic="throughput",
        )

    if skill_token_pct >= 70:
        cards["skill_attribution"] = _card(
            "Skill-Driven Session",
            f"{skill_token_pct:.1f}% of token volume was attributable to loaded skills. The session was primarily skill-guided.",
            f"{skill_token_pct:.1f}% of tokens attributed to skills",
            severity="info",
            recommendation="High skill attribution is usually efficient. Verify the skills used are still the best fit for the task.",
            topic="skill_attribution",
        )
    elif distinct_skills and unattributed_tokens > 0:
        cards["skill_attribution"] = _card(
            "Mixed Guidance Footprint",
            f"The session combined skill-led work with {unattributed_tokens:,} unattributed tokens. Some activity occurred outside any skill window.",
            f"{unattributed_tokens:,} unattributed tokens alongside {distinct_skills} loaded skills",
            severity="info",
            recommendation="Unattributed activity is not necessarily bad, but it may indicate skill coverage gaps.",
            topic="skill_attribution",
        )

    if skill_attribution:
        top_skill, top_stats = sorted(
            skill_attribution.items(),
            key=lambda item: (-(item[1].get("total_tokens", 0) or 0), item[0]),
        )[0]
        top_tokens = int(top_stats.get("total_tokens", 0) or 0)
        total_skill_tokens = sum(
            int(bucket.get("total_tokens", 0) or 0)
            for bucket in skill_attribution.values()
        )
        if (
            top_tokens
            and total_skill_tokens
            and (top_tokens / total_skill_tokens) >= 0.7
        ):
            cards["skill_dominance"] = _card(
                "Single Skill Dominance",
                f"{top_skill} accounted for {top_tokens:,} of {total_skill_tokens:,} attributed tokens.",
                f"{top_skill} contributed {top_tokens:,} of {total_skill_tokens:,} attributed tokens",
                severity="info",
                recommendation=f"Consider whether {top_skill} should be decomposed into smaller, more focused skills.",
                topic="skill_dominance",
            )
        elif len(skill_attribution) > 1:
            cards["skill_dominance"] = _card(
                "Multi-Skill Session",
                f"Activity was distributed across {len(skill_attribution)} skills.",
                f"{len(skill_attribution)} skills carried attributed activity",
                severity="info",
                recommendation="Multi-skill sessions are healthy when tasks are well-scoped.",
                topic="skill_dominance",
            )

    ordered = sorted(
        cards.values(),
        key=lambda c: (
            _SEVERITY_ORDER.get(c.get("severity", "medium"), 2),
            c.get("topic", ""),
        ),
    )
    return ordered[:10]


def build_session_executive_summary(summary: Dict[str, Any]) -> str:
    parts: List[str] = []
    total_tokens = int(summary.get("total_tokens", 0) or 0)
    cost = summary.get("estimated_cost_usd")
    tool_calls = int(summary.get("total_tool_calls", 0) or 0)
    duration = float(summary.get("session_duration_seconds", 0) or 0)
    model = str(summary.get("model") or "unknown")
    failure_rate = float(summary.get("failure_rate_pct", 0) or 0)
    edited_without_read = int(summary.get("edited_without_prior_read_count", 0) or 0)
    distinct_files_edited = int(summary.get("distinct_files_edited", 0) or 0)
    continuation_loops = int(summary.get("continuation_loops", 0) or 0)

    scope = f"This {model} session used {total_tokens:,} tokens across {tool_calls} tool calls"
    if cost is not None:
        scope += f" for an estimated ${float(cost):.2f}"
    scope += "."
    parts.append(scope)

    concerns: List[str] = []
    if failure_rate >= 10:
        concerns.append(f"a {failure_rate:.0f}% tool failure rate")
    if edited_without_read and distinct_files_edited:
        concerns.append(f"{edited_without_read} files edited without prior read")
    if continuation_loops:
        concerns.append(f"{continuation_loops} context continuation loops")

    if concerns:
        parts.append("Primary concerns: " + ", ".join(concerns) + ".")
    elif duration > 0 and tool_calls > 0:
        parts.append("No significant issues detected.")

    return " ".join(parts)


def build_project_executive_summary(aggregate: Dict[str, Any]) -> str:
    totals = aggregate.get("totals") or {}
    sessions = int(totals.get("sessions", 0) or 0)
    if sessions == 0:
        return "No sessions imported yet."

    total_cost = float(totals.get("estimated_cost_usd", 0) or 0)
    total_tokens = int(totals.get("total_tokens", 0) or 0)
    session_rankings = aggregate.get("session_rankings") or []

    parts: List[str] = []
    parts.append(
        f"This project has {sessions} session(s) totaling ${total_cost:.2f} "
        f"and {total_tokens:,} tokens."
    )

    high_attention = [
        s for s in session_rankings if float(s.get("attention_score", 0) or 0) > 0.5
    ]
    if high_attention:
        top = high_attention[0]
        title = top.get("display_title") or top.get("session_name", "a session")
        parts.append(
            f'The top session requiring attention is "{title}" '
            f"(cost ${float(top.get('estimated_cost_usd', 0) or 0):.2f}, "
            f"{float(top.get('failure_rate_pct', 0) or 0):.0f}% failure rate)."
        )

    return " ".join(parts)


def build_overview_insights(summary: Dict[str, Any]) -> List[Dict[str, str]]:
    return [
        c
        for c in build_session_insights(summary)
        if c.get("topic")
        in {
            "edit_without_read",
            "tool_failure",
            "context_pressure",
            "cache_dominance",
            "long_session",
            "skill_attribution",
            "skill_dominance",
        }
    ][:5]


def _project_card(
    title: str,
    interpretation: str,
    evidence: str,
    recommendation: str,
    *,
    severity: str = "medium",
) -> Dict[str, str]:
    return {
        "title": title,
        "interpretation": interpretation,
        "evidence": f"Evidence: {evidence}",
        "recommendation": recommendation,
        "severity": severity,
    }


def build_project_overview_insights(aggregate: Dict[str, Any]) -> List[Dict[str, str]]:
    cards: List[Dict[str, str]] = []
    totals = aggregate.get("totals") or {}
    top_turns = aggregate.get("top_turns") or []
    top_prompt_groups = aggregate.get("top_prompt_groups") or []
    session_rankings = aggregate.get("session_rankings") or []
    sessions = aggregate.get("sessions") or []

    if totals.get("sessions", 0):
        avg_cost = float(totals.get("estimated_cost_usd", 0) or 0) / max(
            int(totals.get("sessions", 0) or 0), 1
        )
        cards.append(
            _project_card(
                "Single Project Control Plane",
                "The project now has enough imported session data to prioritize investigation from one aggregate view.",
                f"{int(totals.get('sessions', 0) or 0)} sessions, {int(totals.get('prompt_groups', 0) or 0)} prompt groups, average session cost ${avg_cost:.2f}",
                "Use the project dashboard as the default entrypoint and only drill into sessions after a ranked prompt or turn stands out.",
                severity="info",
            )
        )

    if top_turns:
        top_cost = float(top_turns[0].get("estimated_cost_usd", 0) or 0)
        median_index = min(len(top_turns) - 1, max(0, len(top_turns) // 2))
        median_cost = float(top_turns[median_index].get("estimated_cost_usd", 0) or 0)
        if top_cost > 0 and median_cost > 0 and top_cost >= median_cost * 3:
            cards.append(
                _project_card(
                    "Strong /clear Opportunity",
                    "One turn is dramatically more expensive than a typical expensive turn, which usually signals context buildup rather than intrinsically harder work.",
                    f"top ranked turn cost ${top_cost:.2f} versus comparison turn ${median_cost:.2f}",
                    "Recommend `/clear` before task shifts or before the spike-prone segment, then continue in a fresh context window.",
                    severity="high",
                )
            )

    long_context_sessions = [
        item
        for item in session_rankings
        if float(item.get("continuation_loops", 0) or 0) > 0
        or float(item.get("max_tokens_stops", 0) or 0) > 0
    ]
    if long_context_sessions:
        cards.append(
            _project_card(
                "Long Context Pressure",
                "Several sessions show continuation or max-token behavior, which usually means the work is stretching past a healthy context size.",
                f"{len(long_context_sessions)} sessions with continuation loops or max-token stops",
                "Split exploratory work into smaller sessions and reset context sooner when the task changes or the agent starts slowing down.",
                severity="high",
            )
        )

    high_failure_sessions = [
        item
        for item in session_rankings
        if float(item.get("failure_rate_pct", 0) or 0) >= 10
    ]
    if high_failure_sessions:
        cards.append(
            _project_card(
                "Operational Friction Concentration",
                "Some high-cost sessions are also spending effort on avoidable failures instead of forward progress.",
                f"{len(high_failure_sessions)} sessions have failure rate at or above 10%",
                "Triage the fragile tool paths first because reducing retries lowers both spend and attention drag.",
                severity="medium",
            )
        )

    repeated_heavy_startup = 0
    for session in sessions:
        prompt_groups = session.get("prompt_groups") or []
        if not prompt_groups:
            continue
        first_group = prompt_groups[0]
        if (
            int(first_group.get("tool_call_count", 0) or 0) == 0
            and int(first_group.get("input_tokens", 0) or 0) >= 1000
        ):
            repeated_heavy_startup += 1
    if repeated_heavy_startup >= 2:
        cards.append(
            _project_card(
                "Repeated Startup Overhead",
                "Multiple sessions are paying a large first-prompt cost before meaningful tool activity begins.",
                f"{repeated_heavy_startup} sessions start with high-input prompt groups and no tool work",
                "Trim repeated bootstrap context, move reusable setup into shorter instructions, and avoid re-sending large repo preambles when not needed.",
                severity="medium",
            )
        )

    return cards[:6]


def build_project_cost_insights(aggregate: Dict[str, Any]) -> List[Dict[str, str]]:
    cards: List[Dict[str, str]] = []
    totals = aggregate.get("totals") or {}
    model_breakdown = aggregate.get("model_breakdown") or []
    top_prompt_groups = aggregate.get("top_prompt_groups") or []

    total_tokens = int(totals.get("total_tokens", 0) or 0)
    total_cost = float(totals.get("estimated_cost_usd", 0) or 0)
    cache_read = int(totals.get("total_cache_read_tokens", 0) or 0)
    if total_tokens > 0:
        cache_share = (cache_read / total_tokens) * 100
        if cache_share >= 40:
            cards.append(
                _project_card(
                    "Cache-Heavy Cost Profile",
                    "A large slice of token volume is context replay, which is often a symptom of long-running conversations.",
                    f"{cache_read:,} cache-read tokens out of {total_tokens:,} total tokens ({cache_share:.1f}%)",
                    "Review the sessions with the largest late-turn costs and reset context more aggressively when a task boundary appears.",
                    severity="medium",
                )
            )
    if total_cost >= 1 and top_prompt_groups:
        top_prompt = top_prompt_groups[0]
        cards.append(
            _project_card(
                "Prompt Spend Is Concentrated",
                "A small number of prompt groups are likely driving a disproportionate share of project cost.",
                f"top prompt group '{top_prompt.get('prompt_excerpt') or '(no prompt)'}' costs about ${float(top_prompt.get('estimated_cost_usd', 0) or 0):.2f}",
                "Start optimization with the top prompt groups because they give the fastest path to lower project spend.",
                severity="medium",
            )
        )
    if len(model_breakdown) >= 2:
        priciest = model_breakdown[0]
        cheapest = model_breakdown[-1]
        if float(priciest.get("cost", 0) or 0) > float(
            cheapest.get("cost", 0) or 0
        ) and int(priciest.get("tool_calls", 0) or 0) <= int(
            cheapest.get("tool_calls", 0) or 0
        ):
            cards.append(
                _project_card(
                    "Model Choice Review",
                    "The most expensive model is not obviously buying more operational throughput than cheaper alternatives.",
                    f"{priciest.get('model')} cost ${float(priciest.get('cost', 0) or 0):.2f} across {int(priciest.get('tool_calls', 0) or 0)} tool calls",
                    "Shift default exploratory or operational work to the cheaper model and reserve the premium model for the sessions that really need deep reasoning.",
                    severity="high",
                )
            )
    return cards[:4]


def build_project_prompt_insights(aggregate: Dict[str, Any]) -> List[Dict[str, str]]:
    cards: List[Dict[str, str]] = []
    top_prompt_groups = aggregate.get("top_prompt_groups") or []
    if not top_prompt_groups:
        return cards

    prompt_hash_counts: Dict[str, int] = {}
    for item in top_prompt_groups:
        prompt_hash = str(item.get("prompt_hash") or "")
        if prompt_hash:
            prompt_hash_counts[prompt_hash] = prompt_hash_counts.get(prompt_hash, 0) + 1
    repeated_prompt = next(
        (
            item
            for item in top_prompt_groups
            if prompt_hash_counts.get(str(item.get("prompt_hash") or ""), 0) >= 2
        ),
        None,
    )
    if repeated_prompt:
        cards.append(
            _project_card(
                "Repeated Expensive Prompt Pattern",
                "The same prompt shape appears multiple times among the highest-cost prompt groups, which suggests repeated overhead rather than one isolated outlier.",
                f"prompt hash {repeated_prompt.get('prompt_hash')} repeats in the expensive prompt ranking",
                "Consolidate or shorten that repeated setup prompt so future sessions do not keep paying the same initialization cost.",
                severity="medium",
            )
        )
    long_prompt_groups = [
        item
        for item in top_prompt_groups
        if int(item.get("total_tokens", 0) or 0) >= 5000
        and int(item.get("tool_call_count", 0) or 0) <= 1
    ]
    if long_prompt_groups:
        cards.append(
            _project_card(
                "High-Context Low-Action Prompt Group",
                "Some expensive prompt groups are spending a lot of tokens without much tool activity, which often means context packaging is too heavy.",
                f"{len(long_prompt_groups)} top prompt groups have high token volume with at most one tool call",
                "Reduce prompt boilerplate and move non-essential context out of the hot path so the model starts doing useful work earlier.",
                severity="medium",
            )
        )
    return cards[:4]


def build_qa_insights(summary: Dict[str, Any]) -> List[Dict[str, str]]:
    return [
        c
        for c in build_session_insights(summary)
        if c.get("topic")
        in {
            "edit_without_read",
            "tool_failure",
            "context_pressure",
            "rework",
            "fragile_tool",
        }
    ][:5]


def build_cost_efficiency_insights(summary: Dict[str, Any]) -> List[Dict[str, str]]:
    return [
        c
        for c in build_session_insights(summary)
        if c.get("topic")
        in {
            "cache_dominance",
            "throughput",
            "skill_attribution",
            "long_session",
        }
    ][:5]


def build_cost_efficiency_insights(summary: Dict[str, Any]) -> List[Dict[str, str]]:
    cards: List[Dict[str, str]] = []
    total_tokens = int(summary.get("total_tokens", 0) or 0)
    cache_tokens = int(summary.get("total_cache_read_tokens", 0) or 0)
    output_tokens = int(summary.get("total_output_tokens", 0) or 0)
    cost = summary.get("estimated_cost_usd")
    duration_seconds = float(summary.get("session_duration_seconds", 0) or 0)
    tools_per_min = float(
        (summary.get("efficiency_indicators") or {}).get("tool_calls_per_minute", 0)
        or 0
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
    skill_token_pct = float(
        attribution_shares.get("skill_attributed_token_pct", 0) or 0
    )
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
