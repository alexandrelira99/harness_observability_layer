# Metrics Expansion Design

This document defines the planned metrics expansion for the Harness Observability Layer.

It covers every metric currently **not** captured or surfaced, with exact raw field paths, normalization changes, derived computation, and impact rationale.

This document follows the truth source rules established in `agent-observability-project.md`.

## Scope and conventions

- **Raw source** refers to the original JSONL records before normalization.
- **Canonical event** refers to the normalized `Event` dataclass emitted by the integration layers.
- **Derived metric** refers to a value computed by `compute_metrics()` from canonical events.
- **Available in** indicates which harness sources expose the underlying data.

Where a metric requires a normalization change, the change is specified as a diff against the current normalization logic. Where a metric is purely a derived computation, only the `compute_metrics()` change is specified.

---

## Phase 1 — Token usage and cost

These metrics require extracting `message.usage` and `message.model` from raw Claude Code records, and aggregating the already-passed-through `usage` dict from Codex `turn.completed` records.

### 1.1 Token usage per API call

**Derived metrics:**

- `total_input_tokens` — sum of all input tokens across the session
- `total_output_tokens` — sum of all output tokens across the session
- `total_cache_creation_tokens` — sum of cache creation tokens
- `total_cache_read_tokens` — sum of cache read tokens
- `total_tokens` — sum of all token categories

**Raw source — Claude Code:**

The raw JSONL record for `type: "assistant"` contains:

```
raw["message"]["usage"] = {
    "input_tokens": 12345,
    "output_tokens": 678,
    "cache_creation_input_tokens": 4500,
    "cache_read_input_tokens": 8000
}
```

Currently extracted at `claude_code_jsonl.py:476-504` but only the `message.content` blocks are processed. The `message.usage` dict is never read.

**Normalization change — Claude Code:**

The `AGENT_MESSAGE` event emitted at `claude_code_jsonl.py:298-313` and the `TOOL_CALL_STARTED` events emitted at `claude_code_jsonl.py:489-503` are both produced from the same `raw` record with `type == "assistant"`. Token usage should be attached to the `AGENT_MESSAGE` event since it represents the model response boundary.

Add to the `AGENT_MESSAGE` payload:

```python
payload = {
    "message": "\n".join(texts),
    "phase": "assistant",
    "usage": raw.get("message", {}).get("usage"),  # NEW
}
```

The `_assistant_text_message()` function at line 298 should extract `raw["message"]["usage"]` and include it in the returned event payload.

**Raw source — Codex:**

The raw JSONL record for `type: "turn.completed"` contains:

```
raw["usage"] = {
    "input_tokens": 12345,
    "output_tokens": 678,
    ...
}
```

This is already passed through as `payload["usage"]` in `codex_jsonl.py:167` but never aggregated.

**Computation in `compute_metrics()`:**

```python
total_input_tokens = 0
total_output_tokens = 0
total_cache_creation_tokens = 0
total_cache_read_tokens = 0

for event in events:
    if event_type == AGENT_MESSAGE:
        usage = payload.get("usage") or {}
        total_input_tokens += int(usage.get("input_tokens", 0))
        total_output_tokens += int(usage.get("output_tokens", 0))
        total_cache_creation_tokens += int(usage.get("cache_creation_input_tokens", 0))
        total_cache_read_tokens += int(usage.get("cache_read_input_tokens", 0))
    elif event_type == TASK_FINISHED:
        usage = payload.get("usage") or {}
        total_input_tokens += int(usage.get("input_tokens", 0))
        total_output_tokens += int(usage.get("output_tokens", 0))
        total_cache_creation_tokens += int(usage.get("cache_creation_input_tokens", 0))
        total_cache_read_tokens += int(usage.get("cache_read_input_tokens", 0))
```

Output keys added to the summary dict:

```python
"total_input_tokens": total_input_tokens,
"total_output_tokens": total_output_tokens,
"total_cache_creation_tokens": total_cache_creation_tokens,
"total_cache_read_tokens": total_cache_read_tokens,
"total_tokens": total_input_tokens + total_output_tokens + total_cache_creation_tokens + total_cache_read_tokens,
```

**Impact:**

- Enables cost estimation when combined with model identification.
- Enables efficiency metrics like `tokens_per_tool_call` and `tokens_per_edit`.
- Cache metrics (`cache_read_tokens`, `cache_creation_tokens`) reveal prompt caching effectiveness — a session with high cache hit rate is cheaper per turn.

**Caveats:**

- Codex token counts are per-turn, not per-API-call. A single turn may contain multiple API calls internally. The metric is "turn-level token usage" for Codex.
- Token counts are only available when the raw JSONL contains them. Some session formats or export modes may omit them. All token metrics should default to `0` when absent.

---

### 1.2 Model identification

**Derived metrics:**

- `model` — the model identifier used in the session
- `models_used` — set of distinct model identifiers (if the session switched models)

**Raw source — Claude Code:**

