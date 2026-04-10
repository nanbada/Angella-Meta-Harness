#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
export ANGELLA_ROOT="$ROOT_DIR"

# shellcheck source=./setup-common.sh
source "$ROOT_DIR/scripts/setup-common.sh"

if [ "$CHECK_ONLY" = true ]; then
    detect_python_runtime
    load_mlx_environment false
    check_python_requirements_support
    report_harness_credential_status
    exit 0
fi

load_python_for_install_stage
load_mlx_environment true

if [ -n "$HARNESS_PROFILE" ] || [ -n "$LEAD_MODEL_OVERRIDE" ] || [ -n "$PLANNER_MODEL_OVERRIDE" ] || [ -n "$WORKER_MODEL_OVERRIDE" ]; then
    resolve_harness_selection
    write_bootstrap_state
fi

mkdir -p "$SCRIPT_DIR/knowledge"
ok "Knowledge directory verified: $SCRIPT_DIR/knowledge/"

create_control_plane_layout
write_bootstrap_state
write_install_state_summary
write_harness_resolution_snapshot
report_harness_credential_status
