# Multi-Harness Adaptation Plan

This document defines the technical path to evolve HOL from a Codex-focused importer into a reusable observability package for multiple agent harnesses.

## Goal

Support at least these harness families with a shared observability core:

- Codex
- Claude Code

The package should preserve one canonical event model while allowing source-specific parsers and adapters.

## Design Principles

1. Keep normalization source-specific and metrics source-agnostic.
2. Preserve append-only canonical events as the main contract.
3. Treat each harness adapter as a thin translation layer, not a second analytics stack.
4. Prefer useful partial coverage over waiting for perfect source fidelity.
5. Preserve backward compatibility for existing Codex commands while the CLI evolves.