```
raw["message"]["model"] = "claude-sonnet-4-20250514"
```

Available on every `type: "assistant"` record. Currently never extracted.

**Normalization change — Claude Code:**

Add `model` to the `AGENT_MESSAGE` payload:

```python
payload = {
    "message": "\n".join(texts),
    "phase": "assistant",
    "usage": raw.get("message", {}).get("usage"),
    "model": raw.get("message", {}).get("model"),  # NEW
}
```

**Raw source — Codex:**

Model information is available in the `session_meta` record:

```
raw["payload"]["model_provider"] = "openai"
```

This is already captured in `SESSION_STARTED` payload at `codex_jsonl.py:188`. The `model_provider` field identifies the provider, but the actual model name (e.g., `o3`, `gpt-4.1`) may not be available in all Codex JSONL variants. When available, it should be extracted from the `session_meta` payload or individual response records.

**Computation in `compute_metrics()`:**

```python
models_used = set()
for event in events:
    if event_type == AGENT_MESSAGE:
        model = payload.get("model")
        if model:
            models_used.add(model)
```

Output keys:

```python
"model": next(iter(models_used), None),
"models_used": sorted(models_used),
```

**Impact:**

- Required for cost estimation (different models have different per-token pricing).
- Enables cross-model comparison (the "comparison across models" advanced metric from the design doc).
- Allows filtering and grouping sessions by model in portfolio views.

---

### 1.3 Cost estimation

**Derived metrics:**

- `estimated_cost_usd` — estimated total cost in USD

**Computation in `compute_metrics()`:**

This is a derived metric computed from token counts and model identification. It requires a pricing table:

```python
PRICING_PER_MILLION_TOKENS = {
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0, "cache_write": 3.75, "cache_read": 0.30},
    "claude-opus-4-20250514": {"input": 15.0, "output": 75.0, "cache_write": 18.75, "cache_read": 1.50},
    "claude-haiku-3-20250414": {"input": 0.80, "output": 4.0, "cache_write": 1.00, "cache_read": 0.08},
}
```

Cost computation:

```python
def estimate_cost(tokens, model):
    pricing = PRICING_PER_MILLION_TOKENS.get(model)
    if not pricing:
        return None
    input_cost = (tokens["total_input_tokens"] / 1_000_000) * pricing["input"]
    output_cost = (tokens["total_output_tokens"] / 1_000_000) * pricing["output"]
    cache_write_cost = (tokens["total_cache_creation_tokens"] / 1_000_000) * pricing["cache_write"]
    cache_read_cost = (tokens["total_cache_read_tokens"] / 1_000_000) * pricing["cache_read"]
    return round(input_cost + output_cost + cache_write_cost + cache_read_cost, 4)
```

Output key:

```python
"estimated_cost_usd": estimate_cost(token_totals, model),
```

**Impact:**

- Directly answers "how much did this session cost?"
- Enables cost comparison across sessions and models.
- Feeds into portfolio-level cost tracking.

**Caveats:**

- This is an approximation. Actual billing depends on the provider's accounting.
- The pricing table must be maintained as Anthropic/OpenAI update prices.
- For models not in the pricing table, the value should be `None` rather than `0` to avoid misleading the user.
- Codex sessions using OpenAI models have different token pricing; the table should cover both provider families.

---

### 1.4 Cache effectiveness

**Derived metrics:**

- `cache_hit_rate_pct` — percentage of input tokens served from cache

**Computation:**

```python
total_input = total_input_tokens + total_cache_read_tokens
cache_hit_rate_pct = round((total_cache_read_tokens / total_input) * 100, 2) if total_input else 0.0
```

Output key:

```python
"cache_hit_rate_pct": cache_hit_rate_pct,
```

**Impact:**

- High cache hit rate (>80%) indicates effective prompt reuse and lower costs.
- Low cache hit rate may indicate excessive context churn or inefficient session structure.
- Useful for evaluating whether CLAUDE.md files and skill organization are cost-effective.

---

## Phase 2 — Duration and latency

These metrics require computing time deltas from existing timestamps. No normalization changes needed — all required data is already in canonical events.

### 2.1 Session wall-clock duration

**Derived metrics:**

- `session_duration_seconds` — total elapsed time from first to last event

**Computation in `compute_metrics()`:**

```python
from datetime import datetime, timezone

def _parse_ts(ts_str):
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None

timestamps = [_parse_ts(e.get("ts")) for e in events]
valid_ts = [t for t in timestamps if t is not None]
session_duration_seconds = (valid_ts[-1] - valid_ts[0]).total_seconds() if len(valid_ts) >= 2 else 0.0
```

Output key:

```python
"session_duration_seconds": round(session_duration_seconds, 2),
```

**Impact:**

- Fundamental "how long did this take?" metric.
- Enables productivity metrics like `edits_per_hour` and `tool_calls_per_minute`.
- Reveals sessions that ran for hours vs minutes.

---

