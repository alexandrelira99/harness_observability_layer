# Release Hardening Checklist

This checklist covers security controls that should be in place before publishing HOL broadly via PyPI or another public package channel.

Status legend:

- `done`: implemented and evidenced locally
- `partial`: some support exists, but an operational or policy gap remains
- `missing`: not implemented or not evidenced
- `external`: depends on GitHub/PyPI/org settings not verifiable from this checkout alone

## Source Control

- protect the default branch
- require pull request reviews
- require at least one additional reviewer for release-critical files
- enable CODEOWNERS enforcement
- require status checks before merge

Release-critical files:

- `pyproject.toml`
- `.github/workflows/*`
- `src/harness_observability_layer/plugin/api.py`
- `src/reporting/session_artifacts.py`
- `src/integrations/*`

### Source Control Matrix

| Item | Status | Evidence | Remaining gap |
| --- | --- | --- | --- |
| protect the default branch | `external` | No local repository policy file proves branch protection. This must be verified in GitHub branch settings. | Confirm default branch protection in the hosted repo before release. |
| require pull request reviews | `external` | No local config proves review requirements. | Confirm branch protection requires PR review before merge. |
| require at least one additional reviewer for release-critical files | `partial` | [`.github/CODEOWNERS`](../.github/CODEOWNERS) exists and covers the listed release-critical files, but every rule currently points only to `@alexandrelira99`. | Add at least one additional owner/reviewer for release-critical paths and enforce CODEOWNERS review in branch protection. |
| enable CODEOWNERS enforcement | `partial` | [`.github/CODEOWNERS`](../.github/CODEOWNERS) exists and maps critical files. | Enforcement is a GitHub branch protection setting and must be enabled remotely. |
| require status checks before merge | `partial` | CI workflow exists in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml). | Make CI a required status check in GitHub branch protection. |

## Maintainer Accounts

- enable strong authentication for all maintainers
- minimize the set of publish-capable maintainers
- rotate tokens periodically

### Maintainer Accounts Matrix

| Item | Status | Evidence | Remaining gap |
| --- | --- | --- | --- |
| enable strong authentication for all maintainers | `external` | Authentication policy is not represented in this checkout. | Verify MFA or stronger auth for all maintainers in GitHub and PyPI. |
| minimize the set of publish-capable maintainers | `external` | The release workflow uses `PYPI_API_TOKEN`, but token ownership/scope is not visible locally in [`.github/workflows/release.yml`](../.github/workflows/release.yml). | Audit PyPI owners/maintainers and repository secret access. |
| rotate tokens periodically | `external` | No rotation schedule or automation is documented locally. | Define and document token rotation cadence for PyPI and any release credentials. |

## CI And Publishing

- build in CI from tagged commits only
- publish from CI, not from a workstation
- run tests before build
- build sdist and wheel
- keep release logs and artifact hashes

### CI And Publishing Matrix

| Item | Status | Evidence | Remaining gap |
| --- | --- | --- | --- |
| build in CI from tagged commits only | `done` | [`.github/workflows/release.yml`](../.github/workflows/release.yml) triggers on `push.tags: v*`. | Keep release tags intentional and documented. |
| publish from CI, not from a workstation | `partial` | Publishing is wired through GitHub Actions + `twine upload` in [`.github/workflows/release.yml`](../.github/workflows/release.yml). | Operationally enforce CI-only publishing and avoid workstation fallback credentials/process. |
| run tests before build | `done` | Tests run in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml), and the release workflow now runs the unit suite before `python -m build` in [`.github/workflows/release.yml`](../.github/workflows/release.yml). | Keep release and CI test coverage aligned as the suite grows. |
| build sdist and wheel | `done` | The release workflow runs `python -m build`, which produces both formats by default from [pyproject.toml](../pyproject.toml). | Optionally assert both files exist in CI for stronger guarantees. |
| keep release logs and artifact hashes | `done` | GitHub Actions preserves build logs, uploads `dist/*`, and now generates/uploads `dist/SHA256SUMS` in [`.github/workflows/release.yml`](../.github/workflows/release.yml). | Optionally publish hashes in release notes as well for operator convenience. |

## Package Review

- review runtime dependencies
- review build dependencies
- verify no install-time side effects
- verify no hidden telemetry or analytics dependencies
- verify README privacy statements match real behavior

### Package Review Matrix

