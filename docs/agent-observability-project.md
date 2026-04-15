# Agent Observability Project

This document is the initial truth source for an observability project focused on Claude Code / Codex style harnesses.

## Goal

Measure what an agent actually does during a task, using observable signals from the harness and tools, instead of trying to infer inaccessible internal attention directly.

The project should help answer questions such as:

- How many tool calls were made per task or session?
- Which tools were used most?
- Which files were consulted, how often, and in which ranges?
- How much of a file was read before it was edited?
- Which skills or plugins were loaded but had no measurable downstream effect?
- Which skills appear too dense relative to their practical usage?

## Non-goals

- Infer the model's exact internal attention distribution.
- Claim perfect causal attribution between a skill and an outcome.
- Depend on vendor-specific private telemetry to produce useful metrics.

## Core principle

The system should treat observability as event collection plus offline analysis.

We do not attempt to prove what the model "thought".
We measure what the system can observe:

- prompts and responses
- tool calls
- file reads
- file searches
- file edits
- skill loads
- plugin invocations
- task outcomes

## Architecture

The project is split into four layers:

1. Capture layer
- Wrap the harness and/or tools.
- Emit structured events for every meaningful operation.

2. Normalization layer
- Convert heterogeneous tool behavior into a common event model.
- Example: `sed`, `cat`, `open`, and `find` may all become `file_read` events.

3. Analysis layer
- Aggregate events by session, task, agent, skill, plugin, file, and tool.
- Compute derived metrics and approximations.

4. Reporting layer
- Produce JSON, CSV, Markdown summaries, or a small dashboard.
- Prefer project-local artifacts over transient temp directories when results should be preserved.

## Recommended MVP scope

The MVP should not try to solve everything.
It should answer four questions reliably:

1. How many tool calls were made?
2. Which files were read?
3. Which files were edited?
4. Which skills/plugins were activated and what happened afterward?

## Event model

All observability data should be stored as append-only structured events.

Recommended storage formats:

- `JSONL` for simplicity and debuggability
- `SQLite` as an optional later step for queryability

Each event should include:

- `ts`
- `session_id`
- `task_id`
- `agent_id`
- `event_type`
- `source`
- `payload`

## Canonical event types

The project should normalize activity into these event types:

- `session_started`
- `session_finished`
- `task_started`
- `task_finished`
- `agent_message`
- `tool_call_started`
- `tool_call_finished`
- `tool_call_failed`
- `file_read`
- `file_search`
- `file_edit`
- `skill_loaded`
- `plugin_invoked`

## Event schema examples

### Tool call start

```json
{
  "ts": "2026-04-14T19:10:00Z",
  "session_id": "sess_001",
  "task_id": "task_001",
  "agent_id": "main",
  "event_type": "tool_call_started",
  "source": "harness",
  "payload": {
    "tool_name": "exec_command",
    "tool_namespace": "functions",
    "arguments": {
      "cmd": "sed -n '1,200p' src/app.py"
    }
  }
}
```

### File read

```json
{
  "ts": "2026-04-14T19:10:01Z",
  "session_id": "sess_001",
  "task_id": "task_001",
  "agent_id": "main",
  "event_type": "file_read",
  "source": "tool_adapter",
  "payload": {
    "path": "src/app.py",
    "line_start": 1,
    "line_end": 200,
    "read_method": "sed",
    "bytes": 4217
  }
}
```

### File edit

```json
{
  "ts": "2026-04-14T19:12:42Z",
  "session_id": "sess_001",
  "task_id": "task_001",
  "agent_id": "main",
  "event_type": "file_edit",
  "source": "tool_adapter",
  "payload": {
    "path": "src/app.py",
    "edit_method": "apply_patch",
    "added_lines": 12,
    "removed_lines": 4
  }
}
```

### Skill loaded

```json
{
  "ts": "2026-04-14T19:09:58Z",
  "session_id": "sess_001",
  "task_id": "task_001",
  "agent_id": "main",
  "event_type": "skill_loaded",
  "source": "harness",
  "payload": {
    "skill_name": "openai-docs",
    "skill_path": ".codex/skills/.system/openai-docs/SKILL.md"
  }
}
```

## File usage model

The system should track file usage using observed spans.

For each file, maintain:

- total line count
- read spans
- merged read spans
- read coverage percentage
- edit count
- whether edits happened after read

Derived metrics:

- `distinct_files_read`
- `reads_per_file`
- `union_lines_read`
- `read_coverage_pct`
- `edited_without_prior_read`
- `read_then_edited`

## Skill and plugin effectiveness model

Because internal attention cannot be measured directly, skills and plugins should be evaluated with proxies.

### Skill activation metrics

- `skill_load_count`
- `skill_load_rate`
- `skill_loaded_without_followup_activity`
- `skill_loaded_with_relevant_tool_usage`
- `skill_loaded_with_relevant_file_reads`
- `skill_loaded_with_subsequent_edit`