### 2.2 Per-tool-call latency

**Derived metrics:**

- `tool_call_durations_by_name` — mapping from tool name to list of durations in seconds
- `avg_tool_duration_by_name` — mapping from tool name to average duration
- `median_tool_duration_by_name` — mapping from tool name to median duration

**Computation in `compute_metrics()`:**

Requires pairing `TOOL_CALL_STARTED` with `TOOL_CALL_FINISHED` using `call_id`:

```python
call_start_times = {}  # call_id -> datetime
tool_durations = defaultdict(list)  # tool_name -> [duration_seconds]

for event in events:
    if event_type == TOOL_CALL_STARTED:
        call_id = payload.get("call_id")
        ts = _parse_ts(event.get("ts"))
        if call_id and ts:
            call_start_times[call_id] = ts
    elif event_type in (TOOL_CALL_FINISHED, TOOL_CALL_FAILED):
        call_id = payload.get("call_id")
        ts = _parse_ts(event.get("ts"))
        if call_id and ts and call_id in call_start_times:
            duration = (ts - call_start_times.pop(call_id)).total_seconds()
            tool_name = payload.get("tool_name", "unknown")
            tool_durations[tool_name].append(duration)

avg_tool_duration_by_name = {
    name: round(sum(durs) / len(durs), 3)
    for name, durs in tool_durations.items()
}
```

Output keys:

```python
"tool_call_durations_by_name": {k: sorted(v) for k, v in tool_durations.items()},
"avg_tool_duration_by_name": avg_tool_duration_by_name,
"total_tool_duration_seconds": round(sum(d for ds in tool_durations.values() for d in ds), 2),
```

**Impact:**

- Identifies which tools are latency bottlenecks.
- Detects slow shell commands vs fast file reads.
- Enables "agent efficiency" — high tool latency with low output may indicate poor command choices.

**Caveats:**

- Timestamps in Claude Code observed blocks share the `occurred_at` value for both start and finish of the same call, so duration may be `0` for those calls. Only natively paired start/finish events yield real durations.
- Codex `response_item` timestamps may not capture actual execution time, only the event emission time.

---

### 2.3 Per-task duration

**Derived metrics:**

- `task_durations` — mapping from task_id to duration in seconds

**Computation:**

```python
task_start_times = {}  # task_id -> datetime
task_durations = {}

for event in events:
    ts = _parse_ts(event.get("ts"))
    if not ts:
        continue
    if event_type == TASK_STARTED:
        task_start_times[event.get("task_id")] = ts
    elif event_type == TASK_FINISHED:
        tid = event.get("task_id")
        if tid in task_start_times:
            task_durations[tid] = round((ts - task_start_times.pop(tid)).total_seconds(), 2)
```

Output key:

```python
"task_durations": task_durations,
```

**Impact:**

- Reveals which turns or subtasks took the longest.
- For Codex, each turn is a task, so this gives per-turn timing.
- Enables "time per turn" comparisons across sessions.

---

## Phase 3 — Truncation and model behavior signals

### 3.1 Stop reason tracking

**Derived metrics:**

- `stop_reasons` — Counter of stop reasons across the session
- `max_tokens_stops` — count of `max_tokens` stops (truncation events)

**Raw source — Claude Code:**

```
raw["message"]["stop_reason"] = "end_turn" | "tool_use" | "max_tokens" | "stop_sequence"
```

Available on every `type: "assistant"` record. Currently never extracted.

**Normalization change — Claude Code:**

Add `stop_reason` to the `AGENT_MESSAGE` payload:

```python
payload = {
    "message": "\n".join(texts),
    "phase": "assistant",
    "usage": ...,
    "model": ...,
    "stop_reason": raw.get("message", {}).get("stop_reason"),  # NEW
}
```

**Computation in `compute_metrics()`:**

```python
stop_reasons = Counter()
for event in events:
    if event_type == AGENT_MESSAGE:
        reason = payload.get("stop_reason")
        if reason:
            stop_reasons[reason] += 1
```

Output keys:

```python
"stop_reasons": dict(stop_reasons),
"max_tokens_stops": stop_reasons.get("max_tokens", 0),
```

**Impact:**

- `max_tokens` stops indicate the model hit the output limit — a sign of context window pressure or excessively verbose responses.
- The ratio of `tool_use` stops to `end_turn` stops reveals the model's tool usage pattern. A high `tool_use` ratio means the model is actively working. A high `end_turn` ratio means more conversational/analytical sessions.
- Repeated `max_tokens` stops in sequence may indicate a stuck loop.

---

### 3.2 Continuation loop detection

**Derived metrics:**

- `continuation_loops` — count of sequences where `max_tokens` stop is followed by another `max_tokens` stop

**Computation:**

```python
continuation_loops = 0
prev_was_max_tokens = False
for event in events:
    if event_type == AGENT_MESSAGE:
        reason = payload.get("stop_reason")
        if reason == "max_tokens":
            if prev_was_max_tokens:
                continuation_loops += 1
            prev_was_max_tokens = True
        else:
            prev_was_max_tokens = False
```

