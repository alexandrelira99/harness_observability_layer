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
| protect the default branch | `done` | Repository policy has been confirmed by the maintainer: `main` is protected operationally in GitHub. | Revisit only if branch strategy changes. |
| require pull request reviews | `done` | Repository policy has been confirmed by the maintainer: changes to `main` go through pull requests and require codeowner approval. | Revisit only if review policy changes. |
| require at least one additional reviewer for release-critical files | `done` | [`.github/CODEOWNERS`](../.github/CODEOWNERS) exists and covers the listed release-critical files. For this repository, the intended governance model is a single codeowner approval by `@alexandrelira99` for PRs targeting `main`, including external contributions touching release-critical files. | Revisit this policy only if maintainer ownership expands. |
| enable CODEOWNERS enforcement | `done` | [`.github/CODEOWNERS`](../.github/CODEOWNERS) exists and maps critical files, and the maintainer confirmed that PRs to `main` are gated by codeowner approval. | Revisit if repository ownership or branch policy changes. |
| require status checks before merge | `done` | CI workflow exists in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml), and the maintainer confirmed the GitHub protection policy is already in place for `main`. | Keep CI coverage aligned with the expected merge gate. |

## Maintainer Accounts

- enable strong authentication for all maintainers
- minimize the set of publish-capable maintainers
- rotate tokens periodically

### Maintainer Accounts Matrix

| Item | Status | Evidence | Remaining gap |
| --- | --- | --- | --- |
| enable strong authentication for all maintainers | `external` | Authentication policy is not represented in this checkout. | Verify MFA or stronger auth for all maintainers in GitHub and PyPI. |
| minimize the set of publish-capable maintainers | `partial` | The release workflow now uses Trusted Publishing in [`.github/workflows/release.yml`](../.github/workflows/release.yml), which removes the need for a long-lived PyPI upload token in GitHub. | After the first publish, confirm that only the intended PyPI project owner has publish-capable project access. |
| rotate tokens periodically | `done` | The release workflow now uses Trusted Publishing in [`.github/workflows/release.yml`](../.github/workflows/release.yml), so the default publication path no longer depends on a long-lived PyPI API token. [`docs/pypi-release-process.md`](pypi-release-process.md) documents ongoing review of trusted-publisher configuration instead. | If a fallback token is ever introduced, bring back explicit rotation and scope review. |

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
| publish from CI, not from a workstation | `done` | Publishing is now wired through GitHub Actions Trusted Publishing in [`.github/workflows/release.yml`](../.github/workflows/release.yml), and the local policy documents CI-only publication in [`docs/pypi-release-process.md`](pypi-release-process.md) and [`CONTRIBUTING.md`](../CONTRIBUTING.md). | Revisit only for incident-response fallback procedures. |
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
| review runtime dependencies | `done` | Runtime dependencies remain intentionally empty in [pyproject.toml](../pyproject.toml), and that decision is now documented in [`docs/pypi-release-process.md`](pypi-release-process.md). | Re-review before each public release if runtime dependencies are introduced later. |
| review build dependencies | `done` | Build and release dependencies are explicitly limited to `setuptools`, `build`, `twine`, and the GitHub Trusted Publishing action across [pyproject.toml](../pyproject.toml), [`.github/workflows/release.yml`](../.github/workflows/release.yml), and [`docs/pypi-release-process.md`](pypi-release-process.md). | Re-review if packaging or release tooling expands. |
| verify no install-time side effects | `done` | [tests/test_release_surface.py](../tests/test_release_surface.py) now asserts that importing the package and building the CLI parser does not create files in a clean working directory. | Keep this test aligned if package import behavior changes. |
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
| confirm import/analyze/report flows work offline | `done` | [tests/test_release_surface.py](../tests/test_release_surface.py) now runs the main CLI `import`, `analyze`, and `report` flows while socket connection attempts are patched to fail, proving the local flows succeed without network access. | Extend later if additional CLI commands or data sources are added. |
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
| version updated intentionally | `done` | Version is explicitly set to `0.1.0` in [pyproject.toml](../pyproject.toml), mirrored in [src/harness_observability_layer/__init__.py](../src/harness_observability_layer/__init__.py), described in [CHANGELOG.md](../CHANGELOG.md), and governed by the versioning policy in [`docs/pypi-release-process.md`](pypi-release-process.md). | Keep version metadata and changelog entries updated together for each tagged release. |
| changelog or release notes prepared | `done` | Release notes now exist in [CHANGELOG.md](../CHANGELOG.md). | Keep the changelog updated for each tagged release. |
| security and privacy docs updated | `done` | Security/privacy behavior is described in [README.md](../README.md), with supporting docs in [security-and-privacy-review-plan.md](security-and-privacy-review-plan.md) and [security-audit-inventory.md](security-audit-inventory.md). | Revisit these docs whenever privacy behavior or defaults change. |
| release workflow reviewed | `done` | [`.github/workflows/release.yml`](../.github/workflows/release.yml) now runs tests before build, checks distributions with `twine`, smoke-tests wheel installation via the `hol` CLI, uploads artifact hashes, and publishes to PyPI through Trusted Publishing; the intended release policy is documented in [`docs/pypi-release-process.md`](pypi-release-process.md). | Re-review whenever packaging, publishing, or credential handling changes. |

## Snapshot

Current local assessment from this checkout:

- `done`: 22
- `partial`: 1
- `missing`: 0
- `external`: 2

Interpretation:

- artifact-level privacy, offline behavior, and release validation are in good shape
- GitHub-side release governance is now treated as satisfied based on maintainer-confirmed repository policy
- the remaining meaningful gaps are centered on PyPI publisher scope and credential hygiene
