# Parity Status — Angella Harness

Last updated: 2026-04-08

## Summary

- Canonical document: `docs/PARITY.md`
- Validator: `scripts/run_harness_parity_diff.py`
- Scope: Angella-side runtime behavior, recipe wiring, MCP integration, and retired-surface removal.
- Workspace `knowledge/` may point to a shared wiki via symlink or live inside the repo. Parity checks only the Angella integration surface, not every downstream consumer of that wiki.
- *Note:* `meta_loop_ops.py`, `control_plane_admin.py`, and `recipes/harness-self-optimize.yaml` were retired on 2026-04-07 and are intentionally excluded from the live surface.

## Lane 1 — setup check clean exit

- Status: implemented
- Evidence: `setup.sh`
- Evidence: `scripts/test_setup_flows.sh`

## Lane 2 — install-only drift overwrite

- Status: implemented
- Evidence: `scripts/setup-install.sh`
- Evidence: `scripts/test_setup_flows.sh`

## Lane 3 — frontier-first profile resolution

- Status: implemented
- Evidence: `scripts/harness_catalog.py`
- Evidence: `scripts/test_harness_self_optimize_adapter.py`
- Evidence: `scripts/test_frontier_harness_reset.py`

## Lane 4 — multi-tier personal agent & llm-wiki integration

- Status: implemented
- Evidence: `recipes/personal-agent-loop.yaml`
- Evidence: `mcp-servers/llmwiki_compiler_ops.py`
- Evidence: `mcp-servers/personal_context_ops.py`
- Evidence: `scripts/test_harness_knowledge.py`

## Lane 5 — output compaction path

- Status: implemented
- Evidence: `mcp-servers/output_compactor.py`
- Evidence: `scripts/test_harness_knowledge.py`

## Lane 6 — google scion coordination (file-backed mvp)

- Status: implemented
- Evidence: `mcp-servers/scion_coordination_ops.py`
- Evidence: `recipes/autoresearch-loop.yaml`
- Evidence: `scripts/test_scion_coordination.py`
- Evidence: `docs/arch-snapshot.md`

## Lane 7 — retired meta-loop/control-plane surface removed

- Status: implemented
- Evidence: `config/goose-config.yaml`
- Evidence: `.goosehints`
- Evidence: `scripts/test_meta_loop_admin.py`