Output key:

```python
"continuation_loops": continuation_loops,
```

**Impact:**

- Detects when the model is struggling to fit its response within the output limit.
- May indicate the task is too complex for a single response or the model is generating excessively verbose output.

---

## Phase 4 — Conversation and message metrics

### 4.1 User message count

**Derived metric:**

- `user_message_count` — total number of user messages in the session

**Computation in `compute_metrics()`:**

```python
user_message_count = sum(1 for e in events if e.get("event_type") == USER_MESSAGE)
```

Output key:

```python
"user_message_count": user_message_count,
```

**Impact:**

- Enables "turns per session" metric.
- Required for `tools_per_turn` and `tokens_per_turn` efficiency metrics.

---

### 4.2 Agent message metrics

**Derived metrics:**

- `agent_message_count` — total number of agent responses
- `agent_message_total_chars` — total character count of agent messages

**Computation:**

```python
agent_message_count = 0
agent_message_total_chars = 0
for event in events:
    if event_type == AGENT_MESSAGE:
        agent_message_count += 1
        msg = payload.get("message") or ""
        agent_message_total_chars += len(msg)
```

Output keys:

```python
"agent_message_count": agent_message_count,
"agent_message_total_chars": agent_message_total_chars,
```

**Impact:**

- Enables `agent_to_user_ratio` (agent_message_count / user_message_count).
- Verbosity tracking: high char count per tool call may indicate the model is over-explaining.
- Combined with token counts, enables `chars_per_output_token`.

---

### 4.3 Turns per session and tools per turn

**Derived metrics:**

- `turns_per_session` — number of user→agent cycles
- `tool_calls_per_turn` — average tool calls per user turn
- `tokens_per_turn` — average tokens per user turn

**Computation:**

```python
turns_per_session = user_message_count
tool_calls_per_turn = round(total_tool_calls / user_message_count, 2) if user_message_count else 0.0
tokens_per_turn = round(total_tokens / user_message_count, 0) if user_message_count else 0
```

Output keys:

```python
"turns_per_session": turns_per_session,
"tool_calls_per_turn": tool_calls_per_turn,
"tokens_per_turn": tokens_per_turn,
```

**Impact:**

- `tool_calls_per_turn` is a direct measure of agent productivity per interaction.
- `tokens_per_turn` reveals how expensive each user interaction is.

---

## Phase 5 — Enhanced tool metrics

### 5.1 Per-tool failure rate

**Derived metric:**

- `tool_failure_rate_by_name` — mapping from tool name to failure rate percentage

**Computation:**

```python
tool_failure_rate_by_name = {}
for tool_name in set(tool_counts) | set(tool_failures):
    calls = tool_counts.get(tool_name, 0)
    fails = tool_failures.get(tool_name, 0)
    total = calls + fails  # failures are separate events, not subsets of finished
    tool_failure_rate_by_name[tool_name] = round((fails / total) * 100, 2) if total else 0.0
```

Output key:

```python
"tool_failure_rate_by_name": tool_failure_rate_by_name,
```

**Impact:**

- A tool called 100 times with 5 failures (5%) is very different from one called 3 times with 1 failure (33%).
- Surfaces tools that the agent consistently struggles with.

---

### 5.2 Bash command categorization

**Derived metric:**

- `bash_command_categories` — Counter of categorized bash command types

**Computation:**

This requires a categorization function applied to the `arguments` of `TOOL_CALL_STARTED` events where `tool_name == "Bash"`:

```python
def _categorize_bash_command(cmd):
    if not cmd:
        return "unknown"
    cmd = cmd.strip()
    prefixes = [
        ("git ", "git"), ("git", "git"),
        ("pytest", "test"), ("python -m pytest", "test"),
        ("npm test", "test"), ("yarn test", "test"),
        ("go test", "test"), ("cargo test", "test"),
        ("npm run lint", "lint"), ("yarn lint", "lint"),
        ("ruff", "lint"), ("flake8", "lint"), ("eslint", "lint"),
        ("mypy", "lint"), ("pylint", "lint"),
        ("npm run build", "build"), ("yarn build", "build"),
        ("cargo build", "build"), ("go build", "build"),
        ("make", "build"),
        ("pip install", "install"), ("npm install", "install"),
        ("cargo add", "install"), ("go get", "install"),
        ("docker", "docker"),
        ("curl", "network"), ("wget", "network"),
        ("ssh", "network"),
        ("ls", "file_ops"), ("find", "file_ops"),
        ("mkdir", "file_ops"), ("cp ", "file_ops"),
        ("mv ", "file_ops"), ("rm ", "file_ops"),
        ("chmod", "file_ops"), ("cat ", "file_ops"),
        ("sed ", "file_ops"), ("grep", "file_ops"),
        ("rg ", "search"), ("ag ", "search"),
    ]
    lowered = cmd.lower()
    for prefix, category in prefixes:
        if lowered.startswith(prefix):
            return category
    return "other"

bash_categories = Counter()
for event in events:
    if event_type == TOOL_CALL_STARTED and payload.get("tool_name") == "Bash":
        cmd = str((payload.get("arguments") or {}).get("command", ""))
        bash_categories[_categorize_bash_command(cmd)] += 1
```

