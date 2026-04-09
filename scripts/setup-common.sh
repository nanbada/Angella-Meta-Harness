#!/usr/bin/env bash

set -euo pipefail

if [ -z "${ANGELLA_ROOT:-}" ]; then
    ANGELLA_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi

SCRIPT_DIR="$ANGELLA_ROOT"
GOOSE_CONFIG_DIR="${HOME}/.config/goose"
GOOSE_RECIPE_DIR="${GOOSE_CONFIG_DIR}/recipes"
RENDERED_CONFIG_PATH="${GOOSE_CONFIG_DIR}/config.yaml"
RENDERED_RECIPE_PATH="${GOOSE_RECIPE_DIR}/autoresearch-loop.yaml"
RENDERED_SUB_RECIPE_DIR="${GOOSE_RECIPE_DIR}/sub"

ANGELLA_CACHE_DIR="${ANGELLA_CACHE_DIR:-${SCRIPT_DIR}/.cache/angella}"
ANGELLA_BOOTSTRAP_VENV_DIR="${ANGELLA_BOOTSTRAP_VENV_DIR:-${ANGELLA_CACHE_DIR}/bootstrap-venv}"
ANGELLA_BOOTSTRAP_STATE_PATH="${ANGELLA_BOOTSTRAP_STATE_PATH:-${ANGELLA_CACHE_DIR}/bootstrap.env}"
ANGELLA_PIP_CACHE_DIR="${ANGELLA_PIP_CACHE_DIR:-${ANGELLA_CACHE_DIR}/pip}"
ANGELLA_UV_CACHE_DIR="${ANGELLA_UV_CACHE_DIR:-${ANGELLA_CACHE_DIR}/uv}"
ANGELLA_WHEELHOUSE_DIR="${ANGELLA_WHEELHOUSE_DIR:-${SCRIPT_DIR}/vendor/wheels}"
ANGELLA_CONTROL_PLANE_DIR="${ANGELLA_CONTROL_PLANE_DIR:-${ANGELLA_CACHE_DIR}/control-plane}"
ANGELLA_CONTROL_RUNS_DIR="${ANGELLA_CONTROL_RUNS_DIR:-${ANGELLA_CONTROL_PLANE_DIR}/runs}"
ANGELLA_CONTROL_FAILURES_OPEN_DIR="${ANGELLA_CONTROL_FAILURES_OPEN_DIR:-${ANGELLA_CONTROL_PLANE_DIR}/failures/open}"
ANGELLA_CONTROL_FAILURES_CLOSED_DIR="${ANGELLA_CONTROL_FAILURES_CLOSED_DIR:-${ANGELLA_CONTROL_PLANE_DIR}/failures/closed}"
ANGELLA_CONTROL_KNOWLEDGE_SOPS_DIR="${ANGELLA_CONTROL_KNOWLEDGE_SOPS_DIR:-${ANGELLA_CONTROL_PLANE_DIR}/knowledge/sops}"
ANGELLA_CONTROL_KNOWLEDGE_SKILLS_DIR="${ANGELLA_CONTROL_KNOWLEDGE_SKILLS_DIR:-${ANGELLA_CONTROL_PLANE_DIR}/knowledge/skills}"
ANGELLA_CONTROL_META_LOOP_DIR="${ANGELLA_CONTROL_META_LOOP_DIR:-${ANGELLA_CONTROL_PLANE_DIR}/queue/meta-loop}"
ANGELLA_CONTROL_INSTALL_DIR="${ANGELLA_CONTROL_INSTALL_DIR:-${ANGELLA_CONTROL_PLANE_DIR}/install}"
ANGELLA_CONTROL_INSTALL_SUMMARY_PATH="${ANGELLA_CONTROL_INSTALL_SUMMARY_PATH:-${ANGELLA_CONTROL_INSTALL_DIR}/summary.json}"
ANGELLA_CONTROL_INSTALL_TELEMETRY_PATH="${ANGELLA_CONTROL_INSTALL_TELEMETRY_PATH:-${ANGELLA_CONTROL_INSTALL_DIR}/telemetry.jsonl}"
ANGELLA_CUSTOM_PROVIDER_DIR="${ANGELLA_CUSTOM_PROVIDER_DIR:-${GOOSE_CONFIG_DIR}/custom_providers}"
ANGELLA_HARNESS_MODELS_PATH="${ANGELLA_HARNESS_MODELS_PATH:-${SCRIPT_DIR}/config/harness-models.yaml}"
ANGELLA_HARNESS_PROFILES_PATH="${ANGELLA_HARNESS_PROFILES_PATH:-${SCRIPT_DIR}/config/harness-profiles.yaml}"

CHECK_RENDER_DIR="${CHECK_RENDER_DIR:-}"
OLLAMA_TAGS_JSON="${OLLAMA_TAGS_JSON:-}"
AUTO_YES="${AUTO_YES:-false}"
CHECK_ONLY="${CHECK_ONLY:-false}"
BOOTSTRAP_ONLY="${BOOTSTRAP_ONLY:-false}"
INSTALL_ONLY="${INSTALL_ONLY:-false}"
LIST_MODELS="${LIST_MODELS:-false}"
LIST_HARNESS_PROFILES="${LIST_HARNESS_PROFILES:-false}"
PYTHON_PIP_AVAILABLE="${PYTHON_PIP_AVAILABLE:-false}"
ENV_MLX_PATH="${ENV_MLX_PATH:-}"
PYTHON_CMD="${PYTHON_CMD:-}"
HARNESS_PROFILE="${HARNESS_PROFILE:-}"
LEAD_MODEL_OVERRIDE="${LEAD_MODEL_OVERRIDE:-}"
PLANNER_MODEL_OVERRIDE="${PLANNER_MODEL_OVERRIDE:-}"
WORKER_MODEL_OVERRIDE="${WORKER_MODEL_OVERRIDE:-}"
ANGELLA_LOCAL_WORKER_BACKEND="${ANGELLA_LOCAL_WORKER_BACKEND:-}"
ANGELLA_MLX_BASE_URL="${ANGELLA_MLX_BASE_URL:-}"
ANGELLA_MLX_MODEL="${ANGELLA_MLX_MODEL:-}"
ANGELLA_HARNESS_PROFILE_ID="${ANGELLA_HARNESS_PROFILE_ID:-}"
ANGELLA_LEAD_MODEL_ID="${ANGELLA_LEAD_MODEL_ID:-}"
ANGELLA_PLANNER_MODEL_ID="${ANGELLA_PLANNER_MODEL_ID:-}"
ANGELLA_WORKER_MODEL_ID="${ANGELLA_WORKER_MODEL_ID:-}"
ANGELLA_LEAD_PROVIDER="${ANGELLA_LEAD_PROVIDER:-}"
ANGELLA_LEAD_MODEL="${ANGELLA_LEAD_MODEL:-}"
ANGELLA_LEAD_CONTEXT_LIMIT="${ANGELLA_LEAD_CONTEXT_LIMIT:-}"
ANGELLA_LEAD_TEMPERATURE="${ANGELLA_LEAD_TEMPERATURE:-}"
ANGELLA_PLANNER_PROVIDER="${ANGELLA_PLANNER_PROVIDER:-}"
ANGELLA_PLANNER_MODEL="${ANGELLA_PLANNER_MODEL:-}"
ANGELLA_PLANNER_CONTEXT_LIMIT="${ANGELLA_PLANNER_CONTEXT_LIMIT:-}"
ANGELLA_PLANNER_TEMPERATURE="${ANGELLA_PLANNER_TEMPERATURE:-}"
ANGELLA_WORKER_PROVIDER="${ANGELLA_WORKER_PROVIDER:-}"
ANGELLA_WORKER_MODEL="${ANGELLA_WORKER_MODEL:-}"
ANGELLA_WORKER_CONTEXT_LIMIT="${ANGELLA_WORKER_CONTEXT_LIMIT:-}"
ANGELLA_WORKER_TEMPERATURE="${ANGELLA_WORKER_TEMPERATURE:-}"
ANGELLA_MLX_ENABLED="${ANGELLA_MLX_ENABLED:-false}"
ANGELLA_MLX_PREVIEW_ENABLED="${ANGELLA_MLX_PREVIEW_ENABLED:-false}"
ANGELLA_NVFP4_ENABLED="${ANGELLA_NVFP4_ENABLED:-false}"
ANGELLA_APFEL_ENABLED="${ANGELLA_APFEL_ENABLED:-false}"
ANGELLA_EXECUTION_MODE="${ANGELLA_EXECUTION_MODE:-}"
ANGELLA_WORKER_TIER="${ANGELLA_WORKER_TIER:-}"
ANGELLA_FALLBACK_REASON="${ANGELLA_FALLBACK_REASON:-}"
ANGELLA_FRONTIER_REACHABLE="${ANGELLA_FRONTIER_REACHABLE:-true}"
ANGELLA_LOCAL_CACHE_ENABLED="${ANGELLA_LOCAL_CACHE_ENABLED:-false}"
ANGELLA_TOKEN_SAVER_ENABLED="${ANGELLA_TOKEN_SAVER_ENABLED:-false}"
ANGELLA_NON_GOALS_JSON="${ANGELLA_NON_GOALS_JSON:-[]}"
ANGELLA_MLX_POLICY_JSON="${ANGELLA_MLX_POLICY_JSON:-{}}"
ANGELLA_INSTALL_RENDERED_HASHES_JSON="${ANGELLA_INSTALL_RENDERED_HASHES_JSON:-{}}"
ANGELLA_INSTALL_PREEXISTING_HASHES_JSON="${ANGELLA_INSTALL_PREEXISTING_HASHES_JSON:-{}}"
ANGELLA_INSTALL_APPLIED_HASHES_JSON="${ANGELLA_INSTALL_APPLIED_HASHES_JSON:-{}}"
ANGELLA_INSTALL_DRIFT_DETECTED="${ANGELLA_INSTALL_DRIFT_DETECTED:-false}"
ANGELLA_INSTALL_DRIFT_TARGETS_JSON="${ANGELLA_INSTALL_DRIFT_TARGETS_JSON:-[]}"
ANGELLA_INSTALL_OVERWRITE_MODE="${ANGELLA_INSTALL_OVERWRITE_MODE:-not_run}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC} $1"; }
ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
fail()  { echo -e "${RED}[FAIL]${NC} $1"; }

