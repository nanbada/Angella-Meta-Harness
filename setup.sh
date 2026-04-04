#!/bin/bash
# ============================================================
# Angella — M3 Autoresearch Self-Optimize Loop Setup
# ============================================================
# 이 스크립트는 Goose + Ollama + MCP 환경을 자동으로 셋업합니다.
# Usage: bash setup.sh
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC} $1"; }
ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
fail()  { echo -e "${RED}[FAIL]${NC} $1"; }

detect_python() {
    if command -v python3 &>/dev/null; then
        echo "python3"
        return
    fi

    if command -v python &>/dev/null; then
        echo "python"
        return
    fi

    return 1
}

escape_sed_replacement() {
    printf '%s' "$1" | sed -e 's/[&|]/\\&/g'
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

echo ""
echo "============================================"
echo "  🦆 Angella — M3 Autoresearch Setup"
echo "  MacBook Pro M3 36GB + MLX + Goose"
echo "============================================"
echo ""

# ──────────────────────────────────────────────
# 1. Check Homebrew
# ──────────────────────────────────────────────
info "Checking Homebrew..."
if command -v brew &>/dev/null; then
    ok "Homebrew found"
else
    fail "Homebrew not found. Install from https://brew.sh"
    exit 1
fi

# ──────────────────────────────────────────────
# 2. Check & Install Goose CLI
# ──────────────────────────────────────────────
info "Checking Goose CLI..."
if command -v goose &>/dev/null; then
    ok "Goose CLI found: $(goose --version 2>/dev/null || echo 'version unknown')"
else
    warn "Goose CLI not found. Installing..."
    echo ""
    echo "  Option 1: brew install block-goose-cli"
    echo "  Option 2: curl -fsSL https://github.com/block/goose/releases/download/stable/download_cli.sh | CONFIGURE=false bash"
    echo ""
    read -p "Install via Homebrew? [Y/n] " choice
    case "$choice" in
        n|N) 
            info "Skipping Goose CLI installation."
            warn "Please install Goose manually before running recipes."
            ;;
        *)
            brew install block-goose-cli
            ok "Goose CLI installed"
            ;;
    esac
fi

# ──────────────────────────────────────────────
# 3. Check Ollama
# ──────────────────────────────────────────────
info "Checking Ollama..."
if command -v ollama &>/dev/null; then
    ok "Ollama found: $(ollama --version 2>/dev/null || echo 'installed')"
else
    fail "Ollama not found. Install from https://ollama.com"
    exit 1
fi

# Check if Ollama is running
info "Checking Ollama server..."
if curl -s http://localhost:11434/api/tags &>/dev/null; then
    ok "Ollama server is running"
else
    warn "Ollama server is not running."
    read -p "Start Ollama server now? [Y/n] " choice
    case "$choice" in
        n|N)
            warn "Ollama server not started. Run 'ollama serve' before using recipes."
            ;;
        *)
            info "Starting Ollama server in background..."
            ollama serve &>/dev/null &
            sleep 3
            if curl -s http://localhost:11434/api/tags &>/dev/null; then
                ok "Ollama server started"
            else
                warn "Failed to start Ollama. Try 'ollama serve' manually."
            fi
            ;;
    esac
fi

# ──────────────────────────────────────────────
# 4. Pull Ollama Models
# ──────────────────────────────────────────────
info "Checking required Ollama models..."

pull_model() {
    local model=$1
    if ollama list 2>/dev/null | grep -q "$model"; then
        ok "Model '$model' already pulled"
    else
        info "Pulling '$model' (this may take a while)..."
        ollama pull "$model"
        ok "Model '$model' pulled"
    fi
}

if curl -s http://localhost:11434/api/tags &>/dev/null; then
    pull_model "qwen2.5-coder:32b"
    pull_model "gemma4:26b"
else
    warn "Ollama not running — skipping model pull. Run these manually:"
    echo "  ollama pull qwen2.5-coder:32b"
    echo "  ollama pull gemma4:26b"
fi

# ──────────────────────────────────────────────
# 5. Detect Python Runtime
# ──────────────────────────────────────────────
info "Detecting Python runtime for MCP servers..."
if PYTHON_CMD="$(detect_python)"; then
    ok "Using Python interpreter: $PYTHON_CMD"
