# Parity Status — Angella Harness

Last updated: 2026-04-10

## Summary

- Canonical document: `docs/PARITY.md`
- Validator: `scripts/run_harness_parity_diff.py`
- Scope: Angella-side runtime behavior, Meta-Harness wiring, MCP integration, and transparency artifact persistence.
- *Note:* Goose recipes and configs have been retired in favor of Gemini Native Meta-Harness (Brains/Hands).

## Lane 1 — setup check clean exit

- Status: implemented
- Evidence: `setup.sh`
- Evidence: `scripts/test_setup_flows.sh`
- Evidence: `scripts/setup-common.sh`

## Lane 2 — install-only drift detection

- Status: implemented
- Evidence: `scripts/setup-install.sh`
- Evidence: `scripts/test_setup_flows.sh`
- Evidence: `config/project-vars.json`

## Lane 3 — frontier-first profile resolution

- Status: implemented
- Evidence: `scripts/harness_catalog.py`
- Evidence: `scripts/test_harness_self_optimize_adapter.py`
- Evidence: `scripts/test_frontier_harness_reset.py`

## Lane 4 — meta-harness brain/hand decoupling

- Status: implemented
- Evidence: `.gemini/agents/angella-researcher.md`
- Evidence: `.gemini/skills/angella-core.md`
- Evidence: `mcp-servers/llmwiki_compiler_ops.py`
- Evidence: `scripts/test_harness_knowledge.py`

## Lane 5 — output compaction path

- Status: implemented
- Evidence: `mcp-servers/output_compactor.py`
- Evidence: `scripts/test_harness_knowledge.py`

## Lane 6 — google scion coordination (file-backed mvp)

- Status: implemented
- Evidence: `mcp-servers/scion_coordination_ops.py`
- Evidence: `scripts/test_scion_coordination.py`
- Evidence: `docs/arch-snapshot.md`

## Lane 7 — dedicated agent specialized delegation

- Status: implemented
- Evidence: `.gemini/agents/angella-implementer.md`
- Evidence: `.gemini/agents/angella-reviewer.md`
- Evidence: `.gemini/agents/angella-archivist.md`
- Evidence: `GEMINI.md`

## Lane 8 — local worker stabilization (ollama + proxy)

- Status: implemented
- Evidence: `config/harness-models.yaml`
- Evidence: `scripts/ollama_proxy.py`
- Evidence: `Modelfile.gemma4-gguf`
- Evidence: `docs/setup-gemma4-ollama.md`
