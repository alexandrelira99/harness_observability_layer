# Contributing

Thanks for contributing to Harness Observability Layer.

## Preferred Contribution Path

The preferred path for evolving this project is through pull requests to this repository.

- open an issue or draft PR when the change is non-trivial
- keep changes focused and easy to review
- prefer additive, well-documented changes over broad rewrites
- update tests and docs together with behavior changes

## Branch And Review Expectations

Until stricter GitHub protections are enabled, contributors should still follow these rules operationally:

- do not push directly to `main` for non-trivial changes
- open a pull request for code, release workflow, packaging, and security/privacy changes
- wait for CI to pass before merge
- request review for changes touching release-critical files
- for PRs targeting `main`, a review from the repository codeowner is the required approval gate for release-critical changes, including contributions from external collaborators
- treat PyPI publication as CI-only via Trusted Publishing; do not upload release artifacts from a workstation except for incident recovery explicitly approved by the maintainer

Release-critical files include:

- `pyproject.toml`
- `.github/workflows/*`
- `src/harness_observability_layer/plugin/api.py`
- `src/reporting/session_artifacts.py`
- `src/integrations/*`

## Local Development

Install locally:

```bash
pip install -e .
```

Run tests:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

## Documentation Expectations

If your change affects user-visible behavior, also update the relevant docs:

- `README.md` as the primary product-facing document
- `CHANGELOG.md`
- `docs/release-hardening-checklist.md`
- security/privacy docs when relevant
- `docs/pypi-release-process.md` for packaging, release, or dependency-policy changes

## Packaging And Release Expectations

- keep runtime dependencies minimal and intentional
- justify any new runtime or build dependency in the PR
- keep `pyproject.toml` metadata complete enough for a public PyPI release
- update version metadata and `CHANGELOG.md` together for public releases

## Licensing

This repository is licensed under the Mozilla Public License 2.0.

If you modify MPL-covered files and distribute or publish those modifications, the modified files must remain available under the MPL terms.
