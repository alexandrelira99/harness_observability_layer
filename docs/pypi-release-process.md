# PyPI Release Process

This document captures the local release policy for publishing HOL as a public Python package.

## Release Intent

- update the version in `pyproject.toml` and `src/harness_observability_layer/__init__.py` intentionally for each public release
- add or update the matching entry in `CHANGELOG.md`
- tag public releases as `v<version>`

## Dependency Review Policy

Runtime dependency policy:

- HOL should remain dependency-light by default
- an empty runtime dependency set is intentional for `0.1.0`
- any new runtime dependency must be justified in the pull request description and reflected in release docs if it changes privacy or network behavior

Build dependency policy:

- the build backend should remain minimal
- current release tooling is intentionally limited to `setuptools`, `build`, and `twine`
- any added packaging or release dependency must be reviewed for supply-chain and credential-handling impact

## Install Surface Expectations

Public releases should preserve these expectations:

- importing the package must not create project artifacts or write files implicitly
- installing the wheel must not require network access beyond package download itself
- the CLI import, analyze, and report flows must run offline against local files

These expectations are covered by release-surface tests in `tests/test_release_surface.py`.

## Publishing Policy

- public releases should be published from GitHub Actions, not from a maintainer workstation
- the release workflow should build the sdist and wheel, run tests, validate metadata, and smoke-test the built wheel before upload
- PyPI publication should use Trusted Publishing via GitHub Actions OIDC instead of a long-lived `PYPI_API_TOKEN`
- the release workflow should retain build artifacts and integrity hashes

This repository documents a CI-first publishing policy locally, but enforcement still depends on GitHub and PyPI settings outside the checkout.

## Trusted Publishing Setup

HOL now expects PyPI Trusted Publishing from GitHub Actions.

When creating the publisher in PyPI, use:

- Owner: `alexandrelira99`
- Repository name: `harness_observability_layer`
- Workflow name: `release.yml`
- Environment name: `pypi`

Recommended first-publish path:

- create a pending publisher for the project name `harness-observability-layer` in PyPI
- keep yourself as the only project `Owner` after the first successful publish
- remove any fallback `PYPI_API_TOKEN` secret from GitHub once Trusted Publishing is active

Important:

- a pending publisher does not reserve the project name until the first successful publish
- publish the first tagged release soon after configuring the pending publisher

## Maintainer Controls

- maintainers with publish rights should use MFA on GitHub and PyPI
- publish-capable accounts should be kept to the minimum practical set
- Trusted Publishing configuration and PyPI project roles should be reviewed on a regular cadence

Recommended cadence:

- review maintainers and trusted-publishing configuration once per quarter
- review again immediately after maintainer changes or any credential incident