Output key:

```python
"bash_command_categories": dict(bash_categories),
```

**Impact:**

- Answers "what did the agent spend its time doing?" at a higher level than raw tool names.
- Reveals whether the agent is primarily testing, building, searching, or doing file operations.
- High `other` category may indicate unusual or ad-hoc commands worth investigating.

---

### 5.3 Tool call parallelism

**Derived metric:**

- `max_concurrent_tool_calls` — maximum number of tool calls started before any finished
- `parallel_tool_call_count` — number of times multiple tool_use blocks appeared in a single assistant message

**Computation:**

```python
active_calls = 0
max_concurrent = 0
parallel_count = 0

for event in events:
    if event_type == TOOL_CALL_STARTED:
        active_calls += 1
        max_concurrent = max(max_concurrent, active_calls)
    elif event_type in (TOOL_CALL_FINISHED, TOOL_CALL_FAILED):
        active_calls = max(0, active_calls - 1)

parallel_tool_call_count = sum(
    1 for e in events
    if e.get("event_type") == TOOL_CALL_STARTED
    and e.get("source") == "claude_code_jsonl"
)
# Alternative: count assistant messages with >1 tool_use block
# This requires detecting multi-tool assistant messages during normalization.
```

Output keys:

```python
"max_concurrent_tool_calls": max_concurrent,
```

**Impact:**

- Indicates the model's parallelism strategy. A model that dispatches multiple reads simultaneously is more efficient.
- Low parallelism with high sequential calls may indicate suboptimal task decomposition.

---

## Phase 6 — Enhanced file metrics

### 6.1 Re-read detection

**Derived metric:**

- `reread_files` — list of files that were read more than once
- `reread_count_by_file` — mapping from file path to number of times re-read

**Computation in `compute_metrics()`:**

```python
file_read_count = Counter()
for event in events:
    if event_type == FILE_READ:
        path = payload.get("path")
        if path:
            file_read_count[path] += 1

reread_count_by_file = {p: c for p, c in file_read_count.items() if c > 1}
reread_files = sorted(reread_count_by_file.keys())
```

Output keys:

```python
"reread_files": reread_files,
"reread_count_by_file": reread_count_by_file,
"reread_file_count": len(reread_files),
```

**Impact:**

- Listed in the design doc under "advanced metrics for later".
- Re-reading the same file multiple times is a strong inefficiency indicator — the agent may be forgetting context or re-scanning files it already read.
- High re-read counts on a specific file may indicate the file is complex or poorly structured.

---

### 6.2 Re-read of same line spans (overlap detection)

**Derived metric:**

- `overlapping_read_spans_by_file` — mapping from file path to count of overlapping read spans

**Computation:**

```python
overlapping_read_spans_by_file = {}
for path, spans in file_read_spans.items():
    if len(spans) <= 1:
        continue
    overlaps = 0
    sorted_spans = sorted(spans)
    for i in range(len(sorted_spans)):
        for j in range(i + 1, len(sorted_spans)):
            s1, e1 = sorted_spans[i]
            s2, e2 = sorted_spans[j]
            if s2 <= e1:
                overlaps += 1
    if overlaps > 0:
        overlapping_read_spans_by_file[path] = overlaps
```

Output key:

```python
"overlapping_read_spans_by_file": overlapping_read_spans_by_file,
```

**Impact:**

- More granular than re-read detection — catches when the agent reads overlapping line ranges of the same file.
- Indicates context waste: the same lines were read multiple times.

---

### 6.3 File create / modify / delete classification

**Derived metric:**

- `files_created` — count of files that were created (not previously existing)
- `files_modified` — count of files that were modified
- `files_deleted` — count of files that were deleted
- `file_edit_types` — Counter of edit types: `create`, `update`, `delete`

**Normalization change — Codex:**

The `FILE_EDIT` event at `codex_jsonl.py:318` currently discards `change.get("type")`. Add it to the payload:

```python
payload = make_file_edit_payload(path, "apply_patch", added_lines, removed_lines)
payload["edit_change_type"] = change.get("type")  # "add", "update", or "delete"
```

**Normalization change — Claude Code:**

Claude Code doesn't provide explicit create/modify/delete classification. Heuristics:

- If `tool_name == "Write"` (or the tool input has a `command` containing `>` redirection), classify as `create` or `overwrite`.
- If `tool_name == "Edit"`, classify as `update`.
- Track which files appeared in `FILE_READ` before their first `FILE_EDIT` — files not previously read and then edited with `edit_method == "Edit"` are likely `update`. Files not previously read and edited with `edit_method` suggesting new content may be `create`.

