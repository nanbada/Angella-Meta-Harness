# Component: recipe-runtime

Generated from control-plane evidence and tracked harness knowledge.

## Contract

- benchmark command: `./.cache/angella/bootstrap-venv/bin/python scripts/test_harness_self_optimize_adapter.py`
- success signal: adapter benchmark completes and the recipe exits via accepted, revert, or verification-only
- metric key: `build_time`

## Related Knowledge

### SOPs

- [failure-meta-loop-policy-gap.md](../sops/failure-meta-loop-policy-gap.md)

### Skills

- [worker-ollama-gemma4-26b.md](../skills/worker-ollama-gemma4-26b.md)
- [worker-gemma4-local.md](../skills/worker-gemma4-local.md)

### Sources

- [source-cache-angella-control-plane-runs-angella-verification-recipe-runtime-verification-20260406-1000-summary-json.md](../sources/source-cache-angella-control-plane-runs-angella-verification-recipe-runtime-verification-20260406-1000-summary-json.md)
- [source-cache-angella-control-plane-runs-angella-verification-recipe-runtime-verification-20260406-1000-report-md.md](../sources/source-cache-angella-control-plane-runs-angella-verification-recipe-runtime-verification-20260406-1000-report-md.md)
- [source-cache-angella-control-plane-runs-angella-verification-recipe-runtime-20260405-2331-summary-json.md](../sources/source-cache-angella-control-plane-runs-angella-verification-recipe-runtime-20260405-2331-summary-json.md)
- [source-cache-angella-control-plane-runs-angella-real-recipe-runtime-20260405-220929-summary-json.md](../sources/source-cache-angella-control-plane-runs-angella-real-recipe-runtime-20260405-220929-summary-json.md)

## Recent Accepted Runs

- `angella-real-recipe-runtime-20260405-220929` metric=`build_time` summary=Accepted recipe-runtime hardening for inspection, quality criteria, deterministic export policy, and adapter validation. Meta-loop export: branch=codex/meta ... -e7dc6779, pr_url=https://github.com/nanbada/Angella/pull/7, promoted_targets=2 pr=https://github.com/nanbada/Angella/pull/7

## Recent Verification-Only Runs

- `angella-verification-recipe-runtime-verification-20260406-1000` metric=`build_time` summary=Verification-only run: achieved build_time 0.5381s. All binary acceptance checks passed.
- `angella-verification-recipe-runtime-20260405-2331` metric=`build_time` summary=Verification-only run: achieved build_time 0.4854s. No changes proposed as baseline tests passed.

## Current Open Failures

- `meta_loop_policy_gap` source_run=`angella-real-recipe-runtime-20260405-220929`
