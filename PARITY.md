# Parity Status — Angella Harness

Last updated: 2026-04-07

## Summary

- Canonical document: this top-level `PARITY.md` outlines the fulfilled capabilities of the Angella harness.
- Scope: Angella harness runtime behavior, OS context synchronization, LLM-Wiki integration, and output compaction.
- *Note:* Massive over-engineered lanes (formerly relying on `meta_loop_ops.py`) were purged on 2026-04-07 to optimize for 160KB of token efficiency and refocus on the `LLM-Wiki` paradigm.

## Lane 1 — setup check clean exit

- Status: implemented
- Evidence: `scripts/test_setup_flows.sh`
- Evidence: `docs/current-harness-status.md`

## Lane 2 — install-only drift overwrite

- Status: implemented
- Evidence: `scripts/test_setup_flows.sh`
- Evidence: `docs/setup-installer-architecture.md`

## Lane 3 — frontier-first profile resolution

- Status: implemented
- Evidence: `scripts/harness_catalog.py`
- Evidence: `scripts/test_frontier_harness_reset.py`

## Lane 4 — Multi-Tier OS Personal Agent & LLM-Wiki Integration

- Status: implemented
- Evidence: `recipes/personal-agent-loop.yaml`
- Evidence: `mcp-servers/llmwiki_compiler_ops.py`
- Evidence: `mcp-servers/personal_context_ops.py`
- Evidence: `knowledge/sources/` and `knowledge/wiki/` integration logic.

## Lane 5 — Output Compaction Path

- Status: implemented
- Evidence: `mcp-servers/output_compactor.py` (Fully repaired MCP stdin loop).
