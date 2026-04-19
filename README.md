# Harness Observability Layer

Harness Observability Layer, or HOL, is a local-first toolkit for importing agent sessions, normalizing them into canonical events, and turning them into actionable reports.

Today the project is more than a thin metrics MVP. It supports:

- importing archived Codex sessions
- importing archived Claude Code sessions
- generating canonical normalized JSONL events
- computing session summaries and richer attribution metrics
- building static HTML reporting surfaces
- comparing and summarizing sessions from the CLI
- producing project-level indexes and portfolio-style markdown views

The core idea is simple: if you already have agent session archives, HOL helps you inspect how the work happened, not just what the final answer was.

## What HOL Is Good For

Common use cases include:

- reviewing how an agent used tools, files, and skills during a session
- auditing whether edits happened before reads
- understanding token usage, cache behavior, duration, and failure rates
- comparing multiple sessions for quality or efficiency differences
- building a local artifact trail for debugging agent workflows
- generating shareable static reports without needing a running server

## Current Product Surface

HOL currently has four practical layers:

1. Importers for Codex and Claude Code archived sessions
2. A canonical event pipeline that normalizes raw session logs
3. A metrics and attribution layer that computes summaries from normalized events
4. Static reporting outputs, including a guided dashboard-style site and a project sessions index

## Install

```bash
pip install harness-observability-layer
```

This exposes the unified CLI:

```bash
hol --help
```

You can also invoke the package directly:

```bash
python -m harness_observability_layer --help
```

## Development Install

For local development from this repository:

```bash
pip install -e .
```

For release validation and packaging tooling during development:

```bash
pip install -e .[dev]
```

## Quick Start

The most common path is:

```bash
hol import latest
hol analyze latest --format markdown
```

If you are developing from this repository and want to be sure you are using the local checkout instead of an older installed package, prefer:

```bash
PYTHONPATH=src python3 -m harness_observability_layer.cli.main --project-root . import latest
```

## CLI Commands

The command surface is intentionally small and stable:

### Import

```bash
hol import session <path>
hol import latest
hol import all
hol import claude-session <path>
hol import claude-latest
hol import claude-all
```

Useful flags:

- `--reimport`
- `--no-raw-copy`
- `--no-resolve-files`

### Analyze

```bash
hol analyze session <session-id> --format markdown
hol analyze latest --format markdown
hol analyze compare <session-a> <session-b>
```

### Report

```bash
hol report html <session-id>
hol report markdown <session-id>
hol report summary <session-id> --format json
```

### Index And Review

```bash
hol list --limit 5
hol portfolio --limit 10
hol failures --min-failures 1
```

## Import Flows

### Import an existing Codex session

```bash
hol import session ~/.codex/archived_sessions/rollout-YYYY-MM-DDTHH-MM-SS-....jsonl
```

Privacy-oriented variant:

```bash
hol import session ~/.codex/archived_sessions/rollout-YYYY-MM-DDTHH-MM-SS-....jsonl --no-raw-copy --no-resolve-files
```

### Import the latest archived Codex session

```bash
hol import latest
```

This picks the most recently modified eligible `rollout-*.jsonl` from `~/.codex/archived_sessions`.
Sessions whose recorded `cwd` points at a different directory are skipped. Sessions without a usable `cwd` are still eligible as a fallback.

### Import all archived Codex sessions

```bash
hol import all
```

By default, existing imported session folders are skipped.
To force reimport:

```bash
hol import all --reimport
```

### Import a Claude Code session

```bash
hol import claude-session ~/.claude/projects/<project>/<session>.jsonl
```

To import the latest Claude session from the default archive tree:

```bash
hol import claude-latest
```

Like Codex import, Claude import filters out archived sessions whose recorded `cwd` clearly belongs to another directory. Sessions without a usable `cwd` remain eligible.

## Generated Artifacts

Each imported session creates a project-local artifact folder such as:

- `hol-artifacts/sessions/<session-name>/raw.codex.jsonl`
- `hol-artifacts/sessions/<session-name>/normalized.events.jsonl`
- `hol-artifacts/sessions/<session-name>/summary.json`
- `hol-artifacts/sessions/<session-name>/metadata.json`
- `hol-artifacts/sessions/<session-name>/report.html`
- `hol-artifacts/sessions/<session-name>/report.css`