Add `edit_change_type` to `FILE_EDIT` payloads where determinable:

```python
payload = make_file_edit_payload(edit_path, "Edit", added_lines, removed_lines)
payload["edit_change_type"] = "update"  # Default for Claude Code Edit tool
```

For Write tool detection:

```python
if tool_name == "Write":
    payload["edit_change_type"] = "create"
```

**Computation:**

```python
file_edit_types = Counter()
for event in events:
    if event_type == FILE_EDIT:
        change_type = payload.get("edit_change_type", "update")
        file_edit_types[change_type] += 1
```

Output keys:

```python
"file_edit_types": dict(file_edit_types),
"files_created": file_edit_types.get("add", 0),
"files_modified": file_edit_types.get("update", 0),
"files_deleted": file_edit_types.get("delete", 0),
```

**Impact:**

- Distinguishes net-new code creation from modification of existing code.
- Sessions that create many files vs modifying few are qualitatively different tasks.
- Delete events may indicate cleanup or refactoring.

---

### 6.4 Read-to-edit ratio per file

**Derived metric:**

- `file_read_to_edit_ratio` — mapping from file path to `union_lines_read / max(added_lines + removed_lines, 1)`

**Computation:**

```python
file_read_to_edit_ratio = {}
for path, stats in file_summary.items():
    edits = stats["added_lines"] + stats["removed_lines"]
    if edits > 0:
        ratio = round(stats["union_lines_read"] / edits, 2)
        file_read_to_edit_ratio[path] = ratio
```

Output key:

```python
"file_read_to_edit_ratio": file_read_to_edit_ratio,
```

**Impact:**

- High ratio (read extensively, edited little): the file was consulted but not deeply changed. May indicate exploration or reference usage.
- Low ratio (read little, edited heavily): potentially risky — the agent made significant changes without fully understanding the file.
- Very low ratio on files in `edited_without_prior_read` is a quality risk signal.

---

### 6.5 Search-to-action correlation

**Derived metrics:**

- `searches_without_read` — count of FILE_SEARCH events not followed by a FILE_READ on a matching path
- `searches_without_edit` — count of FILE_SEARCH events not followed by a FILE_EDIT on a matching path
- `search_to_read_rate` — percentage of searches that led to at least one read

**Computation:**

This requires tracking event sequences. Since paths may not match exactly (a search in `src/` may lead to reading `src/foo.py`), a reasonable heuristic is to check if any FILE_READ occurs after the search with a path that starts with the search path:

```python
search_events = []
for event in events:
    if event_type == FILE_SEARCH:
        search_events.append(event)

search_path_set = {e.get("payload", {}).get("path") for e in search_events}
read_path_set = {e.get("payload", {}).get("path") for e in events if e.get("event_type") == FILE_READ}

searches_with_read = 0
searches_without_read = 0
for search_event in search_events:
    sp = search_event.get("payload", {}).get("path")
    if not sp:
        continue
    matched = any(rp and (rp.startswith(sp) or sp.startswith(rp)) for rp in read_path_set)
    if matched:
        searches_with_read += 1
    else:
        searches_without_read += 1

total_searches = len(search_events)
search_to_read_rate = round((searches_with_read / total_searches) * 100, 2) if total_searches else 0.0
```

Output keys:

```python
"total_searches": total_searches,
"searches_with_read": searches_with_read,
"searches_without_read": searches_without_read,
"search_to_read_rate": search_to_read_rate,
```

**Impact:**

- `searches_without_read` is an exploration waste indicator — the agent searched but found nothing useful.
- `search_to_read_rate` measures search effectiveness. A low rate may indicate poor search queries or searching in wrong directories.

---

## Phase 7 — Skill and plugin effectiveness

### 7.1 Skill loaded without follow-up activity

**Derived metric:**

- `skills_without_followup` — list of skill names loaded with no subsequent tool calls or file operations within a time window

**Computation:**

This requires tracking the temporal relationship between `SKILL_LOADED` events and subsequent tool activity:

```python
skill_activity = {}  # skill_name -> {"loaded_at": ts, "has_tool_activity": bool, "has_file_activity": bool}

for i, event in enumerate(events):
    if event_type == SKILL_LOADED:
        skill_name = payload.get("skill_name", "unknown")
        skill_ts = _parse_ts(event.get("ts"))
        # Look ahead for tool activity within a reasonable window (next 20 events)
        has_tool_activity = False
        has_file_activity = False
        for future_event in events[i+1:i+21]:
            ft = future_event.get("event_type")
            if ft in (TOOL_CALL_STARTED, TOOL_CALL_FINISHED):
                has_tool_activity = True
            if ft in (FILE_READ, FILE_EDIT, FILE_SEARCH):
                has_file_activity = True
        skill_activity[skill_name] = {
            "has_tool_activity": has_tool_activity,
            "has_file_activity": has_file_activity,
        }

skills_without_followup = sorted(
    name for name, activity in skill_activity.items()
    if not activity["has_tool_activity"] and not activity["has_file_activity"]
)
```

