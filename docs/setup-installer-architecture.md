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
- deeper control-plane integration with the meta-loop recipe and SOP promotion
