#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
export ANGELLA_ROOT="$ROOT_DIR"

# shellcheck source=./setup-common.sh
source "$ROOT_DIR/scripts/setup-common.sh"

check_homebrew
ensure_goose
detect_python_runtime

if [ "$CHECK_ONLY" = true ]; then
    if [ "$LIST_MODELS" = true ]; then
        list_harness_models
        exit 0
    fi

    if [ "$LIST_HARNESS_PROFILES" = true ]; then
        list_harness_profiles
        exit 0
    fi

    resolve_harness_selection
    if [ "$ANGELLA_WORKER_PROVIDER" = "ollama" ]; then
        check_ollama_binary
        ensure_ollama_server
        ensure_models
    fi
    if [ "$ANGELLA_WORKER_PROVIDER" = "angella_apfel_local" ] && [ "$ANGELLA_APFEL_ENABLED" != "true" ]; then
        fail "Selected apfel worker is not available. Check ANGELLA_APFEL_BASE_URL and provider health."
        exit 1
    fi
    check_python_requirements_support
    create_control_plane_layout
    write_harness_resolution_snapshot
    exit 0
fi

if [ "$INSTALL_ONLY" = true ]; then
    if ! bootstrap_state_exists; then
        fail "Bootstrap environment not found. Run 'bash setup.sh --bootstrap-only' or full setup first."
        exit 1
    fi

    exit 0
fi

if [ "$LIST_MODELS" = true ]; then
    list_harness_models
    exit 0
fi

if [ "$LIST_HARNESS_PROFILES" = true ]; then
    list_harness_profiles
    exit 0
fi

resolve_harness_selection
if [ "$ANGELLA_WORKER_PROVIDER" = "ollama" ]; then
    check_ollama_binary
    ensure_ollama_server
    ensure_models
fi
if [ "$ANGELLA_WORKER_PROVIDER" = "angella_apfel_local" ] && [ "$ANGELLA_APFEL_ENABLED" != "true" ]; then
    fail "Selected apfel worker is not available. Check ANGELLA_APFEL_BASE_URL and provider health."
    exit 1
fi
ensure_bootstrap_environment "$PYTHON_CMD"
write_bootstrap_state
create_control_plane_layout
write_harness_resolution_snapshot
