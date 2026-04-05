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

CHECK_RENDER_DIR="${CHECK_RENDER_DIR:-}"
OLLAMA_TAGS_JSON="${OLLAMA_TAGS_JSON:-}"
AUTO_YES="${AUTO_YES:-false}"
CHECK_ONLY="${CHECK_ONLY:-false}"
BOOTSTRAP_ONLY="${BOOTSTRAP_ONLY:-false}"
INSTALL_ONLY="${INSTALL_ONLY:-false}"
PYTHON_PIP_AVAILABLE="${PYTHON_PIP_AVAILABLE:-false}"
ENV_MLX_PATH="${ENV_MLX_PATH:-}"
PYTHON_CMD="${PYTHON_CMD:-}"

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

escape_sed_replacement() {
    local escaped=${1//\\/\\\\}
    escaped=${escaped//&/\\&}
    escaped=${escaped//|/\\|}
    printf '%s' "$escaped"
}

render_template() {
    local template_path=$1
    local output_path=$2
    local escaped_root
    local escaped_python
    local escaped_recipe_path

    escaped_root="$(escape_sed_replacement "$SCRIPT_DIR")"
    escaped_python="$(escape_sed_replacement "$PYTHON_CMD")"
    escaped_recipe_path="$(escape_sed_replacement "$RENDERED_RECIPE_PATH")"

    mkdir -p "$(dirname "$output_path")"
    sed \
        -e "s|__ANGELLA_ROOT__|$escaped_root|g" \
        -e "s|__PYTHON_CMD__|$escaped_python|g" \
        -e "s|__RENDERED_RECIPE_PATH__|$escaped_recipe_path|g" \
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

bootstrap_state_exists() {
    [ -f "$ANGELLA_BOOTSTRAP_STATE_PATH" ]
}

write_bootstrap_state() {
    mkdir -p "$(dirname "$ANGELLA_BOOTSTRAP_STATE_PATH")"
    cat >"$ANGELLA_BOOTSTRAP_STATE_PATH" <<EOF
PYTHON_CMD=$(printf '%q' "$PYTHON_CMD")
EOF
}

load_bootstrap_state() {
    if ! bootstrap_state_exists; then
        return 1
    fi

    # shellcheck disable=SC1090
    source "$ANGELLA_BOOTSTRAP_STATE_PATH"
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
    info "Checking required Ollama models..."
    if ! ollama_is_running; then
        warn "Ollama server is not running. Skipping model pull."
        echo "  Run manually later:"
        echo "    ollama pull qwen2.5-coder:32b"
        echo "    ollama pull gemma4:26b"
        return
    fi

    if [ "$CHECK_ONLY" = true ]; then
        if ollama_has_model "qwen2.5-coder:32b"; then
            ok "Model 'qwen2.5-coder:32b' already pulled"
        else
            warn "Model 'qwen2.5-coder:32b' is not pulled yet."
        fi

        if ollama_has_model "gemma4:26b"; then
            ok "Model 'gemma4:26b' already pulled"
        else
            warn "Model 'gemma4:26b' is not pulled yet."
        fi
        return
    fi

    pull_model "qwen2.5-coder:32b"
    pull_model "gemma4:26b"
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
    info "Rendering Angella templates..."
    render_and_verify "$SCRIPT_DIR/recipes/autoresearch-loop.yaml" "$RENDERED_RECIPE_PATH"
    render_and_verify "$SCRIPT_DIR/recipes/sub/code-optimize.yaml" "$RENDERED_SUB_RECIPE_DIR/code-optimize.yaml"
    render_and_verify "$SCRIPT_DIR/recipes/sub/evaluate-metric.yaml" "$RENDERED_SUB_RECIPE_DIR/evaluate-metric.yaml"

    if [ -f "$RENDERED_CONFIG_PATH" ]; then
        warn "Goose config already exists at $RENDERED_CONFIG_PATH"
        if prompt_yes_no "Overwrite with Angella config?" "no"; then
            render_and_verify "$SCRIPT_DIR/config/goose-config.yaml" "$RENDERED_CONFIG_PATH"
            ok "Goose config updated"
        else
            info "Keeping existing config. Angella templates for recipes were still refreshed."
        fi
    else
        render_and_verify "$SCRIPT_DIR/config/goose-config.yaml" "$RENDERED_CONFIG_PATH"
        ok "Goose config installed to $RENDERED_CONFIG_PATH"
    fi

    ok "Rendered recipe installed to $RENDERED_RECIPE_PATH"
    ok "Rendered sub-recipes installed to $RENDERED_SUB_RECIPE_DIR"
}

report_google_api_key_status() {
    if [ -n "${GOOGLE_API_KEY:-}" ]; then
        ok "GOOGLE_API_KEY is already set"
    else
        warn "GOOGLE_API_KEY is not set. Goose lead model will need it at runtime."
        echo "  Configure later with:"
        echo "    goose configure"
        echo "  Or export it in your shell before running the recipe."
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
    echo "     cp $SCRIPT_DIR/.env.mlx.example $SCRIPT_DIR/.env.mlx"
    echo "     source $SCRIPT_DIR/.env.mlx"
    echo ""

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
