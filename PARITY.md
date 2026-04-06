# Parity Status — Angella Harness

Last updated: 2026-04-06

## Summary

- Canonical document: this top-level `PARITY.md` is consumed by `scripts/run_harness_parity_diff.py`.
- Scope: Angella harness runtime behavior, tracked knowledge sync, builtin search, and output compaction.
- Requested checkpoint: 13 lanes implemented and checked by the parity diff runner.

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
- Evidence: `scripts/test_harness_self_optimize_adapter.py`
- Evidence: `scripts/test_frontier_harness_reset.py`

## Lane 4 — harness self-optimize verification-only

- Status: implemented
- Evidence: `recipes/harness-self-optimize.yaml`
- Evidence: `mcp-servers/meta_loop_ops.py`
- Evidence: `scripts/test_meta_loop_admin.py`

## Lane 5 — finalize accepted run with promotion/export/failure closure

- Status: implemented
- Evidence: `mcp-servers/meta_loop_ops.py`
- Evidence: `scripts/test_meta_loop_admin.py`

## Lane 6 — accepted finalize pre-export wiki sync

- Status: implemented
- Evidence: `mcp-servers/meta_loop_ops.py`
- Evidence: `scripts/test_meta_loop_admin.py`

## Lane 7 — verification-only scoped wiki sync

- Status: implemented
- Evidence: `mcp-servers/meta_loop_ops.py`
- Evidence: `scripts/test_meta_loop_admin.py`

## Lane 8 — admin sync backfill policy

- Status: implemented
- Evidence: `config/knowledge-policy.yaml`
- Evidence: `knowledge/index.md`
- Evidence: `knowledge/log.md`
- Evidence: `scripts/test_harness_knowledge.py`

## Lane 9 — builtin search retrieval path

- Status: implemented
- Evidence: `mcp-servers/meta_loop_ops.py`
- Evidence: `scripts/test_harness_knowledge.py`

## Lane 10 — output compaction path

- Status: implemented
- Evidence: `mcp-servers/output_compactor.py`
- Evidence: `scripts/test_harness_knowledge.py`

## Lane 11 — knowledge lint path

- Status: implemented
- Evidence: `scripts/validate_harness_schema.py`
- Evidence: `scripts/test_harness_knowledge.py`

## Lane 12 — raw source registration path

- Status: implemented
- Evidence: `knowledge/sources/index.md`
- Evidence: `scripts/test_harness_knowledge.py`

## Lane 13 — query writeback path

- Status: implemented
- Evidence: `mcp-servers/meta_loop_ops.py`
- Evidence: `scripts/test_harness_knowledge.py`

## Lane 14 — LLM-Wiki & OS Personal Agent Path

- Status: implemented
- Evidence: `recipes/personal-agent-loop.yaml`
- Evidence: `knowledge/wiki/schema.md`
- Evidence: `mcp-servers/personal_context_ops.py`
