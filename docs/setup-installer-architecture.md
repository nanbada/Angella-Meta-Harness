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

Handled by [`scripts/setup-bootstrap.sh`](/Users/nanbada/projects/Angella/scripts/setup-bootstrap.sh).

Responsibilities:
- runtime tool checks (`brew`, `goose`, `ollama`)
- harness catalog/profile resolution
- Ollama server/model validation for the selected worker
- base Python detection
- reusable bootstrap environment creation under `.cache/angella/bootstrap-venv`
- bootstrap state persistence
- MCP dependency installation into the bootstrap environment

### Stage 2: Install

Handled by [`scripts/setup-install.sh`](/Users/nanbada/projects/Angella/scripts/setup-install.sh).

Responsibilities:
- load `.env.mlx` or `.env.mlx.example`
- render config and recipe templates
- render both `autoresearch-loop` and `harness-self-optimize` recipes into Goose
- render custom provider templates when needed
- install rendered Goose config/recipes into `$HOME/.config/goose`
- create the control-plane layout under `.cache/angella/control-plane`
- create local log directories
- print runtime follow-up instructions

## User entrypoints

The main entrypoint remains [`setup.sh`](/Users/nanbada/projects/Angella/setup.sh).

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

- [`config/harness-models.yaml`](/Users/nanbada/projects/Angella/config/harness-models.yaml)
- [`config/harness-profiles.yaml`](/Users/nanbada/projects/Angella/config/harness-profiles.yaml)

`scripts/harness_catalog.py` resolves:
- which lead model to use
- which planner model to use
- which local worker to use
- whether preview/apfel capabilities are actually enabled

The resolved selection is persisted into bootstrap state and mirrored into:

- Goose rendered config
- control-plane `current-selection.json`
- future run telemetry

## Control-plane artifacts

Recipe/runtime logging now normalizes the control-plane payloads instead of writing ad hoc JSON blobs.

- `runs/<run_id>/intent.json`
  - always includes `ideal_state_8_12_words`, `metric_key`, `success_threshold`, `binary_acceptance_checks`, `non_goals`, `operator_constraints`
  - records validation metadata for the 8-12 word ideal-state contract
- `runs/<run_id>/telemetry.jsonl`
  - appends structured loop iteration events with normalized intent and harness metadata
- `runs/<run_id>/summary.json`
  - records selected model ids, resolved provider/model names, env capability snapshot, benchmark history, failure causes, kept changes, and reverted changes
- `failures/open/*.json`
  - stores normalized failure artifacts with `component`, `failure_type`, `reproduction`, `expected`, `observed`, `candidate_fix_area`, and `source_run_id`
- `queue/meta-loop/*.json`
  - stores promotion reports, accepted-run finalize records, branch/export metadata, and PR bookkeeping

Accepted-run finalization now does all of the following in one flow:

- generate control-plane SOP/skill drafts from the accepted run summary
- promote those drafts into tracked `knowledge/` files when the promotion rule is satisfied
- merge into an existing tracked knowledge file by appending a run-scoped addendum instead of skipping immediately
- annotate `summary.json` with promotion/export/finalization metadata
- prune stale draft and queue artifacts through the control-plane admin tool

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
