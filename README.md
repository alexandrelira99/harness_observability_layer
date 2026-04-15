# Harness Observability Layer

Minimal MVP for instrumenting an agent harness and generating observability metrics from canonical events.

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

## What exists

- canonical event model
- append-only JSONL logger
- observable file and shell adapters
- minimal harness runner
- offline analyzer
- mocked session example
- Codex session importer
- Claude Code session importer
- Codex runtime wrapper for `codex exec --json`

## Quick start

After `pip install harness-observability-layer`, the most common path is to point `hol` at an existing local session archive:

```bash
hol import latest
hol analyze latest --format markdown
```

For repository-local development, the bundled example remains available:

```bash
PYTHONPATH=src .venv/bin/python examples/mock_session.py
```

This writes events to a per-session file like `/tmp/harness_observability_layer/sess_xxxx.events.jsonl` and prints a derived metrics summary.

By default the example writes runtime data to `/tmp/harness_observability_layer/events.jsonl` so it can run cleanly in sandboxed environments.

## Import an existing Codex session

```bash
hol import session ~/.codex/archived_sessions/rollout-YYYY-MM-DDTHH-MM-SS-....jsonl
```

Privacy-oriented variant:

```bash
hol import session ~/.codex/archived_sessions/rollout-YYYY-MM-DDTHH-MM-SS-....jsonl --no-raw-copy --no-resolve-files
```

This now creates a session artifact folder inside the project:

- `hol-artifacts/sessions/<session-name>/raw.codex.jsonl`
- `hol-artifacts/sessions/<session-name>/normalized.events.jsonl`
- `hol-artifacts/sessions/<session-name>/summary.json`
- `hol-artifacts/sessions/<session-name>/report.html`
- `hol-artifacts/sessions/<session-name>/report.css`

It also refreshes:

- `hol-artifacts/sessions/index.html`

## Import the latest archived Codex session

```bash
hol import latest
```

This picks the most recently modified `rollout-*.jsonl` from `~/.codex/archived_sessions` and imports it into the project.

## Import a Claude Code session

```bash
hol import claude-session ~/.claude/projects/<project>/<session>.jsonl
```

This imports a Claude Code JSONL session into canonical events and stores it under:

- `hol-artifacts/sessions/claude-<session-name>/raw.claude.jsonl`
- `hol-artifacts/sessions/claude-<session-name>/normalized.events.jsonl`
- `hol-artifacts/sessions/claude-<session-name>/summary.json`
- `hol-artifacts/sessions/claude-<session-name>/report.html`

To import the latest Claude session from the default archive tree:

```bash
hol import claude-latest
```

## Import all archived Codex sessions

```bash
hol import all
```

This imports every `rollout-*.jsonl` from `~/.codex/archived_sessions`.

By default:

- existing imported session folders are skipped

To force reimport:

```bash
hol import all --reimport
```

## Summarize and compare imported sessions

```bash
hol list --limit 5
hol analyze latest --format markdown
hol analyze compare <session-a> <session-b>
hol report markdown <session-id>
hol report markdown <session-id> --redact-sensitive
```

## Run Codex with observability capture

From the published package, use the `hol` CLI for imports, summaries, comparisons, and reports.
The live Codex runtime wrapper below remains a repository-local helper script:

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

## Open the HTML report

After an import or live run, open the generated `report.html` file from the corresponding artifact folder.
The page is static and does not require a server.

To browse imported sessions, open:

- `hol-artifacts/sessions/index.html`

In restricted environments, running Codex itself may still require broader filesystem or network access than the parser/importer.

The legacy scripts remain available, but the package/CLI surface is now the recommended interface.

## Citation

If you use this project in research, documentation, or derivative tooling, please cite it using [CITATION.cff](CITATION.cff).
