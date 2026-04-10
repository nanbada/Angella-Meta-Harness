# Angella Meta-Learning: Lessons Learned
Last distilled: 2026-04-10T05:30:00.000Z

> This file is automatically evolved by the Archivist Loop based on historical run logs.

### [2026-04-10] failure | CI/CD Hardening | sync-regex-corruption
- component: [setup-check](components/setup-check.md)
- summary: Resolved 12 consecutive CI failures caused by a loose regex in `scripts/sync_project_vars.py`.
- **Root Cause**: The regex for shell exports stripped variable names, leaving only values (e.g., `export value` instead of `export VAR=value`). This broke `setup --check` in clean environments.
- **Remedy**: 
    1. Fixed regex with strict boundaries and groups.
    2. Implemented `Dockerfile.test` for local Ubuntu 24.04 replication.
    3. Integrated `sync_project_vars.py` into `.githooks/pre-commit` to prevent documentation/template drift.
    4. Enabled `set -x` and comprehensive diagnostic dumps in `scripts/test_setup_flows.sh`.

### [2026-04-05] accepted | recipe-runtime | angella-real-recipe-runtime-20260405-220929
...
