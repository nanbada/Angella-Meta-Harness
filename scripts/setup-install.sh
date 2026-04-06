#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
export ANGELLA_ROOT="$ROOT_DIR"

# shellcheck source=./setup-common.sh
source "$ROOT_DIR/scripts/setup-common.sh"

resolve_env_mlx_path

if [ "$CHECK_ONLY" = true ]; then
    detect_python_runtime
    check_python_requirements_support
    check_templates_only
    report_harness_credential_status
    exit 0
fi

load_python_for_install_stage

if [ -n "$HARNESS_PROFILE" ] || [ -n "$LEAD_MODEL_OVERRIDE" ] || [ -n "$PLANNER_MODEL_OVERRIDE" ] || [ -n "$WORKER_MODEL_OVERRIDE" ]; then
    resolve_harness_selection
    write_bootstrap_state
fi

info "Loading MLX environment variables..."
# shellcheck source=/dev/null
source "$ENV_MLX_PATH"
ok "Environment variables loaded"

render_apfel_custom_provider
install_templates

mkdir -p "$SCRIPT_DIR/logs/Goose Logs"
ok "Log directory created: $SCRIPT_DIR/logs/Goose Logs/"

create_control_plane_layout
write_bootstrap_state
write_install_state_summary
write_harness_resolution_snapshot
report_harness_credential_status
