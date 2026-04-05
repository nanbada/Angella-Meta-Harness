#!/usr/bin/env bash
# ============================================================
# Angella — M3 Autoresearch Self-Optimize Loop Setup
# ============================================================
# Usage:
#   bash setup.sh
#   bash setup.sh --yes
#   bash setup.sh --check
#   bash setup.sh --bootstrap-only
#   bash setup.sh --install-only
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export ANGELLA_ROOT="$SCRIPT_DIR"

AUTO_YES=false
CHECK_ONLY=false
BOOTSTRAP_ONLY=false
INSTALL_ONLY=false
LIST_MODELS=false
LIST_HARNESS_PROFILES=false
HARNESS_PROFILE=""
LEAD_MODEL_OVERRIDE=""
PLANNER_MODEL_OVERRIDE=""
WORKER_MODEL_OVERRIDE=""

cleanup() {
    cleanup_check_render_dir
}

usage() {
    cat <<EOF
Usage: bash setup.sh [--yes] [--check] [--bootstrap-only] [--install-only]
                     [--list-models] [--list-harness-profiles]
                     [--harness-profile <id>]
                     [--lead-model <id>] [--planner-model <id>] [--worker-model <id>]

Options:
  --yes             Prompt 없이 기본값으로 설치를 진행합니다.
  --check           설치 없이 의존성/템플릿 상태만 검증합니다.
  --bootstrap-only  Runtime/toolchain/bootstrap env 준비까지만 수행합니다.
  --install-only    기존 bootstrap env를 사용해 설치 단계만 수행합니다.
  --list-models     Catalog에 등록된 model과 enabled/disabled reason을 출력합니다.
  --list-harness-profiles
                    Harness profile과 resolved lead/planner/worker를 출력합니다.
  --harness-profile Harness profile id를 선택합니다.
  --lead-model      Lead model id를 직접 지정합니다.
  --planner-model   Planner model id를 직접 지정합니다.
  --worker-model    Worker model id를 직접 지정합니다.
  --help            도움말을 출력합니다.
EOF
}

parse_args() {
    while [ $# -gt 0 ]; do
        case "$1" in
            --yes|-y)
                AUTO_YES=true
                ;;
            --check)
                CHECK_ONLY=true
                ;;
            --bootstrap-only)
                BOOTSTRAP_ONLY=true
                ;;
            --install-only)
                INSTALL_ONLY=true
                ;;
            --list-models)
                LIST_MODELS=true
                ;;
            --list-harness-profiles)
                LIST_HARNESS_PROFILES=true
                ;;
            --harness-profile)
                HARNESS_PROFILE=${2:-}
                shift
                ;;
            --lead-model)
                LEAD_MODEL_OVERRIDE=${2:-}
                shift
                ;;
            --planner-model)
                PLANNER_MODEL_OVERRIDE=${2:-}
                shift
                ;;
            --worker-model)
                WORKER_MODEL_OVERRIDE=${2:-}
                shift
                ;;
            --help|-h)
                usage
                exit 0
                ;;
            *)
                echo "Unknown argument: $1" >&2
                usage
                exit 1
                ;;
        esac
        shift
    done

    if [ "$CHECK_ONLY" = true ] && { [ "$BOOTSTRAP_ONLY" = true ] || [ "$INSTALL_ONLY" = true ]; }; then
        echo "--check cannot be combined with --bootstrap-only or --install-only" >&2
        exit 1
    fi

    if [ "$BOOTSTRAP_ONLY" = true ] && [ "$INSTALL_ONLY" = true ]; then
        echo "--bootstrap-only and --install-only are mutually exclusive" >&2
        exit 1
    fi

    if [ "$LIST_MODELS" = true ] && [ "$LIST_HARNESS_PROFILES" = true ]; then
        echo "--list-models and --list-harness-profiles are mutually exclusive" >&2
        exit 1
    fi

    if { [ -n "$LEAD_MODEL_OVERRIDE" ] || [ -n "$PLANNER_MODEL_OVERRIDE" ] || [ -n "$WORKER_MODEL_OVERRIDE" ]; } && [ "$LIST_MODELS" = true ]; then
        echo "--list-models cannot be combined with explicit model overrides" >&2
        exit 1
    fi
}

# shellcheck source=./scripts/setup-common.sh
source "$SCRIPT_DIR/scripts/setup-common.sh"

parse_args "$@"
trap cleanup EXIT

print_banner
export AUTO_YES CHECK_ONLY BOOTSTRAP_ONLY INSTALL_ONLY
export LIST_MODELS LIST_HARNESS_PROFILES HARNESS_PROFILE
export LEAD_MODEL_OVERRIDE PLANNER_MODEL_OVERRIDE WORKER_MODEL_OVERRIDE

bash "$SCRIPT_DIR/scripts/setup-bootstrap.sh"

if [ "$BOOTSTRAP_ONLY" = false ] && [ "$LIST_MODELS" = false ] && [ "$LIST_HARNESS_PROFILES" = false ]; then
    bash "$SCRIPT_DIR/scripts/setup-install.sh"
fi

if [ "$LIST_MODELS" = false ] && [ "$LIST_HARNESS_PROFILES" = false ]; then
    print_summary
fi
