# Changelog

## 1.0.0 - 2026-04-19

- expanded and refined session metrics, including richer attribution and guided reporting signals
- introduced a tabbed guided reporting experience with dedicated QA, workflow, cost, raw metrics, and glossary views
- redesigned the generated HTML surfaces with a dashboard-style visual system for both project and session reports
- added interface localization support for `ENG`, `PT`, and `ES`
- added persisted `Dark` and `Light` display modes for the static reporting UI

## Unreleased

- clarified project positioning and reporting surfaces in `README.md`
- documented guided report tabs, project landing page, and common use cases
- updated root-level documentation to better match the current product surface

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