Output keys:

```python
"skills_without_followup": skills_without_followup,
"skills_without_followup_count": len(skills_without_followup),
```

**Impact:**

- Directly implements the `skill_loaded_without_followup_activity` metric from the design doc.
- Skills loaded but never acted upon may be unnecessary context that wastes tokens.
- This is the "loaded" vs "operationalized" distinction from the usage level model.

---

### 7.2 Plugin invocation success rate

**Derived metric:**

- `plugin_invocation_success_rate` — percentage of plugin invocations that were followed by successful completion (not followed by TOOL_CALL_FAILED)

**Computation:**

This requires correlating `PLUGIN_INVOKED` events with subsequent `TOOL_CALL_FINISHED` or `TOOL_CALL_FAILED` events. Since `PLUGIN_INVOKED` is currently only emitted by the harness (not from JSONL reconstruction), this metric is primarily useful for live sessions.

For JSONL-reconstructed sessions, plugin effectiveness can be proxied through the tool_call success rate for tools that correspond to known plugins.

Output key:

```python
"plugin_invocation_success_rate": round(successful / total * 100, 2) if total else 0.0,
```

**Impact:**

- Implements `plugin_invocation_success_rate` from the design doc.
- Low success rate may indicate broken or misconfigured plugins.

---

## Phase 8 — Session-level efficiency indicators

### 8.1 Agent efficiency score (composite)

**Derived metric:**

- `efficiency_indicators` — dict of individual efficiency signals

**Computation:**

```python
efficiency_indicators = {
    "edited_without_read_ratio": round(
        edited_without_prior_read_count / max(distinct_files_edited, 1) * 100, 2
    ),
    "reread_ratio": round(
        reread_file_count / max(distinct_files_read, 1) * 100, 2
    ),
    "failure_rate_pct": failure_rate_pct,
    "continuation_loops": continuation_loops,
    "max_tokens_stops": max_tokens_stops,
    "tool_calls_per_minute": round(
        total_tool_calls / max(session_duration_seconds / 60, 0.01), 2
    ) if session_duration_seconds > 0 else 0.0,
    "edits_per_minute": round(
        distinct_files_edited / max(session_duration_seconds / 60, 0.01), 2
    ) if session_duration_seconds > 0 else 0.0,
}
```

Output key:

```python
"efficiency_indicators": efficiency_indicators,
```

**Impact:**

- Provides a single dict for consumers to quickly assess session health.
- Each indicator can be thresholded independently (e.g., `edited_without_read_ratio > 50%` = warning).

---

### 8.2 Files read but never edited (exploration files)

**Derived metric:**

- `read_without_edit` — list of files that were read but never edited

**Computation:**

```python
read_without_edit = sorted(path for path in distinct_files_read if path not in distinct_files_edited)
```

Output keys:

```python
"read_without_edit": read_without_edit,
"read_without_edit_count": len(read_without_edit),
```

**Impact:**

- Complements `edited_without_prior_read`. Together they form a complete picture of read-edit coverage.
- Files read but never edited may be: reference files, config files, or files the agent explored but decided not to change.

---

## Summary of normalization changes

### Claude Code integration (`claude_code_jsonl.py`)

| Event type | Current payload | New payload fields |
|---|---|---|
| `AGENT_MESSAGE` | `{message, phase}` | `+usage`, `+model`, `+stop_reason` |
| `FILE_EDIT` (from Write tool) | `{path, edit_method, added_lines, removed_lines}` | `+edit_change_type` |
| `FILE_EDIT` (from Edit tool) | `{path, edit_method, added_lines, removed_lines}` | `+edit_change_type` |

### Codex integration (`codex_jsonl.py`)

| Event type | Current payload | New payload fields |
|---|---|---|
| `FILE_EDIT` | `{path, edit_method, added_lines, removed_lines}` | `+edit_change_type` |

No new canonical event types are needed. All new metrics are either:
1. Additional fields on existing event payloads (normalization layer changes).
2. New derived computations from existing events (analysis layer changes).

---

## Summary of new output keys in `compute_metrics()` return dict

### Token and cost metrics

| Key | Type | Phase |
|---|---|---|
| `total_input_tokens` | `int` | 1.1 |
| `total_output_tokens` | `int` | 1.1 |
| `total_cache_creation_tokens` | `int` | 1.1 |
| `total_cache_read_tokens` | `int` | 1.1 |
| `total_tokens` | `int` | 1.1 |
| `model` | `str \| None` | 1.2 |
| `models_used` | `list[str]` | 1.2 |
| `estimated_cost_usd` | `float \| None` | 1.3 |
| `cache_hit_rate_pct` | `float` | 1.4 |

### Duration metrics

