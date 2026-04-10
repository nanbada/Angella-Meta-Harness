# Setup Installer Architecture

This document describes the current structural design of the Angella installer.

## Goals

- keep the existing `setup.sh` user entrypoint stable
- split the installer into explicit bootstrap and install stages
- make the runtime Python environment deterministic and reusable
- support repository-local cache paths instead of relying on `$HOME` alone
- allow an optional wheelhouse strategy for restricted or repeatable installs
- resolve lead/planner/worker models from a catalog instead of hard-coding them
- create a control-plane layout for telemetry, failures, and reusable knowledge

## Stages

### Stage 1: Bootstrap

Handled by [`scripts/setup-bootstrap.sh`](../../scripts/setup-bootstrap.sh).

Responsibilities:
- runtime tool checks (`brew`, `goose`, local fallback runtimes when selected)
- harness catalog/profile resolution
- frontier-first worker selection and local fallback/cache metadata resolution
- base Python detection
- reusable bootstrap environment creation under `.cache/angella/bootstrap-venv`
- bootstrap state persistence
- MCP dependency installation into the bootstrap environment

### Stage 2: Install

Handled by [`scripts/setup-install.sh`](../../scripts/setup-install.sh).

Responsibilities:
- load `.env.mlx` or `.env.mlx.example`
- render config and recipe templates
- render both `autoresearch-loop` and `harness-self-optimize` recipes into Goose
- render custom provider templates when needed
- install rendered Goose config/recipes into `$HOME/.config/goose`
- compare rendered hashes with preexisting Goose config/recipe hashes before overwrite
- record install drift summary and telemetry under `.cache/angella/control-plane/install/`
- create the control-plane layout under `.cache/angella/control-plane`
- create local log directories
- print runtime follow-up instructions

## User entrypoints

The main entrypoint remains [`setup.sh`](../../setup.sh).

Supported modes:
- `bash setup.sh --check`
- `bash setup.sh --yes`
- `bash setup.sh --bootstrap-only`
- `bash setup.sh --install-only`
- `bash setup.sh --list-models`
- `bash setup.sh --list-harness-profiles`
- `bash setup.sh --harness-profile <id>`
- `bash setup.sh --lead-model <id> --planner-model <id> --worker-model <id>`

## Cache strategy

Repository-local cache paths:
- bootstrap env: `.cache/angella/bootstrap-venv`
- uv cache: `.cache/angella/uv`
- pip cache: `.cache/angella/pip`
- optional wheelhouse: `vendor/wheels`
- control plane: `.cache/angella/control-plane`

The current install preference order is:
1. existing bootstrap env packages
2. `uv pip install ...` when `uv` is available
3. `pip install ...` fallback

## Harness catalog

The harness catalog is stored in:

- [`config/harness-models.yaml`](../../config/harness-models.yaml)
- [`config/harness-profiles.yaml`](../../config/harness-profiles.yaml)

`scripts/harness_catalog.py` resolves:
- which lead model to use
- which planner model to use
- which worker to use in frontier-first mode
- whether a local fallback/cache path is active
- execution mode, worker tier, fallback reason, and token-saver state

The resolved selection is persisted into bootstrap state and mirrored into:

- Goose rendered config
- control-plane `current-selection.json`
- install summary hashes / drift metadata
- future run telemetry
- frontier routing metadata for worker tier and fallback reasons

## Control-plane artifacts

Recipe/runtime logging now normalizes the control-plane payloads instead of writing ad hoc JSON blobs.

- `runs/<run_id>/intent.json`
  - always includes `ideal_state_8_12_words`, `metric_key`, `success_threshold`, `binary_acceptance_checks`, `non_goals`, `operator_constraints`
  - records validation metadata for the 8-12 word ideal-state contract
- `runs/<run_id>/telemetry.jsonl`
  - appends structured loop iteration events with normalized intent and harness metadata
- `runs/<run_id>/summary.json`
  - records selected model ids, resolved provider/model names, env capability snapshot, benchmark history, failure causes, kept changes, reverted changes, and verification-only objective metadata
- `runs/<run_id>/report.md`
  - verification-only runs always write a human-readable markdown report with benchmark outcome and finalize skip reason
- `failures/open/*.json`
  - stores normalized failure artifacts with `component`, `failure_type`, `reproduction`, `expected`, `observed`, `candidate_fix_area`, and `source_run_id`
- `queue/meta-loop/*.json`
  - stores promotion reports, accepted-run finalize records, branch/export metadata, and PR bookkeeping
- `wiki-index.sqlite`
  - stores the builtin SQLite search index for tracked wiki pages and selected docs
- `knowledge-sync.json`
  - stores the latest tracked wiki sync result, updated files, indexed document count, and provider
- `parity-state.json`
  - stores machine-readable lane state, failure reason, and recovery hint for parity audits
- `install/summary.json`
  - stores rendered hashes, preexisting target hashes, applied target hashes, drift detection, drift targets, and overwrite mode
- `install/telemetry.jsonl`
  - appends setup install events so stale config drift is visible after noninteractive runs

Accepted-run finalization now does all of the following in one flow:

- generate control-plane SOP/skill drafts from the accepted run summary
- promote those drafts into tracked `knowledge/` files when the promotion rule is satisfied
- merge into an existing tracked knowledge file by appending a run-scoped addendum instead of skipping immediately
- dedupe repeated addendum content by fingerprint and repeated bullet lines
- close matching `failures/open/*.json` artifacts for the accepted run by moving them into `failures/closed/`
- sync tracked `knowledge/index.md`, `knowledge/log.md`, and `knowledge/components/*.md`
- sync tracked `knowledge/sources/*.md` and `knowledge/queries/*.md`
- rebuild the builtin SQLite wiki index
- annotate `summary.json` with promotion/export/finalization metadata
- prune stale draft and queue artifacts through the control-plane admin tool

Verification-only recording now also does all of the following:

- keep `objective_component` in `summary.json`
- sync tracked component/index/log pages without triggering draft promotion or export
- attach heuristic compaction telemetry for summary/report text
- avoid unrelated historical backfill while still updating scoped component/index/log pages

Read-only inspection is available through the control-plane admin tool and summarizes:

- recent accepted runs
- recent verification-only runs
- open failures
- pending drafts
- recent queue artifacts
- retention policy

Tracked knowledge inspection is also available through the control-plane admin tool:

- entrypoint files
- component page count
- recent wiki log entries
- builtin search index status
- source and query page counts

Additional tracked knowledge admin tools are available:

- `lint_harness_knowledge`
- `save_harness_query_page`

When `format=markdown`, inspection returns a fixed operator-facing report with:

- recent accepted runs
- recent verification-only runs
- open failures by type
- pending drafts by kind
- retention / prune due soon

Component-scoped guidance is also available through the control-plane admin tool:

- benchmark command for each harness component
- default acceptance checks
- success signal
- allowed fix surface
- priority file list to keep live self-optimize runs from exploring the whole repo

The self-optimize recipe should also read matching tracked knowledge before broader exploration:

- related `knowledge/sops/` entries for repeated failure types
- related `knowledge/skills/` entries for the currently selected worker model
- search results returned by `search_harness_knowledge`

When `dry_run=true`, draft generation, promotion, branch export, and queue writes are treated as no-op previews and must not mutate tracked files or control-plane draft state.

Accepted export branch naming is deterministic:

- prefix: `codex/meta-loop-`
- objective slug is bounded
- run id slug is bounded
- an 8-char stable hash suffix is appended

This keeps reruns stable for the same run while preventing unbounded branch names.

Queue retention policy defaults:

- draft markdown / metadata: 14 days
- draft PR markdown: 14 days
- promotion report: 21 days
- export record: 30 days
- finalize record: 30 days
- prune report: 7 days

Passing `max_age_days > 0` to prune overrides these defaults uniformly.

## Knowledge Policy

Tracked harness wiki behavior is configured in:

- [`config/knowledge-policy.yaml`](../../config/knowledge-policy.yaml)

The first implementation uses:

- tracked markdown wiki under `knowledge/**`
- selected markdown docs under `docs/**`
- builtin SQLite FTS search
- no mandatory external `qmd` dependency
- optional `qmd` provider when explicitly selected and installed

## Parity Contract

Behavioral product truth is tracked separately from handoff notes:

- [`PARITY.md`](../../PARITY.md)
- [`scripts/harness_parity_scenarios.json`](../../scripts/harness_parity_scenarios.json)
- [`scripts/run_harness_parity_diff.py`](../../scripts/run_harness_parity_diff.py)

CI and local regression paths should fail when `PARITY.md` and the scenario map drift.

Parity failure handling now also writes:

- control-plane parity state
- lane-scoped failure artifacts under `failures/open/`
- recovery hints derived from tracked harness knowledge search

## Drift policy

- install compares rendered Goose config and recipe hashes with the current target files before overwrite
- `--install-only --yes` uses deterministic overwrite and records `overwrite_mode=auto_yes_overwrite`
- interactive install warns when drift is detected and records whether the operator overwrote or kept the existing config
- the latest install decision is persisted in bootstrap state and mirrored into `install/summary.json`

## Wheelhouse strategy

An optional wheelhouse can be created with:

```bash
bash scripts/build-wheelhouse.sh
```

If `vendor/wheels` contains wheels, setup prefers them as an install source before falling back to remote package resolution.

## Remaining redesign opportunities

- explicit bootstrap environment versioning / invalidation metadata
- relocating the bootstrap env outside the repo when desired
- optional fully offline install mode using a complete wheelhouse
- richer merge/update strategy when a promoted draft targets an existing tracked knowledge file

## Harness Wiki V2 Candidates

- optional `qmd` provider behind the existing `search_harness_knowledge` tool schema instead of replacing the builtin SQLite path
- broader compaction coverage for benchmark stdout/stderr payloads, search snippets, and test output summaries while keeping billing truth out of scope
- policy split for when generated wiki files should be auto-exported, handoff-only, or operator-confirmed before PR packaging
- stronger component/entity schema if the wiki grows beyond the current harness-internal scope
