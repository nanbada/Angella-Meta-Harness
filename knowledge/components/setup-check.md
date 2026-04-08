# Component: setup-check

Generated from control-plane evidence and tracked harness knowledge.

## Contract

- benchmark command: `bash setup.sh --check`
- success signal: setup.sh --check exits 0 and reports template rendering checks passed
- metric key: `build_time`

## Related Knowledge

### SOPs

- _None_

### Skills

- _None_

### Sources

- [source-cache-angella-control-plane-runs-angella-verification-setup-check-success-20260406-1000-summary-json.md](../sources/source-cache-angella-control-plane-runs-angella-verification-setup-check-success-20260406-1000-summary-json.md)
- [source-cache-angella-control-plane-runs-angella-verification-setup-check-success-20260406-1000-report-md.md](../sources/source-cache-angella-control-plane-runs-angella-verification-setup-check-success-20260406-1000-report-md.md)
- [source-cache-angella-control-plane-runs-angella-verification-setup-check-error-20260406-0950-summary-json.md](../sources/source-cache-angella-control-plane-runs-angella-verification-setup-check-error-20260406-0950-summary-json.md)
- [source-cache-angella-control-plane-runs-angella-verification-setup-check-error-20260406-0950-report-md.md](../sources/source-cache-angella-control-plane-runs-angella-verification-setup-check-error-20260406-0950-report-md.md)

## Recent Accepted Runs

- _None_

## Recent Verification-Only Runs

- `angella-verification-setup-check-success-20260406-1000` metric=`build_time` summary=Verification-only run: setup check passed successfully with build_time 0.6066s. All binary acceptance checks (exit 0 and template rendering) were satisfied.
- `angella-verification-setup-check-error-20260406-0950` metric=`build_time` summary=Benchmark failed with TypeError: 'type' and 'NoneType' in scripts/harness_catalog.py. This is a Python syntax/version issue (PEP 604) and the file is not in the allowed fix surface.

## Current Open Failures

- _None_
