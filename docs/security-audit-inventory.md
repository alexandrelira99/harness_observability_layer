# Security Audit Inventory

This inventory summarizes the main code and release surfaces that affect security and privacy in HOL.

## Code Surfaces

| Surface | Files | Notes |
| --- | --- | --- |
| CLI and package entry points | `src/harness_observability_layer/cli/main.py`, `pyproject.toml` | Defines user-facing commands and packaging entry point. |
| Session import and artifact creation | `src/reporting/session_artifacts.py`, `src/harness_observability_layer/plugin/api.py` | Creates local artifacts, copies raw sessions when enabled, and regenerates reports/indexes. |
| Redaction and sanitization | `src/harness_observability_layer/security.py` | Controls session id sanitization and redacted metadata/path rendering. |
| Offline analysis | `src/observer/analyzer.py`, `src/observer/metrics.py` | Computes summaries and optional filesystem-derived file metrics. |
| HTML reporting | `src/reporting/html_report.py`, `src/reporting/session_index.py` | Renders static HTML and should avoid remote assets or unsafe escaping gaps. |
| Harness/runtime execution | `src/integrations/codex_exec.py`, `src/adapters/shell_tools.py` | Uses subprocesses and should be treated as higher-risk execution surfaces. |
| Source adapters | `src/integrations/codex_jsonl.py`, `src/integrations/claude_code_jsonl.py` | Parses external JSONL session formats into canonical events. |

## Release Surfaces

| Surface | Files | Notes |
| --- | --- | --- |
| CI validation | `.github/workflows/ci.yml` | Runs test suite on pushes/PRs. |
| Release build and publish | `.github/workflows/release.yml` | Builds from version tags, runs tests, checks artifacts, and generates hashes. |
| Ownership for critical files | `.github/CODEOWNERS` | Local ownership map exists; enforcement still depends on GitHub settings. |
| Release readiness tracking | `docs/release-hardening-checklist.md`, `CHANGELOG.md` | Documents remaining hardening gaps and release notes. |

## Current Test Coverage Relevant To Hardening

- path traversal-resistant session id sanitization
- optional disabling of file-resolution enrichment
- optional disabling of raw session copies
- redacted summaries and redacted HTML output
- HTML escaping of user-derived content
- HTML remote-asset regression protection
- malformed JSONL tolerance during import

See `tests/test_security_privacy.py` for the concrete checks.

## Known Residual Risks

- branch protection, required reviews, and required status checks are external GitHub settings
- maintainer MFA, token minimization, and token rotation are external account/process controls
- subprocess-based integrations merit ongoing review if execution scope grows
- offline behavior is strongly implied by implementation, but broader end-to-end CLI coverage can still improve confidence