cleanup_check_render_dir() {
    if [ -n "${CHECK_RENDER_DIR:-}" ] && [ -d "${CHECK_RENDER_DIR:-}" ]; then
        rm -rf "$CHECK_RENDER_DIR"
    fi
}

prompt_yes_no() {
    local prompt=$1
    local default_choice=$2
    local suffix response

    if [ "$default_choice" = "yes" ]; then
        suffix="[Y/n]"
    else
        suffix="[y/N]"
    fi

    if [ "$AUTO_YES" = true ]; then
        info "$prompt $suffix -> $default_choice"
        [ "$default_choice" = "yes" ]
        return
    fi

    while true; do
        read -r -p "$prompt $suffix " response
        case "$response" in
            "")
                [ "$default_choice" = "yes" ]
                return
                ;;
            y|Y|yes|YES)
                return 0
                ;;
            n|N|no|NO)
                return 1
                ;;
            *)
                warn "Please answer y or n."
                ;;
        esac
    done
}

json_array_from_args() {
    "$PYTHON_CMD" - "$@" <<'PY'
import json
import sys

print(json.dumps(sys.argv[1:], ensure_ascii=False))
PY
}

hash_dict_json() {
    "$PYTHON_CMD" - "$@" <<'PY'
import hashlib
import json
import pathlib
import sys

args = sys.argv[1:]
payload = {}
for index in range(0, len(args), 2):
    key = args[index]
    path = pathlib.Path(args[index + 1])
    if path.exists():
        payload[key] = hashlib.sha256(path.read_bytes()).hexdigest()
    else:
        payload[key] = ""
print(json.dumps(payload, ensure_ascii=False))
PY
}

sha256_file() {
    local path=$1

    if [ ! -f "$path" ]; then
        echo ""
        return 0
    fi

    "$PYTHON_CMD" - "$path" <<'PY'
import hashlib
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
print(hashlib.sha256(path.read_bytes()).hexdigest())
PY
}

detect_python() {
    if command -v python3 >/dev/null 2>&1; then
        echo "python3"
        return
    fi

    if command -v python >/dev/null 2>&1; then
        echo "python"
        return
    fi

    return 1
}

resolve_env_mlx_path() {
    if [ -f "$SCRIPT_DIR/.env.mlx" ]; then
        ENV_MLX_PATH="$SCRIPT_DIR/.env.mlx"
        return
    fi

    ENV_MLX_PATH="$SCRIPT_DIR/.env.mlx.example"
}

normalize_local_worker_env() {
    if [ -z "${ANGELLA_LOCAL_WORKER_BACKEND:-}" ]; then
        ANGELLA_LOCAL_WORKER_BACKEND="ollama"
    fi

    export ANGELLA_LOCAL_WORKER_BACKEND
}

load_mlx_environment() {
    local verbose="${1:-false}"

    resolve_env_mlx_path
    if [ "$verbose" = true ]; then
        info "Loading MLX environment variables from $(basename "$ENV_MLX_PATH")..."
    fi
    # shellcheck source=/dev/null
    source "$ENV_MLX_PATH"
    normalize_local_worker_env
    if [ "$verbose" = true ]; then
        ok "Environment variables loaded"
    fi
}

