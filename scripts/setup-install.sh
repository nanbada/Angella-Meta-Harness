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
    report_google_api_key_status
    exit 0
fi

load_python_for_install_stage

info "Loading MLX environment variables..."
# shellcheck source=/dev/null
source "$ENV_MLX_PATH"
ok "Environment variables loaded"

install_templates

mkdir -p "$SCRIPT_DIR/logs/Goose Logs"
ok "Log directory created: $SCRIPT_DIR/logs/Goose Logs/"

report_google_api_key_status
