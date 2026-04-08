# Component: setup-yes-warm

Generated from control-plane evidence and tracked harness knowledge.

## Contract

- benchmark command: `bash scripts/test_setup_flows.sh`
- success signal: setup flow regression stays green across bootstrap, install, and --yes paths
- metric key: `build_time`

## Related Knowledge

### SOPs

- [failure-auto-yes-install-config-drift.md](../sops/failure-auto-yes-install-config-drift.md)

### Skills

- [worker-ollama-gemma4-26b.md](../skills/worker-ollama-gemma4-26b.md)
- [worker-gemma4-local.md](../skills/worker-gemma4-local.md)

### Sources

- [source-cache-angella-control-plane-runs-angella-live-setup-yes-warm-20260405-2342-summary-json.md](../sources/source-cache-angella-control-plane-runs-angella-live-setup-yes-warm-20260405-2342-summary-json.md)

## Recent Accepted Runs

- `angella-live-setup-yes-warm-20260405-2342` metric=`build_time` summary=Accepted live setup-yes-warm fix for stale config overwrite under --yes install-only. Meta-loop export: branch=codex/meta-loop-setup-yes-warm-angella-live-s ... -198252ce, pr_url=https://github.com/nanbada/Angella/pull/8, promoted_targets=2 pr=https://github.com/nanbada/Angella/pull/8

## Recent Verification-Only Runs

- _None_

## Current Open Failures

- `auto_yes_install_config_drift` source_run=`angella-live-setup-yes-warm-20260405-2342`
