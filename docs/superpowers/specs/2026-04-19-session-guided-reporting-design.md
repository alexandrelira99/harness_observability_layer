# Session-Guided Reporting Design

Date: 2026-04-19
Project: harness-observability-layer
Status: Draft for user review

## Goal

Evolve the current static HTML reporting experience from a metric-centric session report into a guided, use-case-oriented static site per session, while preserving the existing project-scoped session import behavior and auditability of raw metrics.

The new reporting UX should:

- Keep imports scoped to sessions belonging to the current project.
- Keep the project-level `index.html` as a hub for choosing one session from the project.
- Generate a detailed, session-specific static site with guided views that interpret the session through predefined use cases.
- Preserve access to raw metrics and technical artifacts so the interpreted views remain inspectable and trustworthy.

## Product Direction

The reporting product will move to a two-layer model:

- Guided interpretation as the primary experience.
- Raw metrics and technical artifacts as the supporting evidence layer.

This keeps the tool commercially legible without turning it into a black box. The report should first answer what happened and why it matters, then show the metrics that support that interpretation.

## Scope

This design covers the first version of the guided reporting experience for a single session at a time.

In scope:

- Project-level session hub remains in place.
- Session-level static reporting site with five guided pages.
- Deterministic insights derived from existing metrics and metadata.
- Reuse of existing generated artifacts such as `summary.json`, `metadata.json`, and `normalized.events.jsonl`.

Out of scope for this version:

- Automatic comparison between sessions.
- Automatic comparison between setups, models, or skill/plugin combinations.
- LLM-generated prose or AI-written analysis.
- A JavaScript-heavy application shell.
- Changing the current import filtering logic by project.

## Information Architecture

### Project Hub

The project-scoped session hub remains the main entry point at the existing sessions index location. Its responsibilities remain:

- List imported sessions for the current project.
- Provide high-level summary metadata per session.
- Route the user into one chosen session.

The hub should continue to reflect project scope only and should not mix session-level interpretations together.

### Session Site

Each session receives a detailed static site, generated under a dedicated page-oriented output structure.

Recommended structure:

```text
hol-artifacts/
  sessions/
    index.html
    <session-id>/
      raw.codex.jsonl
      normalized.events.jsonl
      summary.json
      metadata.json
      report.html
      report.css
  page/
    sessions/
      <session-id>/
        index.html
        qa-report.html
        cost-efficiency.html
        workflow-trace.html
        raw-metrics.html
        report.css
```

The existing `hol-artifacts/sessions/<session-id>/...` directory remains the technical artifact store. The new `hol-artifacts/page/sessions/<session-id>/...` directory becomes the guided presentation layer.

## Guided Pages

The first version will ship five pages per session.

### 1. Overview

Purpose:

- Provide the executive summary of the session.
- Surface the top 3-5 insights automatically.
- Present key summary numbers and quick warnings.

Content:

- Session title, subtitle, source and runtime badges.
- Core metrics summary cards.
- Insight cards with short titles, one-sentence rationale, and evidence.
- Links to the four deeper guided pages.
- Links to technical artifacts.

### 2. QA Report

Purpose:

- Interpret operational quality and execution discipline.

Focus areas:

- Editing without prior read.
- Re-read and rework patterns.
- Tool failure concentration.
- Continuation loops and max-token stops.
- File-level read/edit behavior.

Content:

- Quality posture summary.
- Risk cards with evidence lines.
- Supporting tables or lists for operational gaps.

### 3. Cost & Efficiency

Purpose:

- Interpret cost, token profile, duration, throughput, and operational efficiency.

Focus areas:

- Fresh input versus cache reuse versus output.
- Session cumulative tokens.
- Estimated API-equivalent cost.
- Session duration and throughput.
- Calls per turn and activity density.

Content:

- Token profile summary.
- Cost and efficiency insight cards.
- Efficiency summary blocks.
- Supporting numeric tables where useful.

### 4. Workflow Trace

Purpose:

- Show the behavior of the session as an operational trace.

Focus areas:

- Event timeline.
- Tool activity.
- File heatmap.
- Top files.
- Bash activity distribution.

Content:

- Timeline section.
- Tool activity grid.
- File interaction panels.
- Operational trace sections that expose sequence and concentration of work.

### 5. Raw Metrics

Purpose:

- Preserve auditability and trust.

Content:

- `summary.json` rendered in-page.
- Raw derived metrics tables.
- Possibly direct links to normalized event logs and raw imported logs.

This page is the evidence floor for the guided pages.

## Shared Session Shell

All five pages should share a common presentation shell:

- Hero section with title, subtitle, and badges.
- Consistent navigation between the five session pages.
- Compact "key signals" row near the top.
- Body section specific to the page's use case.
- Discreet technical artifact links.

The shell should remain fully static and work without JavaScript.

## Insight System

The first version of insights should be deterministic and template-driven.

Each insight must include:

- A short title.
- A concise interpretation sentence.
- A short evidence line with concrete metrics.

Example structure:

- Title: `High Rework Risk`
- Interpretation: `The session revisited files frequently and edited multiple files without prior read.`
- Evidence: `Evidence: 24 files edited without read, reread ratio 31.1%, 8 tool failures.`

### Insight Design Principles

- Use existing metrics only.
- Avoid vague adjectives without evidence.
- Avoid pretending confidence when data is weak.
- Prefer explicit labels such as "cache-dominant token profile" over generic "good" or "bad".

## Heuristic Inputs by Page

### Overview

Potential heuristic inputs:

- `failure_rate_pct`
- `edited_without_prior_read_count`
- `reread_file_count`
- `continuation_loops`
- `max_tokens_stops`
- `total_tokens`
- `estimated_cost_usd`
- `session_duration_seconds`

Outputs:

- 3-5 headline insights.
- Session posture summary.

### QA Report

Potential heuristic inputs:

- `edited_without_prior_read_count`
- `edited_without_prior_read`
- `read_without_edit_count`
- `reread_ratio`
- `failure_rate_pct`
- `tool_failure_rate_by_name`
- `continuation_loops`
- `max_tokens_stops`
- `file_read_to_edit_ratio`

Outputs:

- Execution quality assessment.
- Risk-oriented insight cards.
- Evidence-based gap summaries.

### Cost & Efficiency

Potential heuristic inputs:

- `total_tokens`
- `total_input_tokens`
- `total_cache_read_tokens`
- `total_output_tokens`
- `estimated_cost_usd`
- `cache_hit_rate_pct`
- `session_duration_seconds`
- `tool_calls_per_turn`
- `tool_calls_per_minute`
- `edits_per_minute`

Outputs:

- Token/cost profile interpretation.
- Throughput posture.
- Efficiency-oriented insight cards.

### Workflow Trace

Potential heuristic inputs:

- `tool_calls_by_name`
- `tool_failures_by_name`
- `files`
- `bash_command_categories`
- normalized event ordering

Outputs:

- Operational trace presentation.
- Work concentration views.

### Raw Metrics

Potential heuristic inputs:

- Entire `summary.json`
- session metadata
- normalized event file references

Outputs:

- Structured evidence display with minimal interpretation.

## Routing and Linking

The project hub should link to the session guided site overview page:

- `hol-artifacts/page/sessions/<session-id>/index.html`

Within each session site, navigation should link directly between the five pages using relative links.

Technical artifact links should also be exposed, linking back to:

- `summary.json`
- `metadata.json`
- `normalized.events.jsonl`
- existing legacy `report.html` when retained

## Backward Compatibility

The existing session artifact generation should remain intact during the first rollout.

That means:

- Existing raw and normalized files remain unchanged.
- Existing `report.html` may remain as a legacy or technical report.
- Existing project import behavior remains unchanged.

The new guided reporting layer should be additive, not destructive.

## Technical Design

Recommended implementation structure:

- Keep generation orchestration in `session_artifacts.py`.
- Add a new page-site generator module in `reporting/`.
- Add a dedicated insight derivation module separate from HTML rendering.
- Reuse metadata and summary loaders already available.

Suggested module responsibilities:

- `session_artifacts.py`
  Orchestrates generation of both technical artifacts and guided page site.

- `session_index.py`
  Continues building the project hub and updates links to point at the new per-session overview page.

- new guided site renderer module
  Builds the session page tree and shared shell.

- new insight derivation module
  Produces deterministic insight cards for each page.

## Visual and UX Direction

The new static site should feel more like a report product than a raw dashboard.

Desired UX qualities:

- Fast to scan.
- Interpretation-first.
- Still evidence-backed.
- Professional and shareable.
- Static and portable.

The visual system should stay consistent with the current no-build static HTML approach, but the layout should support clearer page identity and use-case framing.

## Testing Strategy

The implementation should introduce tests that cover:

- Generation of the new session page tree.
- Session hub links targeting the guided overview page.
- Presence of the five guided pages for a generated session.
- Deterministic insight rendering for representative summaries.
- Safe escaping of user-derived and file-derived content in the new pages.

Where practical, tests should validate both structure and representative content rather than pixel-level layout details.

## Rollout Strategy

Phase 1:

- Generate the new guided page tree alongside current artifacts.
- Keep legacy report output intact.
- Switch project hub links to the new guided overview page.

Phase 2, future:

- Refine heuristics.
- Add session comparison workflows if desired.
- Consider optional richer navigation once the single-session experience is validated.

## Open Decisions Resolved in This Design

The following decisions are considered resolved for the implementation plan:

- Reporting remains project-scoped at import time.
- The project index remains a session-selection hub.
- Guided reporting is session-specific only.
- The first release ships five pages per session.
- The new guided site is static and file-based.
- Raw metrics remain accessible and are not removed.

## Success Criteria

This work is successful when:

- A user can open the project hub and choose a session.
- That session opens into a guided static report site.
- The guided site includes `Overview`, `QA Report`, `Cost & Efficiency`, `Workflow Trace`, and `Raw Metrics`.
- The guided pages interpret existing metrics with deterministic heuristics.
- The user can still reach the raw artifacts and technical evidence backing those interpretations.
