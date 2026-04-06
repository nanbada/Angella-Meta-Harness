# Angella Harness Wiki Log

Append-only event log for accepted runs, verification-only runs, parity updates, and sync lint passes.

## [2026-04-05] accepted | recipe-runtime | angella-real-recipe-runtime-20260405-220929
<!-- angella-log:accepted:angella-real-recipe-runtime-20260405-220929 -->
- component: [recipe-runtime](components/recipe-runtime.md)
- metric: `build_time`
- summary: Accepted recipe-runtime hardening for inspection, quality criteria, deterministic export policy, and adapter validation.
Meta-loop export: branch=codex/meta
...
-e7dc6779, pr_url=https://github.com/nanbada/Angella/pull/7, promoted_targets=2

## [2026-04-05] verification | recipe-runtime | angella-verification-recipe-runtime-20260405-2331
<!-- angella-log:verification:angella-verification-recipe-runtime-20260405-2331 -->
- component: [recipe-runtime](components/recipe-runtime.md)
- metric: `build_time`
- summary: Verification-only run: achieved build_time 0.4854s. No changes proposed as baseline tests passed.

## [2026-04-05] accepted | setup-yes-warm | angella-live-setup-yes-warm-20260405-2342
<!-- angella-log:accepted:angella-live-setup-yes-warm-20260405-2342 -->
- component: [setup-yes-warm](components/setup-yes-warm.md)
- metric: `build_time`
- summary: Accepted live setup-yes-warm fix for stale config overwrite under --yes install-only.
Meta-loop export: branch=codex/meta-loop-setup-yes-warm-angella-live-s
...
-198252ce, pr_url=https://github.com/nanbada/Angella/pull/8, promoted_targets=2

## [2026-04-06] verification | setup-check | angella-verification-setup-check-error-20260406-0950
<!-- angella-log:verification:angella-verification-setup-check-error-20260406-0950 -->
- component: [setup-check](components/setup-check.md)
- metric: `build_time`
- summary: Benchmark failed with TypeError: 'type' and 'NoneType' in scripts/harness_catalog.py. This is a Python syntax/version issue (PEP 604) and the file is not in the allowed fix surface.

## [2026-04-06] verification | setup-check | angella-verification-setup-check-success-20260406-1000
<!-- angella-log:verification:angella-verification-setup-check-success-20260406-1000 -->
- component: [setup-check](components/setup-check.md)
- metric: `build_time`
- summary: Verification-only run: setup check passed successfully with build_time 0.6066s. All binary acceptance checks (exit 0 and template rendering) were satisfied.

## [2026-04-06] verification | profile-resolution | angella-profile-resolution-verification-20260406-1005
<!-- angella-log:verification:angella-profile-resolution-verification-20260406-1005 -->
- component: [profile-resolution](components/profile-resolution.md)
- metric: `build_time`
- summary: Verification-only run: profile resolution is correct and meets all acceptance criteria.

## [2026-04-06] verification | recipe-runtime | angella-verification-recipe-runtime-verification-20260406-1000
<!-- angella-log:verification:angella-verification-recipe-runtime-verification-20260406-1000 -->
- component: [recipe-runtime](components/recipe-runtime.md)
- metric: `build_time`
- summary: Verification-only run: achieved build_time 0.5381s. All binary acceptance checks passed.

## [2026-04-06] parity | PARITY.md
<!-- angella-log:parity:14080c679584 -->
- canonical file: [PARITY.md](../PARITY.md)
- role: product-truth behavioral checklist

## [2026-04-06] lint | harness knowledge sync
<!-- angella-log:lint:51d048747d29 -->
- indexed documents: `20`
- `knowledge/sops/failure-auto-yes-install-config-drift.md`
- `knowledge/sops/failure-meta-loop-policy-gap.md`
- `knowledge/skills/worker-ollama-gemma4-26b.md`
- `knowledge/components/setup-check.md`
- `knowledge/components/setup-yes-warm.md`
- `knowledge/components/setup-yes-cold.md`
- `knowledge/components/profile-resolution.md`
- `knowledge/components/recipe-runtime.md`
- `knowledge/index.md`

