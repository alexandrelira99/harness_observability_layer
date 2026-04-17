# Changelog

## 0.1.2 - 2026-04-17

- expanded session metrics and reporting coverage
- improved generated `index.html` layout behavior on wider screens
- fixed `Operational Gaps` callout overflow in the HTML report

## 0.1.0 - 2026-04-14

Initial public-release prep for Harness Observability Layer.

- package layout finalized around the `harness_observability_layer` namespace
- unified `hol` CLI added for import, analysis, reporting, portfolio, and failure views
- Codex archived-session import support added
- Claude Code archived-session import support added
- static HTML, markdown, and text reporting surfaces added
- privacy controls added: `--no-raw-copy`, `--no-resolve-files`, and `--redact-sensitive`
- session-id sanitization added for safer artifact directory names
- security/privacy regression tests added
- release workflow hardened to run tests before build and generate artifact hashes
