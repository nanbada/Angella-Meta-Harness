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
- accepted run finalize creates knowledge promotion artifacts, summary annotations, export branch, and draft PR
- live `setup-yes-warm` bug reproduction and accepted fix are proven by PR #8
- `setup-check`, `profile-resolution`, and `recipe-runtime` all reached benchmark execution and exited cleanly through verification-only live runs

## Known operational notes

- keep `ollama serve` running before live Goose recipe runs
- `bash setup.sh --install-only --yes` now overwrites stale Goose config deterministically
- install drift summary is written to `.cache/angella/control-plane/install/summary.json`
- `harness-self-optimize` should call `inspect_control_plane(format=markdown)` and `describe_harness_component` before broader exploration
- `scripts/harness_catalog.py` now needs to stay compatible with `/usr/bin/python3` on macOS because `setup-check` can execute under Python 3.9

## Merge readiness checklist

- `python3 scripts/test_control_plane_logging.py`
- `python3 scripts/test_meta_loop_admin.py`
- `python3 scripts/test_harness_self_optimize_adapter.py`
- `bash scripts/test_setup_flows.sh`
- `bash scripts/check-secrets.sh`
- PR body for #6 reflects merge-target status
- PR bodies for #7 and #8 explicitly state reference-proof policy

## Next likely tasks

- secure an accepted live patch-producing proof for `profile-resolution` or `recipe-runtime`
- decide whether to keep the latest verification-only run artifacts as reference notes in PR #6
- merge PR #6 after review, then leave PR #7 and PR #8 as archived proof/reference branches
