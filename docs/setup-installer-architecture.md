# Setup Installer Architecture

This document describes the current structural design of the Angella installer.

## Goals

- keep the existing `setup.sh` user entrypoint stable
- split the installer into explicit bootstrap and install stages
- make the runtime Python environment deterministic and reusable
- support repository-local cache paths instead of relying on `$HOME` alone
- allow an optional wheelhouse strategy for restricted or repeatable installs

## Stages

### Stage 1: Bootstrap

Handled by [`scripts/setup-bootstrap.sh`](/Users/nanbada/projects/Angella/scripts/setup-bootstrap.sh).

Responsibilities:
- runtime tool checks (`brew`, `goose`, `ollama`)
- Ollama server/model validation
- base Python detection
- reusable bootstrap environment creation under `.cache/angella/bootstrap-venv`
- MCP dependency installation into the bootstrap environment

### Stage 2: Install

Handled by [`scripts/setup-install.sh`](/Users/nanbada/projects/Angella/scripts/setup-install.sh).

Responsibilities:
- load `.env.mlx` or `.env.mlx.example`
- render config and recipe templates
- install rendered Goose config/recipes into `$HOME/.config/goose`
- create local log directories
- print runtime follow-up instructions

## User entrypoints

The main entrypoint remains [`setup.sh`](/Users/nanbada/projects/Angella/setup.sh).

Supported modes:
- `bash setup.sh --check`
- `bash setup.sh --yes`
- `bash setup.sh --bootstrap-only`
- `bash setup.sh --install-only`

## Cache strategy

Repository-local cache paths:
- bootstrap env: `.cache/angella/bootstrap-venv`
- uv cache: `.cache/angella/uv`
- pip cache: `.cache/angella/pip`
- optional wheelhouse: `vendor/wheels`

The current install preference order is:
1. existing bootstrap env packages
2. `uv pip install ...` when `uv` is available
3. `pip install ...` fallback

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
- separating runtime-only dependency installation from authoring/development tools
