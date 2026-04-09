# Parity Status — Angella Harness

Last updated: 2026-04-09

## Summary

- Canonical document: `docs/PARITY.md`
- Validator: `scripts/run_harness_parity_diff.py`
- Scope: Angella-side runtime behavior, recipe wiring, MCP integration, and transparency artifact persistence.
- *Note:* `control_plane.py` and `meta_loop_ops.py` have been restored to maintain transparency logs and PR automation path. `recipes/harness-self-optimize.yaml` remains retired.

## Lane 1 — setup check clean exit

- Status: implemented
- Evidence: `setup.sh`
- Evidence: `scripts/test_setup_flows.sh`
- Evidence: `scripts/setup-common.sh`

## Lane 2 — install-only drift overwrite

- Status: implemented
- Evidence: `scripts/setup-install.sh`
- Evidence: `scripts/test_setup_flows.sh`
- Evidence: `config/goose-config.yaml`

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

## Lane 8 — local worker stabilization (ollama + proxy)

- Status: implemented
- Evidence: `config/harness-models.yaml`
- Evidence: `scripts/ollama_proxy.py`
- Evidence: `Modelfile.gemma4-gguf`
- Evidence: `docs/setup-gemma4-ollama.md`