| Key | Type | Phase |
|---|---|---|
| `session_duration_seconds` | `float` | 2.1 |
| `tool_call_durations_by_name` | `dict[str, list[float]]` | 2.2 |
| `avg_tool_duration_by_name` | `dict[str, float]` | 2.2 |
| `total_tool_duration_seconds` | `float` | 2.2 |
| `task_durations` | `dict[str, float]` | 2.3 |

### Model behavior metrics

| Key | Type | Phase |
|---|---|---|
| `stop_reasons` | `dict[str, int]` | 3.1 |
| `max_tokens_stops` | `int` | 3.1 |
| `continuation_loops` | `int` | 3.2 |

### Conversation metrics

| Key | Type | Phase |
|---|---|---|
| `user_message_count` | `int` | 4.1 |
| `agent_message_count` | `int` | 4.2 |
| `agent_message_total_chars` | `int` | 4.2 |
| `turns_per_session` | `int` | 4.3 |
| `tool_calls_per_turn` | `float` | 4.3 |
| `tokens_per_turn` | `float` | 4.3 |

### Enhanced tool metrics

| Key | Type | Phase |
|---|---|---|
| `tool_failure_rate_by_name` | `dict[str, float]` | 5.1 |
| `bash_command_categories` | `dict[str, int]` | 5.2 |
| `max_concurrent_tool_calls` | `int` | 5.3 |

### Enhanced file metrics

| Key | Type | Phase |
|---|---|---|
| `reread_files` | `list[str]` | 6.1 |
| `reread_count_by_file` | `dict[str, int]` | 6.1 |
| `reread_file_count` | `int` | 6.1 |
| `overlapping_read_spans_by_file` | `dict[str, int]` | 6.2 |
| `file_edit_types` | `dict[str, int]` | 6.3 |
| `files_created` | `int` | 6.3 |
| `files_modified` | `int` | 6.3 |
| `files_deleted` | `int` | 6.3 |
| `file_read_to_edit_ratio` | `dict[str, float]` | 6.4 |
| `total_searches` | `int` | 6.5 |
| `searches_with_read` | `int` | 6.5 |
| `searches_without_read` | `int` | 6.5 |
| `search_to_read_rate` | `float` | 6.5 |

### Skill and plugin effectiveness

| Key | Type | Phase |
|---|---|---|
| `skills_without_followup` | `list[str]` | 7.1 |
| `skills_without_followup_count` | `int` | 7.1 |

### Efficiency indicators

| Key | Type | Phase |
|---|---|---|
| `read_without_edit` | `list[str]` | 8.2 |
| `read_without_edit_count` | `int` | 8.2 |
| `efficiency_indicators` | `dict[str, float]` | 8.1 |

---

## Implementation order

The phases are ordered by dependency and impact:

1. **Phase 1** (Token usage and cost) — highest value, requires normalization changes.
2. **Phase 3** (Stop reason) — small normalization change, pairs naturally with Phase 1 since both touch the assistant message handler.
3. **Phase 4** (Conversation metrics) — pure computation, no normalization changes.
4. **Phase 2** (Duration and latency) — pure computation, no normalization changes.
5. **Phase 5** (Enhanced tool metrics) — pure computation, no normalization changes.
6. **Phase 6** (Enhanced file metrics) — partial normalization changes (edit_change_type).
7. **Phase 7** (Skill effectiveness) — pure computation, more complex logic.
8. **Phase 8** (Efficiency indicators) — composite, depends on Phases 2-6.

Phases 1 and 3 should be implemented together since they both modify the Claude Code assistant message handler. Phases 2, 4, 5, and 7 can be implemented independently in any order.

---

## Design doc status alignment

The `agent-observability-project.md` design doc lists the following under "Advanced metrics for later":

| Design doc metric | Covered by this document |
|---|---|
| correlation between skill load and reduced tool usage | Phase 7.1 |
| correlation between skill load and reduced rework | Phase 7.1 (partial — full correlation requires multi-session comparison) |
| instruction density versus observed operationalization | Phase 7.1 (partial — requires token estimation for skill files) |
| repeated reads of same file span | Phase 6.1 and 6.2 |
| agent inefficiency indicators | Phase 8.1 |
| comparison across models, prompts, or task types | Phase 1.2 (model identification enables this) |

The design doc also defines usage levels (loaded, consulted, operationalized, outcome-linked). Phases 7.1 and 7.2 implement the "loaded" → "operationalized" check. The "consulted" and "outcome-linked" levels require richer causality tracking that is deferred beyond this expansion.

---

## Truth source update

Once implemented, the following sections of `agent-observability-project.md` should be updated:

1. **Initial metrics set** — move implemented "advanced" metrics to "initial" section.
2. **Event schema examples** — add `usage`, `model`, `stop_reason` fields to `agent_message` example.
3. **File usage model** — add re-read detection and overlap metrics.
4. **Skill and plugin effectiveness model** — note which usage levels are now implemented.
