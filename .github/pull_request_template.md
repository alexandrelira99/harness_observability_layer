## Summary

- what changed
- why it changed

## Validation

- [ ] `python -m unittest discover -s tests -p "test_*.py"`
- [ ] docs updated when behavior changed
- [ ] changelog updated when release-facing

## Risk Review

- [ ] no unintended telemetry/network behavior introduced
- [ ] no new sensitive-data retention introduced
- [ ] release-critical files reviewed if touched

## Release-Critical Files

Mark any that were touched:

- [ ] `pyproject.toml`
- [ ] `.github/workflows/*`
- [ ] `src/harness_observability_layer/plugin/api.py`
- [ ] `src/reporting/session_artifacts.py`
- [ ] `src/integrations/*`