### Plugin activation metrics

- `plugin_invocation_count`
- `plugin_invocation_success_rate`
- `plugin_invocation_no_effect_rate`

### Density and compression metrics

For skills and instruction sources:

- total line count
- total token estimate
- times loaded
- downstream activity after loading
- outcome association

This allows ranking:

- very long skills with low practical impact
- high-value short skills
- candidates for compression or decomposition

## What "used" means

The project must not use a single overloaded definition of "used".

Instead, usage should be classified into levels:

1. `loaded`
- The skill/plugin/instruction source was made available to the agent.

2. `consulted`
- The agent read the skill or related resource.

3. `operationalized`
- The agent performed tool calls or file interactions consistent with the skill.

4. `outcome-linked`
- The task outcome improved or the resulting action aligns with the skill's intended workflow.

## Capture strategies

There are three viable capture strategies.

### Strategy A: Harness wrapper

Best option when the execution loop is under our control.

Wrap:

- model requests
- model responses
- tool execution
- skill loading
- plugin invocation

Pros:

- cleanest and richest signal
- easy correlation with sessions and tasks

Cons:

- requires control over the runtime

### Strategy B: Tool proxy

Best option when tools are under our control but the model loop is not.

Wrap:

- shell execution tools
- file read tools
- file edit tools
- search tools

Pros:

- enough for strong file and tool analytics
- easier to retrofit

Cons:

- weaker visibility into model-side state

### Strategy C: Transcript reconstruction

Fallback option when only conversation logs or transcripts are available.

Pros:

- minimal integration required

Cons:

- incomplete
- less precise
- harder to reconstruct file spans and causality

## Recommended initial implementation

For a clean project, start with Strategy A plus B.

Build:

- a tiny local harness abstraction
- a logger
- wrapped tools
- an offline analyzer

Do not start with a dashboard.
First make sure the raw event model is stable.

## Suggested repository structure

```text
docs/
  agent-observability-project-draw.md
artifacts/
  live_runs/
  sessions/
src/
  observer/
    events.py
    logger.py
    schemas.py
    normalizers.py
    analyzer.py
    metrics.py
  harness/
    runner.py
    tool_registry.py
    skill_registry.py
  adapters/
    shell_tools.py
    file_tools.py
    skill_loader.py
examples/
  mock_session.py
data/
  events.jsonl
tests/
  test_normalizers.py
  test_metrics.py
```

## Artifact conventions

Imported sessions should be materialized inside the repository under:

- `artifacts/sessions/<session-name>/raw.codex.jsonl`
- `artifacts/sessions/<session-name>/normalized.events.jsonl`
- `artifacts/sessions/<session-name>/summary.json`
- `artifacts/sessions/<session-name>/report.html`
- `artifacts/sessions/<session-name>/report.css`

Imported session browsing should also expose:

- `artifacts/sessions/index.html`

Live observed runs should be materialized under:

- `artifacts/live_runs/run_###/`

## Initial metrics set

The first version should compute these metrics:

- total tool calls per task
- tool calls by tool name
- tool success/failure rate
- distinct files read per task
- distinct files edited per task
- file read coverage percentage
- files edited without prior read
- skill loads per task
- skill loads with no downstream effect
- plugin invocations per task

## Advanced metrics for later

These can wait until the event model is trustworthy:

- correlation between skill load and reduced tool usage
- correlation between skill load and reduced rework
- instruction density versus observed operationalization
- repeated reads of same file span
- agent inefficiency indicators
- comparison across models, prompts, or task types

## Limits and caveats

The system must be explicit about what it cannot know.

It cannot directly measure:

- internal attention
- hidden chain-of-thought usage
- exact causal impact of one instruction block

It can measure:

- observed behavior
- sequence of actions
- partial evidence of operational usage
- downstream correlations

## Truth source rules

This document is the initial truth source for the project.

Any implementation should follow these rules:

- new event types must be added here first
- metric definitions should be documented here before code relies on them
- changes to the meaning of "used", "consulted", or "operationalized" must update this file
- if implementation diverges, this document should be updated in the same change

## First build plan

1. Create a minimal event schema module.
2. Implement a JSONL logger.
3. Wrap a small set of tools:
   `exec_command`, file read operations, file edits.
4. Emit canonical events.
5. Build an offline analyzer that outputs:
   - tool counts
   - file read coverage
   - skill/plugin activation summaries
6. Validate the model on a few mocked sessions before integrating with a real harness.

## Decision summary

- Observability should be based on external events, not guessed attention.
- JSONL is the best first storage format.
- File usage should be tracked as spans, then merged into coverage.
- Skill effectiveness should be measured via downstream behavior proxies.
- The project should begin with a small, reliable MVP and only later add dashboards.
