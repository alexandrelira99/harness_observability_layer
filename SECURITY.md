# Security Policy

## Supported Scope

This project is in active early-stage development. Security fixes will generally target the latest state of `main` first.

## Reporting A Vulnerability

Please do not open a public issue for a suspected security or privacy vulnerability.

Instead:

- contact the maintainer directly through GitHub
- include reproduction details, impact, affected files, and any proof-of-concept material
- mention whether the issue involves sensitive session data, local path disclosure, artifact retention, or release workflow integrity

## Triage Priorities

The highest-priority classes for this repository are:

- unintended disclosure of prompts, tool output, or local filesystem paths
- unsafe artifact writes or path traversal
- hidden network activity or telemetry in local analysis flows
- release workflow or packaging compromise

## Disclosure Approach

The goal is coordinated disclosure:

- acknowledge receipt
- validate impact
- prepare a fix
- publish the fix and any necessary release notes

## Hardening References

- [docs/security-and-privacy-review-plan.md](docs/security-and-privacy-review-plan.md)
- [docs/security-audit-inventory.md](docs/security-audit-inventory.md)
- [docs/release-hardening-checklist.md](docs/release-hardening-checklist.md)
