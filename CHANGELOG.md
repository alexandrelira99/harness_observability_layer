# Changelog

## 1.1.0 - 2026-04-20

- simplified the public CLI around `hol init` and `hol data`
- introduced a localhost-first dashboard flow with `/api/data` and `/api/refresh`
- added live project aggregation directly from Codex and Claude Code archives without requiring exported project artifacts as the primary user journey
- refreshed the dashboard UI for stronger card hierarchy, responsive layout behavior, and a self-contained live theme
- updated root documentation to describe the current localhost product surface

## 1.0.2 - 2026-04-20

- made generic `hol import all` and `hol import latest` fall back to Claude Code when Codex is unavailable for the current project
- fixed Claude Code import crashes when `toolUseResult` is emitted as a string instead of an object

## 1.0.1 - 2026-04-20

- made archived-session import path resolution safer and more portable across machines
- added environment-variable and auto-discovery fallbacks for `hol import all` and `hol import latest`
- changed missing archive resolution to fail with a clear configuration error instead of silently importing nothing

## 1.0.0 - 2026-04-19

- expanded and refined session metrics, including richer attribution and guided reporting signals
- introduced a tabbed guided reporting experience with dedicated QA, workflow, cost, raw metrics, and glossary views
- redesigned the generated HTML surfaces with a dashboard-style visual system for both project and session reports
- added interface localization support for `ENG`, `PT`, and `ES`
- added persisted `Dark` and `Light` display modes for the static reporting UI

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