escape_sed_replacement() {
    local escaped=${1//\\/\\\\}
    escaped=${escaped//&/\\&}
    escaped=${escaped//|/\\|}
    printf '%s' "$escaped"
}

write_shell_var() {
    local name=$1
    local value=$2
    printf "%s=%q\n" "$name" "$value"
}

render_template() {
    local template_path=$1
    local output_path=$2
    local escaped_root
    local escaped_python
    local escaped_recipe_path
    local escaped_goose_provider
    local escaped_goose_model
    local escaped_goose_temperature
    local escaped_goose_lead_provider
    local escaped_goose_lead_model
    local escaped_goose_planner_provider
    local escaped_goose_planner_model
    local escaped_goose_input_limit
    local escaped_harness_profile

    escaped_root="$(escape_sed_replacement "$SCRIPT_DIR")"
    escaped_python="$(escape_sed_replacement "$PYTHON_CMD")"
    escaped_recipe_path="$(escape_sed_replacement "$RENDERED_RECIPE_PATH")"
    escaped_goose_provider="$(escape_sed_replacement "${ANGELLA_WORKER_PROVIDER:-openai}")"
    escaped_goose_model="$(escape_sed_replacement "${ANGELLA_WORKER_MODEL:-gpt-5.2}")"
    escaped_goose_temperature="$(escape_sed_replacement "${ANGELLA_WORKER_TEMPERATURE:-0.3}")"
    escaped_goose_lead_provider="$(escape_sed_replacement "${ANGELLA_LEAD_PROVIDER:-openai}")"
    escaped_goose_lead_model="$(escape_sed_replacement "${ANGELLA_LEAD_MODEL:-gpt-5.2-pro}")"
    escaped_goose_planner_provider="$(escape_sed_replacement "${ANGELLA_PLANNER_PROVIDER:-${ANGELLA_LEAD_PROVIDER:-openai}}")"
    escaped_goose_planner_model="$(escape_sed_replacement "${ANGELLA_PLANNER_MODEL:-${ANGELLA_LEAD_MODEL:-gpt-5.2-pro}}")"
    escaped_goose_input_limit="$(escape_sed_replacement "${ANGELLA_WORKER_CONTEXT_LIMIT:-400000}")"
    escaped_harness_profile="$(escape_sed_replacement "${ANGELLA_HARNESS_PROFILE_ID:-frontier_default}")"

    mkdir -p "$(dirname "$output_path")"
    sed \
        -e "s|__ANGELLA_ROOT__|$escaped_root|g" \
        -e "s|__PYTHON_CMD__|$escaped_python|g" \
        -e "s|__RENDERED_RECIPE_PATH__|$escaped_recipe_path|g" \
        -e "s|__GOOSE_PROVIDER__|$escaped_goose_provider|g" \
        -e "s|__GOOSE_MODEL__|$escaped_goose_model|g" \
        -e "s|__GOOSE_TEMPERATURE__|$escaped_goose_temperature|g" \
        -e "s|__GOOSE_LEAD_PROVIDER__|$escaped_goose_lead_provider|g" \
        -e "s|__GOOSE_LEAD_MODEL__|$escaped_goose_lead_model|g" \
        -e "s|__GOOSE_PLANNER_PROVIDER__|$escaped_goose_planner_provider|g" \
        -e "s|__GOOSE_PLANNER_MODEL__|$escaped_goose_planner_model|g" \
        -e "s|__GOOSE_INPUT_LIMIT__|$escaped_goose_input_limit|g" \
        -e "s|__ANGELLA_HARNESS_PROFILE_ID__|$escaped_harness_profile|g" \
        -e "s|__ANGELLA_EXECUTION_MODE__|$(escape_sed_replacement "${ANGELLA_EXECUTION_MODE:-frontier_primary}")|g" \
        -e "s|__ANGELLA_WORKER_TIER__|$(escape_sed_replacement "${ANGELLA_WORKER_TIER:-frontier_primary}")|g" \
        -e "s|__ANGELLA_FRONTIER_REACHABLE__|$(escape_sed_replacement "${ANGELLA_FRONTIER_REACHABLE:-true}")|g" \
        -e "s|__ANGELLA_LOCAL_CACHE_ENABLED__|$(escape_sed_replacement "${ANGELLA_LOCAL_CACHE_ENABLED:-false}")|g" \
        -e "s|__ANGELLA_TOKEN_SAVER_ENABLED__|$(escape_sed_replacement "${ANGELLA_TOKEN_SAVER_ENABLED:-false}")|g" \
        "$template_path" > "$output_path"
}

verify_rendered_template() {
    local rendered_path=$1

    if grep -Eq '__ANGELLA_ROOT__|__PYTHON_CMD__|__RENDERED_RECIPE_PATH__' "$rendered_path"; then
        fail "Unresolved template placeholder found in $rendered_path"
        return 1
    fi

    return 0
}

verify_template_source_portable() {
    local template_path=$1

    if grep -Fq '/Users/nanbada/projects/Angella' "$template_path"; then
        fail "Developer-specific absolute path is hardcoded in template source: $template_path"
        return 1
    fi

    return 0
}

render_and_verify() {
    local template_path=$1
    local output_path=$2
    render_template "$template_path" "$output_path"
    verify_rendered_template "$output_path"
}

list_harness_models() {
    "$PYTHON_CMD" "$SCRIPT_DIR/scripts/harness_catalog.py" list-models
}

list_harness_profiles() {
    "$PYTHON_CMD" "$SCRIPT_DIR/scripts/harness_catalog.py" list-profiles
}

resolve_harness_selection() {
    local output
    local args=("$PYTHON_CMD" "$SCRIPT_DIR/scripts/harness_catalog.py" "resolve" "--format" "shell")

    if [ -n "$HARNESS_PROFILE" ]; then
        args+=("--profile" "$HARNESS_PROFILE")
    fi
    if [ -n "$LEAD_MODEL_OVERRIDE" ]; then
        args+=("--lead-model" "$LEAD_MODEL_OVERRIDE")
    fi
    if [ -n "$PLANNER_MODEL_OVERRIDE" ]; then
        args+=("--planner-model" "$PLANNER_MODEL_OVERRIDE")
    fi
    if [ -n "$WORKER_MODEL_OVERRIDE" ]; then
        args+=("--worker-model" "$WORKER_MODEL_OVERRIDE")
    fi

    output="$("${args[@]}")"

    # shellcheck disable=SC1090
    eval "$output"
}

create_control_plane_layout() {
    mkdir -p \
        "$ANGELLA_CONTROL_RUNS_DIR" \
        "$ANGELLA_CONTROL_FAILURES_OPEN_DIR" \
        "$ANGELLA_CONTROL_FAILURES_CLOSED_DIR" \
        "$ANGELLA_CONTROL_KNOWLEDGE_SOPS_DIR" \
        "$ANGELLA_CONTROL_KNOWLEDGE_SKILLS_DIR" \
        "$ANGELLA_CONTROL_META_LOOP_DIR" \
        "$ANGELLA_CONTROL_INSTALL_DIR"
}

write_harness_resolution_snapshot() {
    local snapshot_path="${ANGELLA_CONTROL_PLANE_DIR}/current-selection.json"

    create_control_plane_layout

    cat >"$snapshot_path" <<EOF
{
  "profile_id": $(printf '%s' "$ANGELLA_HARNESS_PROFILE_ID" | "$PYTHON_CMD" -c 'import json,sys; print(json.dumps(sys.stdin.read()))'),
  "lead_model_id": $(printf '%s' "$ANGELLA_LEAD_MODEL_ID" | "$PYTHON_CMD" -c 'import json,sys; print(json.dumps(sys.stdin.read()))'),
  "planner_model_id": $(printf '%s' "$ANGELLA_PLANNER_MODEL_ID" | "$PYTHON_CMD" -c 'import json,sys; print(json.dumps(sys.stdin.read()))'),
  "worker_model_id": $(printf '%s' "$ANGELLA_WORKER_MODEL_ID" | "$PYTHON_CMD" -c 'import json,sys; print(json.dumps(sys.stdin.read()))'),
  "lead_provider": $(printf '%s' "$ANGELLA_LEAD_PROVIDER" | "$PYTHON_CMD" -c 'import json,sys; print(json.dumps(sys.stdin.read()))'),
  "lead_model": $(printf '%s' "$ANGELLA_LEAD_MODEL" | "$PYTHON_CMD" -c 'import json,sys; print(json.dumps(sys.stdin.read()))'),
  "planner_provider": $(printf '%s' "$ANGELLA_PLANNER_PROVIDER" | "$PYTHON_CMD" -c 'import json,sys; print(json.dumps(sys.stdin.read()))'),
  "planner_model": $(printf '%s' "$ANGELLA_PLANNER_MODEL" | "$PYTHON_CMD" -c 'import json,sys; print(json.dumps(sys.stdin.read()))'),
  "worker_provider": $(printf '%s' "$ANGELLA_WORKER_PROVIDER" | "$PYTHON_CMD" -c 'import json,sys; print(json.dumps(sys.stdin.read()))'),
  "worker_model": $(printf '%s' "$ANGELLA_WORKER_MODEL" | "$PYTHON_CMD" -c 'import json,sys; print(json.dumps(sys.stdin.read()))'),
  "worker_context_limit": $(printf '%s' "$ANGELLA_WORKER_CONTEXT_LIMIT"),
  "worker_temperature": $(printf '%s' "$ANGELLA_WORKER_TEMPERATURE"),
  "local_worker_backend": $(printf '%s' "$ANGELLA_LOCAL_WORKER_BACKEND" | "$PYTHON_CMD" -c 'import json,sys; print(json.dumps(sys.stdin.read()))'),
  "mlx_base_url": $(printf '%s' "$ANGELLA_MLX_BASE_URL" | "$PYTHON_CMD" -c 'import json,sys; print(json.dumps(sys.stdin.read()))'),
  "mlx_model": $(printf '%s' "$ANGELLA_MLX_MODEL" | "$PYTHON_CMD" -c 'import json,sys; print(json.dumps(sys.stdin.read()))'),
  "mlx_enabled": $(printf '%s' "$ANGELLA_MLX_ENABLED"),
  "mlx_preview_enabled": $(printf '%s' "$ANGELLA_MLX_PREVIEW_ENABLED"),
  "nvfp4_enabled": $(printf '%s' "$ANGELLA_NVFP4_ENABLED"),
  "apfel_enabled": $(printf '%s' "$ANGELLA_APFEL_ENABLED"),
  "execution_mode": $(printf '%s' "$ANGELLA_EXECUTION_MODE" | "$PYTHON_CMD" -c 'import json,sys; print(json.dumps(sys.stdin.read()))'),
  "worker_tier": $(printf '%s' "$ANGELLA_WORKER_TIER" | "$PYTHON_CMD" -c 'import json,sys; print(json.dumps(sys.stdin.read()))'),
  "fallback_reason": $(printf '%s' "$ANGELLA_FALLBACK_REASON" | "$PYTHON_CMD" -c 'import json,sys; print(json.dumps(sys.stdin.read()))'),
  "frontier_reachable": $(printf '%s' "$ANGELLA_FRONTIER_REACHABLE"),
  "local_cache_enabled": $(printf '%s' "$ANGELLA_LOCAL_CACHE_ENABLED"),
  "token_saver_enabled": $(printf '%s' "$ANGELLA_TOKEN_SAVER_ENABLED"),
  "non_goals": ${ANGELLA_NON_GOALS_JSON},
  "mlx_policy": ${ANGELLA_MLX_POLICY_JSON}
}
EOF
}

write_install_state_summary() {
    local timestamp

    create_control_plane_layout
    timestamp="$(date '+%Y%m%d-%H%M%S')"
    ANGELLA_HARNESS_PROFILE_ID="$ANGELLA_HARNESS_PROFILE_ID" \
    ANGELLA_LEAD_MODEL_ID="$ANGELLA_LEAD_MODEL_ID" \
    ANGELLA_PLANNER_MODEL_ID="$ANGELLA_PLANNER_MODEL_ID" \
    ANGELLA_WORKER_MODEL_ID="$ANGELLA_WORKER_MODEL_ID" \
    ANGELLA_INSTALL_SUMMARY_TIMESTAMP="$timestamp" \
    ANGELLA_INSTALL_RENDERED_HASHES_JSON="$ANGELLA_INSTALL_RENDERED_HASHES_JSON" \
    ANGELLA_INSTALL_PREEXISTING_HASHES_JSON="$ANGELLA_INSTALL_PREEXISTING_HASHES_JSON" \
    ANGELLA_INSTALL_APPLIED_HASHES_JSON="$ANGELLA_INSTALL_APPLIED_HASHES_JSON" \
    ANGELLA_INSTALL_DRIFT_TARGETS_JSON="$ANGELLA_INSTALL_DRIFT_TARGETS_JSON" \
    ANGELLA_INSTALL_DRIFT_DETECTED="$ANGELLA_INSTALL_DRIFT_DETECTED" \
    ANGELLA_INSTALL_OVERWRITE_MODE="$ANGELLA_INSTALL_OVERWRITE_MODE" \
    "$PYTHON_CMD" - \
        "$ANGELLA_CONTROL_INSTALL_SUMMARY_PATH" \
        "$ANGELLA_CONTROL_INSTALL_TELEMETRY_PATH" \
        "$RENDERED_CONFIG_PATH" \
        "$RENDERED_RECIPE_PATH" \
        "$RENDERED_SUB_RECIPE_DIR/code-optimize.yaml" \
        "$RENDERED_SUB_RECIPE_DIR/evaluate-metric.yaml" <<'PY'
import datetime as dt
import json
import os
import pathlib
import sys

summary_path = pathlib.Path(sys.argv[1])
telemetry_path = pathlib.Path(sys.argv[2])
config_path, autoresearch_path, code_path, eval_path = sys.argv[3:7]

def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)

def env_json(name: str, default):
    raw = env(name)
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default

timestamp = env("ANGELLA_INSTALL_SUMMARY_TIMESTAMP") or dt.datetime.now().strftime("%Y%m%d-%H%M%S")
summary_payload = {
    "event_type": "setup_install",
    "timestamp": timestamp,
    "profile_id": env("ANGELLA_HARNESS_PROFILE_ID"),
    "selected_model_ids": {
        "lead": env("ANGELLA_LEAD_MODEL_ID"),
        "planner": env("ANGELLA_PLANNER_MODEL_ID"),
        "worker": env("ANGELLA_WORKER_MODEL_ID"),
    },
    "routing": {
        "execution_mode": env("ANGELLA_EXECUTION_MODE"),
        "worker_tier": env("ANGELLA_WORKER_TIER"),
        "fallback_reason": env("ANGELLA_FALLBACK_REASON"),
        "frontier_reachable": env("ANGELLA_FRONTIER_REACHABLE", "true").lower() == "true",
        "local_cache_enabled": env("ANGELLA_LOCAL_CACHE_ENABLED", "false").lower() == "true",
        "token_saver_enabled": env("ANGELLA_TOKEN_SAVER_ENABLED", "false").lower() == "true",
    },
    "rendered_hashes": env_json("ANGELLA_INSTALL_RENDERED_HASHES_JSON", {}),
    "preexisting_target_hashes": env_json("ANGELLA_INSTALL_PREEXISTING_HASHES_JSON", {}),
    "applied_target_hashes": env_json("ANGELLA_INSTALL_APPLIED_HASHES_JSON", {}),
    "drift_detected": env("ANGELLA_INSTALL_DRIFT_DETECTED", "false").lower() == "true",
    "drift_targets": env_json("ANGELLA_INSTALL_DRIFT_TARGETS_JSON", []),
    "overwrite_mode": env("ANGELLA_INSTALL_OVERWRITE_MODE", "not_run"),
    "paths": {
        "config": config_path,
        "autoresearch_loop": autoresearch_path,
        "code_optimize": code_path,
        "evaluate_metric": eval_path,
    },
}
summary_path.parent.mkdir(parents=True, exist_ok=True)
summary_path.write_text(json.dumps(summary_payload, indent=2, ensure_ascii=False), encoding="utf-8")
with telemetry_path.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(summary_payload, ensure_ascii=False) + "\n")
PY
}

bootstrap_state_exists() {
    [ -f "$ANGELLA_BOOTSTRAP_STATE_PATH" ]
}

write_bootstrap_state() {
    mkdir -p "$(dirname "$ANGELLA_BOOTSTRAP_STATE_PATH")"
    {
        write_shell_var "PYTHON_CMD" "$PYTHON_CMD"
        write_shell_var "ANGELLA_HARNESS_PROFILE_ID" "$ANGELLA_HARNESS_PROFILE_ID"
        write_shell_var "ANGELLA_LEAD_MODEL_ID" "$ANGELLA_LEAD_MODEL_ID"
        write_shell_var "ANGELLA_PLANNER_MODEL_ID" "$ANGELLA_PLANNER_MODEL_ID"
        write_shell_var "ANGELLA_WORKER_MODEL_ID" "$ANGELLA_WORKER_MODEL_ID"
        write_shell_var "ANGELLA_LEAD_PROVIDER" "$ANGELLA_LEAD_PROVIDER"
        write_shell_var "ANGELLA_LEAD_MODEL" "$ANGELLA_LEAD_MODEL"
        write_shell_var "ANGELLA_LEAD_CONTEXT_LIMIT" "$ANGELLA_LEAD_CONTEXT_LIMIT"
        write_shell_var "ANGELLA_LEAD_TEMPERATURE" "$ANGELLA_LEAD_TEMPERATURE"
        write_shell_var "ANGELLA_PLANNER_PROVIDER" "$ANGELLA_PLANNER_PROVIDER"
        write_shell_var "ANGELLA_PLANNER_MODEL" "$ANGELLA_PLANNER_MODEL"
        write_shell_var "ANGELLA_PLANNER_CONTEXT_LIMIT" "$ANGELLA_PLANNER_CONTEXT_LIMIT"
        write_shell_var "ANGELLA_PLANNER_TEMPERATURE" "$ANGELLA_PLANNER_TEMPERATURE"
        write_shell_var "ANGELLA_WORKER_PROVIDER" "$ANGELLA_WORKER_PROVIDER"
        write_shell_var "ANGELLA_WORKER_MODEL" "$ANGELLA_WORKER_MODEL"
        write_shell_var "ANGELLA_WORKER_CONTEXT_LIMIT" "$ANGELLA_WORKER_CONTEXT_LIMIT"
        write_shell_var "ANGELLA_WORKER_TEMPERATURE" "$ANGELLA_WORKER_TEMPERATURE"
        write_shell_var "ANGELLA_LOCAL_WORKER_BACKEND" "$ANGELLA_LOCAL_WORKER_BACKEND"
        write_shell_var "ANGELLA_MLX_BASE_URL" "$ANGELLA_MLX_BASE_URL"
        write_shell_var "ANGELLA_MLX_MODEL" "$ANGELLA_MLX_MODEL"
        write_shell_var "ANGELLA_MLX_ENABLED" "$ANGELLA_MLX_ENABLED"
        write_shell_var "ANGELLA_MLX_PREVIEW_ENABLED" "$ANGELLA_MLX_PREVIEW_ENABLED"
        write_shell_var "ANGELLA_NVFP4_ENABLED" "$ANGELLA_NVFP4_ENABLED"
        write_shell_var "ANGELLA_APFEL_ENABLED" "$ANGELLA_APFEL_ENABLED"
        write_shell_var "ANGELLA_EXECUTION_MODE" "$ANGELLA_EXECUTION_MODE"
        write_shell_var "ANGELLA_WORKER_TIER" "$ANGELLA_WORKER_TIER"
        write_shell_var "ANGELLA_FALLBACK_REASON" "$ANGELLA_FALLBACK_REASON"
        write_shell_var "ANGELLA_FRONTIER_REACHABLE" "$ANGELLA_FRONTIER_REACHABLE"
        write_shell_var "ANGELLA_LOCAL_CACHE_ENABLED" "$ANGELLA_LOCAL_CACHE_ENABLED"
        write_shell_var "ANGELLA_TOKEN_SAVER_ENABLED" "$ANGELLA_TOKEN_SAVER_ENABLED"
        write_shell_var "ANGELLA_NON_GOALS_JSON" "$ANGELLA_NON_GOALS_JSON"
        write_shell_var "ANGELLA_MLX_POLICY_JSON" "$ANGELLA_MLX_POLICY_JSON"
        write_shell_var "ANGELLA_INSTALL_RENDERED_HASHES_JSON" "$ANGELLA_INSTALL_RENDERED_HASHES_JSON"
        write_shell_var "ANGELLA_INSTALL_PREEXISTING_HASHES_JSON" "$ANGELLA_INSTALL_PREEXISTING_HASHES_JSON"
        write_shell_var "ANGELLA_INSTALL_APPLIED_HASHES_JSON" "$ANGELLA_INSTALL_APPLIED_HASHES_JSON"
        write_shell_var "ANGELLA_INSTALL_DRIFT_DETECTED" "$ANGELLA_INSTALL_DRIFT_DETECTED"
        write_shell_var "ANGELLA_INSTALL_DRIFT_TARGETS_JSON" "$ANGELLA_INSTALL_DRIFT_TARGETS_JSON"
        write_shell_var "ANGELLA_INSTALL_OVERWRITE_MODE" "$ANGELLA_INSTALL_OVERWRITE_MODE"
    } >"$ANGELLA_BOOTSTRAP_STATE_PATH"
}

load_bootstrap_state() {
    local preserved_local_worker_backend="${ANGELLA_LOCAL_WORKER_BACKEND-__ANGELLA_UNSET__}"
    local preserved_mlx_base_url="${ANGELLA_MLX_BASE_URL-__ANGELLA_UNSET__}"
    local preserved_mlx_model="${ANGELLA_MLX_MODEL-__ANGELLA_UNSET__}"

    if ! bootstrap_state_exists; then
        return 1
    fi

    # shellcheck disable=SC1090
    source "$ANGELLA_BOOTSTRAP_STATE_PATH"
    if [ "$preserved_local_worker_backend" != "__ANGELLA_UNSET__" ]; then
        ANGELLA_LOCAL_WORKER_BACKEND="$preserved_local_worker_backend"
    fi
    if [ "$preserved_mlx_base_url" != "__ANGELLA_UNSET__" ]; then
        ANGELLA_MLX_BASE_URL="$preserved_mlx_base_url"
    fi
    if [ "$preserved_mlx_model" != "__ANGELLA_UNSET__" ]; then
        ANGELLA_MLX_MODEL="$preserved_mlx_model"
    fi
    export ANGELLA_LOCAL_WORKER_BACKEND ANGELLA_MLX_BASE_URL ANGELLA_MLX_MODEL
    [ -n "${PYTHON_CMD:-}" ] && [ -x "$(command -v "$PYTHON_CMD" 2>/dev/null || true)" ] && return 0
    [ -x "$PYTHON_CMD" ]
}

install_python_requirements() {
    local requirements_file=$1
    local required_packages=("mcp")
    local spec_probe='import importlib.util, sys;'
    local package_name
    local python_executable
    local pip_install_args=(-m pip install --disable-pip-version-check -r "$requirements_file")
    local uv_install_args=()

    if [ "$PYTHON_PIP_AVAILABLE" != true ] && ! "$PYTHON_CMD" -m pip --version >/dev/null 2>&1; then
        warn "pip is not available for $PYTHON_CMD. Install Python dependencies manually:"
        echo "  $PYTHON_CMD -m ensurepip --upgrade"
        echo "  $PYTHON_CMD -m pip install mcp"
        return 1
    fi

    for package_name in "${required_packages[@]}"; do
        spec_probe+="sys.exit(1) if importlib.util.find_spec(\"${package_name}\") is None else None;"
    done
    spec_probe+="sys.exit(0)"

    if "$PYTHON_CMD" -c "$spec_probe" >/dev/null 2>&1; then
        info "Python requirements already installed; skipping install."
        return 0
    fi

    mkdir -p "$ANGELLA_PIP_CACHE_DIR" "$ANGELLA_UV_CACHE_DIR"
    python_executable="$("$PYTHON_CMD" -c 'import sys; print(sys.executable)')"

    if command -v uv >/dev/null 2>&1; then
        uv_install_args=(pip install --python "$python_executable" -r "$requirements_file" --quiet)
        if [ -d "$ANGELLA_WHEELHOUSE_DIR" ] && find "$ANGELLA_WHEELHOUSE_DIR" -name '*.whl' -print -quit >/dev/null 2>&1; then
            uv_install_args+=(--find-links "$ANGELLA_WHEELHOUSE_DIR")
        fi

        if UV_CACHE_DIR="$ANGELLA_UV_CACHE_DIR" uv "${uv_install_args[@]}" 2>/dev/null; then
            return 0
        fi

        warn "uv pip install failed. Falling back to pip..."
    fi

    if [ -d "$ANGELLA_WHEELHOUSE_DIR" ] && find "$ANGELLA_WHEELHOUSE_DIR" -name '*.whl' -print -quit >/dev/null 2>&1; then
        export PIP_FIND_LINKS="$ANGELLA_WHEELHOUSE_DIR"
    fi
    export PIP_CACHE_DIR="$ANGELLA_PIP_CACHE_DIR"

    if "$PYTHON_CMD" "${pip_install_args[@]}" --quiet 2>/dev/null; then
        return 0
    fi

    warn "pip install failed. Trying with --user flag..."
    if "$PYTHON_CMD" "${pip_install_args[@]}" --user --quiet 2>/dev/null; then
        return 0
    fi

    warn "pip --user install failed. Trying with --break-system-packages..."
    if "$PYTHON_CMD" "${pip_install_args[@]}" --user --break-system-packages --quiet 2>/dev/null; then
        return 0
    fi

    fail "Could not install Python dependencies."
    echo "  Manual install: $PYTHON_CMD -m pip install --user --break-system-packages -r $requirements_file"
    return 1
}

ensure_bootstrap_environment() {
    local base_python=$1
    local bootstrap_python

    mkdir -p "$ANGELLA_CACHE_DIR"

    if [ ! -x "$ANGELLA_BOOTSTRAP_VENV_DIR/bin/python" ]; then
        info "Creating bootstrap environment at $ANGELLA_BOOTSTRAP_VENV_DIR"
        "$base_python" -m venv "$ANGELLA_BOOTSTRAP_VENV_DIR"
    fi

    bootstrap_python="$ANGELLA_BOOTSTRAP_VENV_DIR/bin/python"
    PYTHON_CMD="$bootstrap_python"
    PYTHON_PIP_AVAILABLE=false
    if "$PYTHON_CMD" -c "import pip" >/dev/null 2>&1; then
        PYTHON_PIP_AVAILABLE=true
    fi

    info "Bootstrapping Python environment..."
    install_python_requirements "$SCRIPT_DIR/mcp-servers/requirements.txt"
    write_bootstrap_state
}

check_homebrew() {
    info "Checking Homebrew..."
    if command -v brew >/dev/null 2>&1; then
        ok "Homebrew found"
    else
        fail "Homebrew not found. Install from https://brew.sh"
        exit 1
    fi
}

ensure_goose() {
    info "Checking Goose CLI..."
    if command -v goose >/dev/null 2>&1; then
        ok "Goose CLI found"
        return
    fi

    if [ "$CHECK_ONLY" = true ]; then
        warn "Goose CLI not found. setup.sh can install it via Homebrew during a non-check run."
        return
    fi

    warn "Goose CLI not found."
    echo ""
    echo "  Option 1: brew install block-goose-cli"
    echo "  Option 2: curl -fsSL https://github.com/block/goose/releases/download/stable/download_cli.sh | CONFIGURE=false bash"
    echo ""

    if prompt_yes_no "Install via Homebrew?" "yes"; then
        brew install block-goose-cli
        ok "Goose CLI installed"
    else
        warn "Skipping Goose CLI installation."
        warn "Please install Goose manually before running recipes."
    fi
}

check_ollama_binary() {
    info "Checking Ollama..."
    if command -v ollama >/dev/null 2>&1; then
        ok "Ollama found"
    else
        fail "Ollama not found. Install from https://ollama.com"
        exit 1
    fi
}

ollama_is_running() {
    OLLAMA_TAGS_JSON="$(curl -sS -m 2 -f http://localhost:11434/api/tags 2>/dev/null || true)"
    [ -n "$OLLAMA_TAGS_JSON" ]
}

ollama_has_model() {
    local model=$1

    if [ -z "$OLLAMA_TAGS_JSON" ] && ! ollama_is_running; then
        return 1
    fi

    [[ "$OLLAMA_TAGS_JSON" == *"\"name\":\"$model\""* ]]
}

ensure_ollama_server() {
    info "Checking Ollama server..."
    if ollama_is_running; then
        ok "Ollama server is running"
        return
    fi

    if [ "$CHECK_ONLY" = true ]; then
        warn "Ollama server is not running. setup.sh will offer to start it during a non-check run."
        return
    fi

    warn "Ollama server is not running."
    if prompt_yes_no "Start Ollama server now?" "yes"; then
        info "Starting Ollama server in background..."
        ollama serve >/dev/null 2>&1 &
        sleep 3
        if ollama_is_running; then
            ok "Ollama server started"
        else
            warn "Failed to start Ollama. Try 'ollama serve' manually."
        fi
    else
        warn "Ollama server not started. Run 'ollama serve' before using recipes."
    fi
}

pull_model() {
    local model=$1
    if ollama_has_model "$model"; then
        ok "Model '$model' already pulled"
    else
        info "Pulling '$model' (this may take a while)..."
        ollama pull "$model"
        ollama_is_running >/dev/null 2>&1 || true
        ok "Model '$model' pulled"
    fi
}

ensure_models() {
    info "Checking selected worker runtime..."

    if [ "$ANGELLA_WORKER_PROVIDER" = "ollama" ]; then
        if ! ollama_is_running; then
            warn "Ollama server is not running. Skipping model pull."
            echo "  Run manually later:"
            echo "    ollama pull $ANGELLA_WORKER_MODEL"
            return
        fi

        if [ "$CHECK_ONLY" = true ]; then
            if ollama_has_model "$ANGELLA_WORKER_MODEL"; then
                ok "Model '$ANGELLA_WORKER_MODEL' already pulled"
            else
                warn "Model '$ANGELLA_WORKER_MODEL' is not pulled yet."
            fi
            return
        fi

        pull_model "$ANGELLA_WORKER_MODEL"
    elif [ "$ANGELLA_WORKER_PROVIDER" = "angella_mlx_local" ]; then
        if [ "$ANGELLA_MLX_ENABLED" = "true" ]; then
            ok "MLX local worker is enabled"
        else
            warn "MLX worker selected but endpoint is not currently enabled."
            warn "Check ANGELLA_LOCAL_WORKER_BACKEND=mlx and ANGELLA_MLX_BASE_URL."
        fi
    elif [ "$ANGELLA_WORKER_PROVIDER" = "angella_apfel_local" ]; then
        if [ "$ANGELLA_APFEL_ENABLED" = "true" ]; then
            ok "legacy apfel custom provider is enabled"
        else
            warn "legacy apfel worker selected but provider is not currently enabled."
        fi
    fi
}

detect_python_runtime() {
    info "Detecting Python runtime for setup/bootstrap..."
    if PYTHON_CMD="$(detect_python)"; then
        ok "Using Python interpreter: $PYTHON_CMD"
    else
        fail "Python not found. Install python3 before running setup."
        exit 1
    fi
}

check_python_requirements_support() {
    info "Checking pip availability for MCP servers..."
    if "$PYTHON_CMD" -c "import pip" >/dev/null 2>&1; then
        PYTHON_PIP_AVAILABLE=true
        ok "pip is available for $PYTHON_CMD"
    else
        fail "pip is not available for $PYTHON_CMD"
        exit 1
    fi
}

load_python_for_install_stage() {
    if [ "$CHECK_ONLY" = true ]; then
        return 0
    fi

    if load_bootstrap_state; then
        return 0
    fi

    fail "Bootstrap environment not found. Run 'bash setup.sh --bootstrap-only' or full setup first."
    exit 1
}

render_all_templates() {
    local config_target=$1
    local recipe_target=$2
    local sub_recipe_dir=$3

    verify_template_source_portable "$SCRIPT_DIR/config/goose-config.yaml"
    verify_template_source_portable "$SCRIPT_DIR/recipes/autoresearch-loop.yaml"
    verify_template_source_portable "$SCRIPT_DIR/recipes/sub/code-optimize.yaml"
    verify_template_source_portable "$SCRIPT_DIR/recipes/sub/evaluate-metric.yaml"

    render_and_verify "$SCRIPT_DIR/config/goose-config.yaml" "$config_target"
    render_and_verify "$SCRIPT_DIR/recipes/autoresearch-loop.yaml" "$recipe_target"
    render_and_verify "$SCRIPT_DIR/recipes/sub/code-optimize.yaml" "$sub_recipe_dir/code-optimize.yaml"
    render_and_verify "$SCRIPT_DIR/recipes/sub/evaluate-metric.yaml" "$sub_recipe_dir/evaluate-metric.yaml"
}

check_templates_only() {
    CHECK_RENDER_DIR="$(mktemp -d)"
    info "Rendering templates into temporary directory..."
    render_all_templates \
        "$CHECK_RENDER_DIR/config.yaml" \
        "$CHECK_RENDER_DIR/autoresearch-loop.yaml" \
        "$CHECK_RENDER_DIR/sub"
    ok "Template rendering checks passed"
}

install_templates() {
    local render_dir
    local rendered_config_path
    local rendered_recipe_path
    local rendered_code_path
    local rendered_eval_path
    local existing_config_hash
    local existing_recipe_hash
    local existing_code_hash
    local existing_eval_hash
    local rendered_config_hash
    local rendered_recipe_hash
    local rendered_code_hash
    local rendered_eval_hash
    local applied_hashes_json
    local drift_targets=()
    local overwrite_mode="installed_new"

    info "Rendering Angella templates..."
    render_dir="$(mktemp -d)"
    rendered_config_path="$render_dir/config.yaml"
    rendered_recipe_path="$render_dir/autoresearch-loop.yaml"
    rendered_code_path="$render_dir/sub/code-optimize.yaml"
    rendered_eval_path="$render_dir/sub/evaluate-metric.yaml"

    render_all_templates \
        "$rendered_config_path" \
        "$rendered_recipe_path" \
        "$render_dir/sub"

    existing_config_hash="$(sha256_file "$RENDERED_CONFIG_PATH")"
    existing_recipe_hash="$(sha256_file "$RENDERED_RECIPE_PATH")"
    existing_code_hash="$(sha256_file "$RENDERED_SUB_RECIPE_DIR/code-optimize.yaml")"
    existing_eval_hash="$(sha256_file "$RENDERED_SUB_RECIPE_DIR/evaluate-metric.yaml")"

    rendered_config_hash="$(sha256_file "$rendered_config_path")"
    rendered_recipe_hash="$(sha256_file "$rendered_recipe_path")"
    rendered_code_hash="$(sha256_file "$rendered_code_path")"
    rendered_eval_hash="$(sha256_file "$rendered_eval_path")"

    ANGELLA_INSTALL_PREEXISTING_HASHES_JSON="$(hash_dict_json \
        config "$RENDERED_CONFIG_PATH" \
        autoresearch_loop "$RENDERED_RECIPE_PATH" \
        code_optimize "$RENDERED_SUB_RECIPE_DIR/code-optimize.yaml" \
        evaluate_metric "$RENDERED_SUB_RECIPE_DIR/evaluate-metric.yaml")"
    ANGELLA_INSTALL_RENDERED_HASHES_JSON="$(hash_dict_json \
        config "$rendered_config_path" \
        autoresearch_loop "$rendered_recipe_path" \
        code_optimize "$rendered_code_path" \
        evaluate_metric "$rendered_eval_path")"

    [ -n "$existing_config_hash" ] && [ "$existing_config_hash" != "$rendered_config_hash" ] && drift_targets+=("config")
    [ -n "$existing_recipe_hash" ] && [ "$existing_recipe_hash" != "$rendered_recipe_hash" ] && drift_targets+=("autoresearch_loop")
    [ -n "$existing_code_hash" ] && [ "$existing_code_hash" != "$rendered_code_hash" ] && drift_targets+=("code_optimize")
    [ -n "$existing_eval_hash" ] && [ "$existing_eval_hash" != "$rendered_eval_hash" ] && drift_targets+=("evaluate_metric")

    ANGELLA_INSTALL_DRIFT_DETECTED=false
    if [ "${#drift_targets[@]}" -gt 0 ]; then
        ANGELLA_INSTALL_DRIFT_DETECTED=true
        ANGELLA_INSTALL_DRIFT_TARGETS_JSON="$(json_array_from_args "${drift_targets[@]}")"
    else
        ANGELLA_INSTALL_DRIFT_TARGETS_JSON="[]"
    fi

    mkdir -p "$GOOSE_RECIPE_DIR" "$RENDERED_SUB_RECIPE_DIR"
    cp "$rendered_recipe_path" "$RENDERED_RECIPE_PATH"
    cp "$rendered_code_path" "$RENDERED_SUB_RECIPE_DIR/code-optimize.yaml"
    cp "$rendered_eval_path" "$RENDERED_SUB_RECIPE_DIR/evaluate-metric.yaml"

    if [ -f "$RENDERED_CONFIG_PATH" ]; then
        if [ "$existing_config_hash" = "$rendered_config_hash" ]; then
            info "Goose config already matches the rendered Angella config"
            overwrite_mode="already_synced"
        else
            warn "Goose config already exists at $RENDERED_CONFIG_PATH"
            if [ "$ANGELLA_INSTALL_DRIFT_DETECTED" = true ]; then
                warn "Detected install drift before overwrite. Targets: $ANGELLA_INSTALL_DRIFT_TARGETS_JSON"
            fi
            if [ "$AUTO_YES" = true ]; then
                info "AUTO_YES=true -> overwriting existing Goose config to avoid stale install drift"
                cp "$rendered_config_path" "$RENDERED_CONFIG_PATH"
                overwrite_mode="auto_yes_overwrite"
                ok "Goose config updated"
            elif prompt_yes_no "Overwrite with Angella config?" "no"; then
                cp "$rendered_config_path" "$RENDERED_CONFIG_PATH"
                overwrite_mode="prompt_overwrite"
                ok "Goose config updated"
            else
                overwrite_mode="kept_existing_config"
                info "Keeping existing config. Angella templates for recipes were still refreshed."
            fi
        fi
    else
        cp "$rendered_config_path" "$RENDERED_CONFIG_PATH"
        overwrite_mode="installed_new"
        ok "Goose config installed to $RENDERED_CONFIG_PATH"
    fi

    ANGELLA_INSTALL_OVERWRITE_MODE="$overwrite_mode"
    applied_hashes_json="$(hash_dict_json \
        config "$RENDERED_CONFIG_PATH" \
        autoresearch_loop "$RENDERED_RECIPE_PATH" \
        code_optimize "$RENDERED_SUB_RECIPE_DIR/code-optimize.yaml" \
        evaluate_metric "$RENDERED_SUB_RECIPE_DIR/evaluate-metric.yaml")"
    ANGELLA_INSTALL_APPLIED_HASHES_JSON="$applied_hashes_json"
    rm -rf "$render_dir"

    ok "Rendered recipe installed to $RENDERED_RECIPE_PATH"
    ok "Rendered sub-recipes installed to $RENDERED_SUB_RECIPE_DIR"
}

json_array_to_display() {
    "$PYTHON_CMD" - "$1" <<'PY'
import json
import sys

try:
    payload = json.loads(sys.argv[1])
except json.JSONDecodeError:
    payload = []

if not payload:
    print("[]")
else:
    print(", ".join(str(item) for item in payload))
PY
}

report_harness_credential_status() {
    local env_name
    local missing=0

    for env_name in GOOGLE_API_KEY OPENAI_API_KEY ANTHROPIC_API_KEY; do
        if [ -n "${!env_name:-}" ]; then
            ok "$env_name is set"
        fi
    done

    case "$ANGELLA_LEAD_PROVIDER" in
        google)
            [ -n "${GOOGLE_API_KEY:-}" ] || missing=1
            ;;
        openai)
            [ -n "${OPENAI_API_KEY:-}" ] || missing=1
            ;;
        anthropic)
            [ -n "${ANTHROPIC_API_KEY:-}" ] || missing=1
            ;;
    esac

    case "$ANGELLA_PLANNER_PROVIDER" in
        google)
            [ -n "${GOOGLE_API_KEY:-}" ] || missing=1
            ;;
        openai)
            [ -n "${OPENAI_API_KEY:-}" ] || missing=1
            ;;
        anthropic)
            [ -n "${ANTHROPIC_API_KEY:-}" ] || missing=1
            ;;
    esac

    case "$ANGELLA_WORKER_PROVIDER" in
        google)
            [ -n "${GOOGLE_API_KEY:-}" ] || missing=1
            ;;
        openai)
            [ -n "${OPENAI_API_KEY:-}" ] || missing=1
            ;;
        anthropic)
            [ -n "${ANTHROPIC_API_KEY:-}" ] || missing=1
            ;;
    esac

    if [ "$missing" -eq 1 ]; then
        warn "One or more selected lead/planner credentials are missing."
        echo "  Configure later with:"
        echo "    goose configure"
        echo "  Or export the provider API key before running the recipe."
    fi
}