HOL also generates the guided reporting site for each imported session under:

- `hol-artifacts/page/sessions/<session-name>/index.html`
- `hol-artifacts/page/sessions/<session-name>/workflow-trace.html`
- `hol-artifacts/page/sessions/<session-name>/qa-report.html`
- `hol-artifacts/page/sessions/<session-name>/cost-efficiency.html`
- `hol-artifacts/page/sessions/<session-name>/raw-metrics.html`
- `hol-artifacts/page/sessions/<session-name>/glossary.html`

And it refreshes the project-level landing page:

- `hol-artifacts/sessions/index.html`

## Guided Report Tabs

The guided site is the most important reporting surface in the current product.

### Workflow Trace

This is the operational overview tab for one session.
Use it to inspect:

- skill activity
- top tools
- event timeline
- attribution segments
- most-touched files

This is usually the best first page when you want to understand how a session unfolded.

### QA Report

This tab highlights quality and workflow-risk signals, including:

- edited-without-read behavior
- QA-oriented insight cards
- suspicious workflow patterns worth reviewing

### Cost & Efficiency

This tab focuses on session economics and throughput:

- token totals
- cache behavior
- cost estimates
- tokens by skill
- skill token breakdown

Use it when comparing a “good answer but expensive session” against a more efficient one.

### Raw Metrics

This tab is the audit-friendly layer.
It renders the `summary.json` content directly and pairs it with attribution tables so you can move from high-level UI back to concrete serialized metrics.

### Glossary

This tab explains the abstract reporting terms that show up in the guided site and in `summary.json`, including:

- skill segments
- boundary types
- tool calling types
- skill attribution buckets

Use it when onboarding someone new to the reporting model or when a metric label feels too internal.

## Project Landing Page

The project-level landing page at `hol-artifacts/sessions/index.html` is now a dashboard-style overview of imported sessions.

It helps answer questions like:

- which session should I open first
- which session had the most tool activity
- which one had the highest failure rate
- which session appears unusually expensive or long

From there, each row links into the guided site for that specific session.

## Security And Privacy

HOL is a local-first analysis tool.

- `hol import`, `hol analyze`, `hol report`, `hol list`, `hol portfolio`, and `hol failures` operate on local files.
- HOL does not upload imported conversations, prompts, tool outputs, or reports by default.
- HOL stores imported raw sessions and derived artifacts only in local paths you control.
- Some metrics such as `total_lines` and read coverage are optional local enrichments derived from the current filesystem state.

Privacy controls available now:

- `--no-raw-copy`
- `--no-resolve-files`
- `--redact-sensitive`

Additional review docs:

- [docs/security-and-privacy-review-plan.md](docs/security-and-privacy-review-plan.md)
- [docs/security-audit-inventory.md](docs/security-audit-inventory.md)
- [docs/release-hardening-checklist.md](docs/release-hardening-checklist.md)
- [CHANGELOG.md](CHANGELOG.md)
- [SECURITY.md](SECURITY.md)
- [CONTRIBUTING.md](CONTRIBUTING.md)
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)

## Repository-Local Runtime Wrapper

The published package centers on the `hol` CLI for imports, summaries, comparisons, and reports.
The live Codex runtime wrapper remains a repository-local helper:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_codex_observed.py \
  "Say only OK" \
  --cwd /path/to/project
```

This wrapper:

- runs `codex exec --json`
- saves the raw Codex JSONL stream
- normalizes it into canonical events
- writes `summary.json`
- writes a styled `report.html`
- prints a metrics summary

By default, live runs are saved under `hol-artifacts/live_runs/run_###/`.

## Open The Reports

The generated HTML is static and does not require a server.

Recommended entry points:

- `hol-artifacts/sessions/index.html` for the project landing page
- `hol-artifacts/page/sessions/<session-name>/index.html` for the guided site of one session
- `hol-artifacts/sessions/<session-name>/report.html` for the legacy single-page report

## Citation

If you use this project in research, documentation, or derivative tooling, please cite it using [CITATION.cff](CITATION.cff).
