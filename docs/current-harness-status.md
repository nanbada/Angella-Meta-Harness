# Current Harness Status

This file is a handoff snapshot for the next work session.

## Main branch for structure work

- branch: `codex/gemma4-default-finalize-meta-loop`
- PR: [#6](https://github.com/nanbada/Angella/pull/6)
- purpose: merge-ready harness structure, control-plane policy, live run stabilization, and the stale config overwrite fix
- merge intent: merge target

## Proof / reference branches

- PR [#7](https://github.com/nanbada/Angella/pull/7)
  - accepted `recipe-runtime` proof/reference export
- PR [#8](https://github.com/nanbada/Angella/pull/8)
  - accepted `setup-yes-warm` live patch-producing proof/reference export
  - reference proof only, not intended for merge

## Merge policy

- PR #6 is the only merge target
- PR #7 and PR #8 stay open as proof/reference PRs
- future accepted meta-loop exports should use new `codex/meta-loop-*` branches and new draft PRs instead of reusing #7 or #8

## Coverage matrix

| Component | Latest outcome | Evidence |
| --- | --- | --- |
| `setup-check` | verification-only clean exit | `angella-verification-setup-check-success-20260406-1000` |
| `profile-resolution` | verification-only clean exit | `angella-profile-resolution-verification-20260406-1005` |
| `recipe-runtime` | verification-only clean exit | `angella-verification-recipe-runtime-verification-20260406-1000` |
| `setup-yes-warm` | accepted live patch-producing proof | PR [#8](https://github.com/nanbada/Angella/pull/8) |

## Verified paths

- verification-only live self-optimize run records both `summary.json` and `report.md` and does not force finalize
- verification-only summary updates now preserve `objective_component`, so inspection no longer collapses those runs to `unspecified`
- tracked harness wiki now has canonical entrypoints in `knowledge/schema.md`, `knowledge/index.md`, `knowledge/log.md`, and `PARITY.md`
- tracked harness wiki now includes `knowledge/sources/*.md` raw-source mirror pages and `knowledge/queries/*.md` saved query pages
- accepted run finalize creates knowledge promotion artifacts, summary annotations, export branch, and draft PR
- accepted run finalize now also closes matching `failures/open/*.json` artifacts for the same `source_run_id`
- accepted and verification-only paths now both trigger tracked wiki sync plus builtin SQLite knowledge indexing
- parity audits now write `.cache/angella/control-plane/parity-state.json` and recovery hints for failed lanes
- live `setup-yes-warm` bug reproduction and accepted fix are proven by PR #8
- `setup-check`, `profile-resolution`, and `recipe-runtime` all reached benchmark execution and exited cleanly through verification-only live runs

## Known operational notes

- default harness is now frontier-first; keep local runtimes such as `ollama serve` running only when fallback/augment paths are intended
- `mlx-community/gemma-4-31b-it-4bit` (optimal local setting for M3 Pro 36GB) is added to `harness-models.yaml` as the `mlx_gemma4_31b_it_4bit` model tier
- experimental `rtk` (Run-Time Kit) module and `frontier_token_saver_lab` profile were completely removed to prevent metric-swallowing bugs
- `bash setup.sh --install-only --yes` now overwrites stale Goose config deterministically
- install drift summary is written to `.cache/angella/control-plane/install/summary.json`
- `harness-self-optimize` should call `inspect_control_plane(format=markdown)` and `describe_harness_component` before broader exploration
- `harness-self-optimize` should read matching tracked `knowledge/sops/` or `knowledge/skills/` before broader exploration when a related failure type or worker pattern already exists
- `harness-self-optimize` should call `search_harness_knowledge` immediately after control-plane inspection and fall back to `knowledge/index.md` / `knowledge/log.md` when search is empty
- `scripts/harness_catalog.py` now needs to stay compatible with `/usr/bin/python3` on macOS because `setup-check` can execute under Python 3.9

## Merge readiness checklist

- `python3 scripts/test_control_plane_logging.py`
- `python3 scripts/test_frontier_harness_reset.py`
- `python3 scripts/test_meta_loop_admin.py`
- `python3 scripts/test_harness_self_optimize_adapter.py`
- `python3 scripts/test_harness_knowledge.py`
- `python3 scripts/test_harness_parity_diff.py`
- `python3 scripts/test_optional_providers.py`
- `python3 scripts/validate_harness_schema.py`
- `python3 scripts/run_harness_parity_diff.py`
- `bash scripts/test_setup_flows.sh`
- `bash scripts/check-secrets.sh`
- PR body for #6 reflects merge-target status
- PR bodies for #7 and #8 explicitly state reference-proof policy

## Next likely tasks

- backfeed promoted knowledge from proof/reference branches into the merge-target branch so accepted learning is reused without manual copy
- secure an accepted live patch-producing proof for `profile-resolution` or `recipe-runtime`
- decide whether builtin search should stay SQLite-only or add optional `qmd` provider as a v2 adapter
- decide whether heuristic compaction telemetry should expand from search/report snippets into broader benchmark output payloads
- decide the policy boundary for auto-exporting generated wiki files versus operator-confirmed export packaging
- decide whether to keep the latest verification-only run artifacts as reference notes in PR #6
- merge PR #6 after review, then leave PR #7 and PR #8 as archived proof/reference branches