print_banner() {
    echo ""
    echo "============================================"
    echo "  🦆 Angella — M3 Autoresearch Setup"
    echo "  MacBook Pro M3 36GB + MLX + Goose"
    echo "============================================"
    echo ""
}

print_summary() {
    echo ""
    echo "============================================"
    if [ "$CHECK_ONLY" = true ]; then
        echo "  ✅ Check Complete!"
    elif [ "$BOOTSTRAP_ONLY" = true ]; then
        echo "  ✅ Bootstrap Complete!"
    else
        echo "  ✅ Setup Complete!"
    fi
    echo "============================================"
    echo ""
    echo "  Next steps:"
    echo ""
    echo "  1. 환경변수 적용:"
    if [ -f "$SCRIPT_DIR/.env.mlx" ]; then
        echo "     # existing .env.mlx detected"
    else
        echo "     cp $SCRIPT_DIR/.env.mlx.example $SCRIPT_DIR/.env.mlx"
    fi
    echo "     source $SCRIPT_DIR/.env.mlx"
    echo ""
    echo "  Harness:"
    echo "     profile: ${ANGELLA_HARNESS_PROFILE_ID:-frontier_default}"
    echo "     lead: ${ANGELLA_LEAD_PROVIDER:-openai}/${ANGELLA_LEAD_MODEL:-gpt-5.2-pro}"
    echo "     planner: ${ANGELLA_PLANNER_PROVIDER:-openai}/${ANGELLA_PLANNER_MODEL:-gpt-5.2-pro}"
    echo "     worker: ${ANGELLA_WORKER_PROVIDER:-openai}/${ANGELLA_WORKER_MODEL:-gpt-5.2}"
    echo "     local backend: ${ANGELLA_LOCAL_WORKER_BACKEND:-ollama}"
    echo "     mode: ${ANGELLA_EXECUTION_MODE:-frontier_primary}"
    echo "     worker tier: ${ANGELLA_WORKER_TIER:-frontier_primary}"
    echo "     fallback reason: ${ANGELLA_FALLBACK_REASON:-none}"
    echo "     local cache enabled: ${ANGELLA_LOCAL_CACHE_ENABLED:-false}"
    echo "     token saver enabled: ${ANGELLA_TOKEN_SAVER_ENABLED:-false}"
    if [ "${ANGELLA_LOCAL_WORKER_BACKEND:-ollama}" = "mlx" ] || [ -n "${ANGELLA_MLX_BASE_URL:-}" ]; then
        echo "     mlx endpoint: ${ANGELLA_MLX_BASE_URL:-not_configured}"
        echo "     mlx model: ${ANGELLA_MLX_MODEL:-mlx-community/gemma-4-31b-it-4bit}"
    fi
    echo ""
    if [ "$CHECK_ONLY" = false ] && [ "$BOOTSTRAP_ONLY" = false ] && [ "${ANGELLA_INSTALL_OVERWRITE_MODE:-not_run}" != "not_run" ]; then
        echo "  Install drift:"
        echo "     detected: ${ANGELLA_INSTALL_DRIFT_DETECTED:-false}"
        echo "     targets: $(json_array_to_display "${ANGELLA_INSTALL_DRIFT_TARGETS_JSON:-[]}")"
        echo "     overwrite mode: ${ANGELLA_INSTALL_OVERWRITE_MODE:-not_run}"
        echo "     summary: ${ANGELLA_CONTROL_INSTALL_SUMMARY_PATH}"
        echo ""
    fi

    if [ "$BOOTSTRAP_ONLY" = true ]; then
        echo "  2. Install stage 실행:"
        echo "     bash $SCRIPT_DIR/setup.sh --install-only"
        echo ""
        echo "  Bootstrap Python:"
        echo "     ${ANGELLA_BOOTSTRAP_VENV_DIR}/bin/python"
    else
        echo "  2. Angella recipe 실행:"
        echo "     goose run --recipe $RENDERED_RECIPE_PATH -s"
        echo ""
        if [ "$CHECK_ONLY" = false ]; then
            echo "  Bootstrap Python:"
            echo "     ${ANGELLA_BOOTSTRAP_VENV_DIR}/bin/python"
            echo ""
        fi
    fi

    echo "  Cache paths:"
    echo "     bootstrap venv: $ANGELLA_BOOTSTRAP_VENV_DIR"
    echo "     uv cache: $ANGELLA_UV_CACHE_DIR"
    echo "     pip cache: $ANGELLA_PIP_CACHE_DIR"
    echo "     wheelhouse: $ANGELLA_WHEELHOUSE_DIR"
    echo ""
    echo "  Logs:"
    echo "     $SCRIPT_DIR/logs/Goose Logs/"
    echo ""
}
