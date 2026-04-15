# Security And Privacy Review Plan

This document captures the local review scope for HOL before public package release.

## Objectives

- keep HOL local-first by default
- avoid hidden network activity during import, analysis, and report generation
- minimize retention of sensitive raw session data
- make privacy controls explicit, testable, and documented

## Current Controls

- `--no-raw-copy`: avoid storing a project-local copy of the raw imported session
- `--no-resolve-files`: avoid reading local source files to enrich line-count metrics
- `--redact-sensitive`: redact titles, paths, and message content in generated summaries/reports
- session directory names are sanitized before artifact creation
- generated HTML is static and uses only local CSS assets

## Review Areas

### Data Handling

- verify raw session storage is optional and disabled when requested
- verify redacted outputs do not leak prompt content or full local paths
- verify metadata defaults do not unnecessarily retain sensitive text

### Filesystem Access

- verify artifact writes stay inside project-controlled artifact directories
- verify path sanitization prevents unsafe directory names
- verify file-resolution enrichment can be disabled cleanly

### Network Exposure

- verify import, analyze, and report flows do not require network access
- verify generated reports do not load remote fonts, scripts, or analytics
- verify runtime dependencies do not introduce telemetry by default

### Release Surface

- verify README privacy claims match implementation
- verify release workflow keeps build artifacts and integrity hashes
- verify public release docs describe privacy controls accurately

## Minimum Pre-Release Checks

- run `python -m unittest discover -s tests -p "test_*.py"`
- review [docs/security-audit-inventory.md](security-audit-inventory.md)
- review [docs/release-hardening-checklist.md](release-hardening-checklist.md)
- confirm README links and privacy statements are current

## Out Of Scope

- hosted service operation
- server-side data retention
- multi-user tenancy controls

HOL is currently a local CLI/package, so the main risks are artifact retention, path leakage, and release-process hardening.