| Item | Status | Evidence | Remaining gap |
| --- | --- | --- | --- |
| review runtime dependencies | `partial` | Runtime dependencies are currently empty in [pyproject.toml](../pyproject.toml), which reduces supply-chain risk. | Record an explicit dependency review decision so this remains intentional as the package evolves. |
| review build dependencies | `partial` | Build dependencies are minimal: `setuptools>=68` in [pyproject.toml](../pyproject.toml). The release workflow additionally installs `build` and `twine`. | Document build dependency review and acceptable versions/tooling policy. |
| verify no install-time side effects | `partial` | Package install surface is simple: setuptools packaging plus CLI entry point in [pyproject.toml](../pyproject.toml). No obvious install hooks were found. | Add an explicit verification step or test proving install has no network calls or artifact writes. |
| verify no hidden telemetry or analytics dependencies | `done` | No runtime dependencies are declared in [pyproject.toml](../pyproject.toml), and a repo search found no telemetry/analytics libraries in `src/`. | Re-check before every public release if dependencies are added later. |
| verify README privacy statements match real behavior | `done` | README privacy claims about local-first behavior and privacy flags align with the CLI and implementation in [README.md](../README.md), [src/harness_observability_layer/cli/main.py](../src/harness_observability_layer/cli/main.py), and [src/reporting/session_artifacts.py](../src/reporting/session_artifacts.py), and the linked privacy docs now exist. | Re-review if defaults or privacy language change before release. |

## Artifact Validation

- confirm generated HTML has no remote assets
- confirm import/analyze/report flows work offline
- confirm `--no-raw-copy`, `--no-resolve-files`, and `--redact-sensitive` work as documented
- confirm path sanitization prevents unsafe artifact directory names

### Artifact Validation Matrix

| Item | Status | Evidence | Remaining gap |
| --- | --- | --- | --- |
| confirm generated HTML has no remote assets | `done` | HTML links only local `report.css` in [src/reporting/html_report.py](../src/reporting/html_report.py), and [tests/test_security_privacy.py](../tests/test_security_privacy.py) asserts no Google Fonts hosts appear. | Keep this covered as report UI evolves. |
| confirm import/analyze/report flows work offline | `partial` | Import/analyze/report paths operate on local files and generated artifacts per [README.md](../README.md), [src/harness_observability_layer/plugin/api.py](../src/harness_observability_layer/plugin/api.py), and [src/observer/analyzer.py](../src/observer/analyzer.py). | Add an explicit end-to-end offline test covering the main CLI flows. |
| confirm `--no-raw-copy`, `--no-resolve-files`, and `--redact-sensitive` work as documented | `done` | Flags are exposed in [src/harness_observability_layer/cli/main.py](../src/harness_observability_layer/cli/main.py), implemented via [src/reporting/session_artifacts.py](../src/reporting/session_artifacts.py), [src/observer/metrics.py](../src/observer/metrics.py), and [src/harness_observability_layer/security.py](../src/harness_observability_layer/security.py), and covered by [tests/test_security_privacy.py](../tests/test_security_privacy.py). | Extend coverage later to more CLI-level end-to-end tests if desired. |
| confirm path sanitization prevents unsafe artifact directory names | `done` | Session IDs are sanitized in [src/harness_observability_layer/security.py](../src/harness_observability_layer/security.py) before destination naming in [src/harness_observability_layer/plugin/api.py](../src/harness_observability_layer/plugin/api.py), with traversal-focused tests in [tests/test_security_privacy.py](../tests/test_security_privacy.py). | Consider adding more edge cases for very long or unusual Unicode names if public input variety increases. |

## Publication Readiness

- version updated intentionally
- changelog or release notes prepared
- security and privacy docs updated
- release workflow reviewed

### Publication Readiness Matrix

| Item | Status | Evidence | Remaining gap |
| --- | --- | --- | --- |
| version updated intentionally | `partial` | Version is explicitly set to `0.1.0` in [pyproject.toml](../pyproject.toml). | There is no release note or versioning policy showing this value was intentionally prepared for the next public release. |
| changelog or release notes prepared | `done` | Release notes now exist in [CHANGELOG.md](../CHANGELOG.md). | Keep the changelog updated for each tagged release. |
| security and privacy docs updated | `done` | Security/privacy behavior is described in [README.md](../README.md), with supporting docs in [security-and-privacy-review-plan.md](security-and-privacy-review-plan.md) and [security-audit-inventory.md](security-audit-inventory.md). | Revisit these docs whenever privacy behavior or defaults change. |
| release workflow reviewed | `partial` | [`.github/workflows/release.yml`](../.github/workflows/release.yml) was reviewed and hardened for tests-before-build, distribution checks, and artifact hashes. | CI-only publication policy and external repo protections still need operational confirmation. |

## Snapshot

Current local assessment from this checkout:

- `done`: 12
- `partial`: 7
- `missing`: 0
- `external`: 6

Interpretation:

- artifact-level privacy and offline behavior are in good shape
- release engineering and governance controls are only partially complete
- GitHub/PyPI policy settings still need explicit verification outside the codebase
