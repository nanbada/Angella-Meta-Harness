# Failure Pattern: meta_loop_policy_gap

Generated from accepted run `angella-real-recipe-runtime-20260405-220929`.

## Trigger

- objective component: `recipe-runtime`
- recurring failure type: `meta_loop_policy_gap`
- observed failure count: `1`
- metric key: `build_time`

## Symptoms

- accepted evidence summary: Accepted recipe-runtime hardening for inspection, quality criteria, deterministic export policy, and adapter validation.

## Response Pattern

- check the accepted run summary, telemetry, and failure artifact together before editing
- keep the fix scoped to the component and acceptance boundary that repeated
- prefer deterministic config or workflow hardening over ad hoc operator steps

## Validation Checks

- meta loop admin tests pass
- setup flow tests pass
- harness self optimize adapter tests pass

## Reuse Boundary

- Keep draft PR flow deterministic
- Keep dry_run side effect free
- Keep accepted branch naming bounded and stable
