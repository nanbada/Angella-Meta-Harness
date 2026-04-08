# Failure Pattern: auto_yes_install_config_drift

Generated from accepted run `angella-live-setup-yes-warm-20260405-2342`.

## Trigger

- objective component: `setup-yes-warm`
- recurring failure type: `auto_yes_install_config_drift`
- observed failure count: `1`
- metric key: `build_time`

## Symptoms

- accepted evidence summary: Accepted live setup-yes-warm fix for stale config overwrite under --yes install-only.

## Response Pattern

- check the accepted run summary, telemetry, and failure artifact together before editing
- keep the fix scoped to the component and acceptance boundary that repeated
- prefer deterministic config or workflow hardening over ad hoc operator steps

## Validation Checks

- install-only yes stale-config check passes
- setup flow tests pass

## Reuse Boundary

- Keep noninteractive behavior deterministic
- Preserve recipe rendering and config install paths