else
    fail "Python not found. Install python3 before running setup."
    exit 1
fi

# ──────────────────────────────────────────────
# 6. Python Dependencies for MCP Servers
# ──────────────────────────────────────────────
info "Installing Python dependencies for MCP servers..."
if "$PYTHON_CMD" -m pip --version &>/dev/null; then
    "$PYTHON_CMD" -m pip install -r "$SCRIPT_DIR/mcp-servers/requirements.txt" --quiet 2>/dev/null || {
        warn "pip install failed. Trying with --user flag..."
        "$PYTHON_CMD" -m pip install -r "$SCRIPT_DIR/mcp-servers/requirements.txt" --user --quiet 2>/dev/null || {
            fail "Could not install Python dependencies."
            echo "  Manual install: $PYTHON_CMD -m pip install mcp fastmcp"
        }
    }
    ok "Python dependencies installed"
else
    warn "pip is not available for $PYTHON_CMD. Install Python dependencies manually:"
    echo "  $PYTHON_CMD -m ensurepip --upgrade"
    echo "  $PYTHON_CMD -m pip install mcp fastmcp"
fi

# ──────────────────────────────────────────────
# 7. Apply Environment Variables
# ──────────────────────────────────────────────
info "Loading MLX environment variables..."
source "$SCRIPT_DIR/.env.mlx"
ok "Environment variables loaded"

# ──────────────────────────────────────────────
# 8. Setup Goose Config
# ──────────────────────────────────────────────
GOOSE_CONFIG_DIR="$HOME/.config/goose"
GOOSE_RECIPE_DIR="$GOOSE_CONFIG_DIR/recipes"
RENDERED_CONFIG_PATH="$GOOSE_CONFIG_DIR/config.yaml"
RENDERED_RECIPE_PATH="$GOOSE_RECIPE_DIR/autoresearch-loop.yaml"
info "Checking Goose config..."

render_template "$SCRIPT_DIR/recipes/autoresearch-loop.yaml" "$RENDERED_RECIPE_PATH"

if [ -f "$RENDERED_CONFIG_PATH" ]; then
    warn "Goose config already exists at $RENDERED_CONFIG_PATH"
    read -p "Overwrite with Angella config? [y/N] " choice
    case "$choice" in
        y|Y)
            render_template "$SCRIPT_DIR/config/goose-config.yaml" "$RENDERED_CONFIG_PATH"
            ok "Goose config updated"
            ;;
        *)
            info "Keeping existing config. You can merge manually from config/goose-config.yaml"
            ;;
    esac
else
    mkdir -p "$GOOSE_CONFIG_DIR"
    render_template "$SCRIPT_DIR/config/goose-config.yaml" "$RENDERED_CONFIG_PATH"
    ok "Goose config installed to $RENDERED_CONFIG_PATH"
fi

ok "Rendered recipe installed to $RENDERED_RECIPE_PATH"

# ──────────────────────────────────────────────
# 9. Create logs directory
# ──────────────────────────────────────────────
mkdir -p "$SCRIPT_DIR/logs/Goose Logs"
ok "Log directory created: $SCRIPT_DIR/logs/Goose Logs/"

# ──────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────
echo ""
echo "============================================"
echo "  ✅ Setup Complete!"
echo "============================================"
echo ""
echo "  Next steps:"
echo ""
echo "  1. 환경변수 영구 적용 (선택):"
echo "     echo 'source $SCRIPT_DIR/.env.mlx' >> ~/.zshrc"
echo ""
echo "  2. Gemini API Key 설정 (필수 — Lead model용):"
echo "     export GOOGLE_API_KEY=your_key_here"
echo "     또는: goose configure → Configure Providers → Google Gemini"
echo ""
echo "  3. Autoresearch Loop 실행:"
echo "     goose session --recipe $RENDERED_RECIPE_PATH"
echo ""
echo "  4. 또는 Goose Desktop에서:"
echo "     /autoresearch 슬래시 커맨드 사용"
echo ""
echo "  Memory 모니터링:"
echo "     Activity Monitor에서 unified memory 28GB 이하 유지 확인"
echo ""