## [2026-04-06] lint | harness knowledge sync
<!-- angella-log:lint:183c89f8fe74 -->
- indexed documents: `20`
- `knowledge/components/setup-yes-warm.md`
- `knowledge/components/recipe-runtime.md`

## [2026-04-06] parity | PARITY.md
<!-- angella-log:parity:02ae46e9ea02 -->
- canonical file: [PARITY.md](../PARITY.md)
- role: product-truth behavioral checklist

## [2026-04-06] lint | harness knowledge sync
<!-- angella-log:lint:9dcb75234e84 -->
- indexed documents: `52`
- `knowledge/sources/source-knowledge-components-profile-resolution-md.md`
- `knowledge/sources/source-knowledge-components-recipe-runtime-md.md`
- `knowledge/sources/source-knowledge-components-setup-check-md.md`
- `knowledge/sources/source-knowledge-components-setup-yes-cold-md.md`
- `knowledge/sources/source-knowledge-components-setup-yes-warm-md.md`
- `knowledge/sources/source-knowledge-index-md.md`
- `knowledge/sources/source-knowledge-log-md.md`
- `knowledge/sources/source-knowledge-schema-md.md`
- `knowledge/sources/source-knowledge-skills-worker-apfel-lowlatency-md.md`
- `knowledge/sources/source-knowledge-skills-worker-gemma4-local-md.md`
- `knowledge/sources/source-knowledge-skills-worker-ollama-gemma4-26b-md.md`
- `knowledge/sources/source-knowledge-sops-failure-auto-yes-install-config-drift-md.md`
- `knowledge/sources/source-knowledge-sops-failure-harvest-and-promotion-md.md`
- `knowledge/sources/source-knowledge-sops-failure-meta-loop-policy-gap-md.md`
- `knowledge/sources/source-knowledge-sops-frontier-lead-selection-md.md`
- `knowledge/sources/source-docs-current-harness-status-md.md`
- `knowledge/sources/source-docs-setup-installer-architecture-md.md`
- `knowledge/sources/source-docs-hybrid-harness-md.md`
- `knowledge/sources/source-docs-promotion-content-quality-md.md`
- `knowledge/sources/source-parity-md.md`
- `knowledge/sources/source-cache-angella-control-plane-runs-angella-live-setup-yes-warm-20260405-2342-summary-json.md`
- `knowledge/sources/source-cache-angella-control-plane-runs-angella-profile-resolution-verification-20260406-1005-summary-json.md`
- `knowledge/sources/source-cache-angella-control-plane-runs-angella-profile-resolution-verification-20260406-1005-report-md.md`
- `knowledge/sources/source-cache-angella-control-plane-runs-angella-real-recipe-runtime-20260405-220929-summary-json.md`
- `knowledge/sources/source-cache-angella-control-plane-runs-angella-verification-recipe-runtime-20260405-2331-summary-json.md`
- `knowledge/sources/source-cache-angella-control-plane-runs-angella-verification-recipe-runtime-verification-20260406-1000-summary-json.md`
- `knowledge/sources/source-cache-angella-control-plane-runs-angella-verification-recipe-runtime-verification-20260406-1000-report-md.md`
- `knowledge/sources/source-cache-angella-control-plane-runs-angella-verification-setup-check-error-20260406-0950-summary-json.md`
- `knowledge/sources/source-cache-angella-control-plane-runs-angella-verification-setup-check-error-20260406-0950-report-md.md`
- `knowledge/sources/source-cache-angella-control-plane-runs-angella-verification-setup-check-success-20260406-1000-summary-json.md`
- `knowledge/sources/source-cache-angella-control-plane-runs-angella-verification-setup-check-success-20260406-1000-report-md.md`
- `knowledge/sources/index.md`
- `knowledge/components/setup-check.md`
- `knowledge/components/setup-yes-warm.md`
- `knowledge/components/setup-yes-cold.md`
- `knowledge/components/profile-resolution.md`
- `knowledge/components/recipe-runtime.md`
- `knowledge/index.md`
