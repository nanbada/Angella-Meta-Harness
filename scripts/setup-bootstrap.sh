#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
export ANGELLA_ROOT="$ROOT_DIR"

# shellcheck source=./setup-common.sh
source "$ROOT_DIR/scripts/setup-common.sh"

check_homebrew
ensure_goose
check_ollama_binary
ensure_ollama_server
ensure_models
detect_python_runtime

if [ "$CHECK_ONLY" = true ]; then
    check_python_requirements_support
    exit 0
fi

if [ "$INSTALL_ONLY" = true ]; then
    if ! bootstrap_state_exists; then
        fail "Bootstrap environment not found. Run 'bash setup.sh --bootstrap-only' or full setup first."
        exit 1
    fi

    exit 0
fi

ensure_bootstrap_environment "$PYTHON_CMD"
