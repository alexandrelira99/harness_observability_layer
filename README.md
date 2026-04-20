# Harness Observability Layer

Harness Observability Layer, or HOL, is a local-first dashboard for inspecting archived agent sessions from the current project.

Today HOL centers on a localhost experience:

- it discovers Codex and Claude Code session archives that belong to the current repository
- it normalizes those sessions into a shared event model in memory
- it computes aggregate metrics, prompt-group rankings, turn rankings, and prescriptive insights
- it serves a project dashboard locally at `http://localhost`

The main product experience is one command:

```bash
hol init
```

## What HOL Does Today

HOL is built for questions like:

- where did spend accumulate in this project
- which prompts or turns were disproportionately expensive
- whether long context or missing `/clear` is driving cost
- whether model choice looks justified
- which sessions deserve review first

The dashboard is project-level first. It gives you one entrypoint with:

- aggregate spend and token cards
- prompt-group and turn rankings
- model mix and daily trends
- sessions requiring attention
- prescriptive insights based on the imported session behavior

## Install

```bash
pip install harness-observability-layer
```

This exposes:

```bash
hol --help
```

You can also run the package directly during development:

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

From the project you want to inspect:

```bash
hol init
```

That starts a local dashboard server and opens the browser to:

```text
http://localhost:3845
```

Useful variants:

```bash
hol init --no-open
hol init --port 4000
hol init --resolve-files
```

If you want the aggregate payload that powers the dashboard:

```bash
hol data
```

## CLI Surface

HOL currently exposes a deliberately small command surface:

### Start the dashboard

```bash
hol init
```

Flags:

- `--port`
- `--host`
- `--no-open`
- `--resolve-files`

### Print the live aggregate JSON

```bash
hol data
```

Flags:

- `--resolve-files`

## Local Server

When HOL is running, it serves:

- `/` for the dashboard HTML
- `/api/data` for the current aggregate JSON
- `/api/refresh` to rebuild the in-memory aggregate and return a small status payload

The default bind is:

```text
127.0.0.1:3845
```

## Session Discovery

HOL automatically looks for both Codex and Claude Code archives and filters them to the current project when the archived session records a matching `cwd`.

### Codex discovery

Resolution order:

1. `HOL_CODEX_ARCHIVED_DIR`
2. `CODEX_ARCHIVED_SESSIONS_DIR`
3. auto-discovery of local defaults such as:
   - `$XDG_DATA_HOME/codex/archived_sessions`
   - `~/.config/codex/archived_sessions`
   - `~/.codex/archived_sessions`

### Claude Code discovery

Resolution order:

1. `HOL_CLAUDE_ARCHIVED_DIR`
2. `CLAUDE_ARCHIVED_SESSIONS_DIR`
3. auto-discovery of local defaults such as:
   - `$XDG_DATA_HOME/claude/projects`
   - `~/.config/claude/projects`
   - `~/.claude/projects`

Sessions without a usable `cwd` remain eligible. Sessions that clearly belong to another project are skipped.

## Privacy And Security

HOL is intended to stay local-first.

Current behavior:

- session archives are read from local disk
- normalization and aggregation happen in memory
- the dashboard is served from localhost
- HOL does not require a remote backend to produce the dashboard

The localhost dashboard currently exposes project aggregates through `/api/data`, so it should be treated as local sensitive data while the server is running.

Security-sensitive areas for this repository include:

- session prompt and tool-output disclosure
- local path leakage
- archive discovery and filtering
- hidden network behavior
- localhost exposure beyond the intended interface

See also:

- [SECURITY.md](SECURITY.md)
- [CHANGELOG.md](CHANGELOG.md)
- [CONTRIBUTING.md](CONTRIBUTING.md)

## Local Development

Run the test suite with:

```bash
python -m unittest discover -s tests
```

If you want to test the local checkout directly:

```bash
PYTHONPATH=src python3 -m harness_observability_layer.cli.main --project-root . init --no-open
```

## Repository-Local Helper

This repository still contains lower-level normalization, metrics, and reporting modules that are useful for development and internal testing. The public user-facing product, however, is the localhost dashboard started by `hol init`.

## Citation

If you use this project in research, documentation, or derivative tooling, please cite it using [CITATION.cff](CITATION.cff).
