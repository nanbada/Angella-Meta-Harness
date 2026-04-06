#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TMP_ROOT="$(mktemp -d)"
trap 'rm -rf "$TMP_ROOT"' EXIT

FAKE_BIN="$TMP_ROOT/bin"
mkdir -p "$FAKE_BIN"

REAL_PYTHON="$(command -v python3)"

cat >"$FAKE_BIN/brew" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF

cat >"$FAKE_BIN/goose" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF

cat >"$FAKE_BIN/uv" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF

cat >"$FAKE_BIN/ollama" <<'EOF'
#!/usr/bin/env bash
case "${1:-}" in
  pull)
    exit 0
    ;;
  serve)
    exit 0
    ;;
  *)
    exit 0
    ;;
esac
EOF

cat >"$FAKE_BIN/curl" <<'EOF'
#!/usr/bin/env bash
if printf '%s\n' "$*" | grep -q '/api/tags'; then
  cat <<'JSON'
{"models":[{"name":"gemma4:26b"}]}
JSON
  exit 0
fi

exit 1
EOF

cat >"$FAKE_BIN/python3" <<EOF
#!/usr/bin/env bash
set -euo pipefail
REAL_PYTHON="$REAL_PYTHON"

if [ "\${1:-}" = "-m" ] && [ "\${2:-}" = "pip" ] && [ "\${3:-}" = "--version" ]; then
  exit 0
fi

if [ "\${1:-}" = "-m" ] && [ "\${2:-}" = "pip" ] && [ "\${3:-}" = "install" ]; then
  exit 0
fi

if [ "\${1:-}" = "-c" ]; then
  case "\${2:-}" in
    "import pip")
      exit 0
      ;;
    *"find_spec(\"mcp\")"* )
      exit 0
      ;;
  esac
fi

exec "\$REAL_PYTHON" "\$@"
EOF

chmod +x "$FAKE_BIN/brew" "$FAKE_BIN/goose" "$FAKE_BIN/ollama" "$FAKE_BIN/curl" "$FAKE_BIN/python3" "$FAKE_BIN/uv"

CHECK_HOME="$TMP_ROOT/home-check"
YES_HOME="$TMP_ROOT/home-yes"
BOOTSTRAP_HOME="$TMP_ROOT/home-bootstrap"
INSTALL_HOME="$TMP_ROOT/home-install"
mkdir -p "$CHECK_HOME" "$YES_HOME" "$BOOTSTRAP_HOME" "$INSTALL_HOME"

export PATH="$FAKE_BIN:$PATH"
GOOGLE_KEY_NAME="GOOGLE_API_KEY"
OPENAI_KEY_NAME="OPENAI_API_KEY"
ANTHROPIC_KEY_NAME="ANTHROPIC_API_KEY"
export "$GOOGLE_KEY_NAME"="test-google-key"
export "$OPENAI_KEY_NAME"="test-openai-key"
export "$ANTHROPIC_KEY_NAME"="test-anthropic-key"
export ANGELLA_OLLAMA_TAGS_JSON='{"models":[{"name":"gemma4:26b"}]}'

CHECK_OUT="$TMP_ROOT/check.out"
CHECK_ERR="$TMP_ROOT/check.err"

(
  cd "$ROOT_DIR"
  HOME="$CHECK_HOME" bash setup.sh --check >"$CHECK_OUT" 2>"$CHECK_ERR"
)

grep -q "Template rendering checks passed" "$CHECK_OUT"
grep -q "Model 'gemma4:26b' already pulled" "$CHECK_OUT"

MODELS_OUT="$TMP_ROOT/models.out"
(
  cd "$ROOT_DIR"
  HOME="$CHECK_HOME" bash setup.sh --list-models >"$MODELS_OUT" 2>/dev/null
)
grep -q "google_gemini_2_5_pro" "$MODELS_OUT"
grep -q "ollama_gemma4_26b" "$MODELS_OUT"
! grep -q "ollama_qwen25_coder_32b" "$MODELS_OUT"

PROFILES_OUT="$TMP_ROOT/profiles.out"
(
  cd "$ROOT_DIR"
  HOME="$CHECK_HOME" bash setup.sh --list-harness-profiles >"$PROFILES_OUT" 2>/dev/null
)
grep -q "default: .*worker=ollama_gemma4_26b" "$PROFILES_OUT"
grep -q "preview_nvfp4: disabled" "$PROFILES_OUT"

BOOTSTRAP_OUT="$TMP_ROOT/bootstrap.out"
BOOTSTRAP_ERR="$TMP_ROOT/bootstrap.err"

(
  cd "$ROOT_DIR"
  HOME="$BOOTSTRAP_HOME" bash setup.sh --bootstrap-only >"$BOOTSTRAP_OUT" 2>"$BOOTSTRAP_ERR"
)

test -f "$ROOT_DIR/.cache/angella/bootstrap.env"
test -f "$ROOT_DIR/.cache/angella/bootstrap-venv/bin/python"
grep -q "ANGELLA_HARNESS_PROFILE_ID=.*default" "$ROOT_DIR/.cache/angella/bootstrap.env"
grep -q "Bootstrap Complete" "$BOOTSTRAP_OUT"

INSTALL_OUT="$TMP_ROOT/install.out"
INSTALL_ERR="$TMP_ROOT/install.err"

(
  cd "$ROOT_DIR"
  HOME="$INSTALL_HOME" bash setup.sh --install-only >"$INSTALL_OUT" 2>"$INSTALL_ERR"
)

test -f "$INSTALL_HOME/.config/goose/config.yaml"
test -f "$INSTALL_HOME/.config/goose/recipes/autoresearch-loop.yaml"
test -f "$ROOT_DIR/.cache/angella/control-plane/install/summary.json"
test -f "$ROOT_DIR/.cache/angella/control-plane/install/telemetry.jsonl"
grep -q '"rendered_hashes"' "$ROOT_DIR/.cache/angella/control-plane/install/summary.json"
grep -q '"overwrite_mode": "installed_new"' "$ROOT_DIR/.cache/angella/control-plane/install/summary.json"
grep -q "Setup Complete" "$INSTALL_OUT"

AUTO_YES_HOME="$TMP_ROOT/home-auto-yes-overwrite"
mkdir -p "$AUTO_YES_HOME/.config/goose/recipes"
cat >"$AUTO_YES_HOME/.config/goose/config.yaml" <<'EOF'
GOOSE_PROVIDER: "ollama"
GOOSE_MODEL: "stale-model"
EOF

AUTO_YES_OUT="$TMP_ROOT/auto-yes-overwrite.out"
AUTO_YES_ERR="$TMP_ROOT/auto-yes-overwrite.err"
(
  cd "$ROOT_DIR"
  HOME="$AUTO_YES_HOME" bash setup.sh \
    --install-only \
    --yes \
    --lead-model openai_gpt_5_2_pro \
    --planner-model openai_gpt_5_2_pro \
    --worker-model ollama_gemma4_26b >"$AUTO_YES_OUT" 2>"$AUTO_YES_ERR"
)

grep -q 'GOOSE_MODEL: "gemma4:26b"' "$AUTO_YES_HOME/.config/goose/config.yaml"
grep -q 'GOOSE_LEAD_PROVIDER: "openai"' "$AUTO_YES_HOME/.config/goose/config.yaml"
grep -q '"drift_detected": true' "$ROOT_DIR/.cache/angella/control-plane/install/summary.json"
grep -q '"overwrite_mode": "auto_yes_overwrite"' "$ROOT_DIR/.cache/angella/control-plane/install/summary.json"
grep -q '"drift_detected": true' "$ROOT_DIR/.cache/angella/control-plane/install/telemetry.jsonl"

YES_OUT="$TMP_ROOT/yes.out"
YES_ERR="$TMP_ROOT/yes.err"

(
  cd "$ROOT_DIR"
  HOME="$YES_HOME" bash setup.sh \
    --harness-profile default \
    --lead-model openai_gpt_5_2_pro \
    --planner-model anthropic_claude_sonnet_4 \
    --worker-model ollama_gemma4_26b \
    --yes >"$YES_OUT" 2>"$YES_ERR"
)

test -f "$YES_HOME/.config/goose/config.yaml"
test -f "$YES_HOME/.config/goose/recipes/autoresearch-loop.yaml"
test -f "$YES_HOME/.config/goose/recipes/harness-self-optimize.yaml"
test -f "$YES_HOME/.config/goose/recipes/sub/code-optimize.yaml"
test -f "$YES_HOME/.config/goose/recipes/sub/evaluate-metric.yaml"
grep -q 'command: "harness-self-optimize"' "$YES_HOME/.config/goose/config.yaml"
grep -q 'GOOSE_LEAD_PROVIDER: "openai"' "$YES_HOME/.config/goose/config.yaml"
grep -q 'GOOSE_LEAD_MODEL: "gpt-5.2-pro"' "$YES_HOME/.config/goose/config.yaml"
grep -q 'GOOSE_PLANNER_PROVIDER: "anthropic"' "$YES_HOME/.config/goose/config.yaml"
grep -q 'GOOSE_PLANNER_MODEL: "claude-sonnet-4-20250514"' "$YES_HOME/.config/goose/config.yaml"
grep -q 'GOOSE_PROVIDER: "ollama"' "$YES_HOME/.config/goose/config.yaml"
grep -q 'GOOSE_MODEL: "gemma4:26b"' "$YES_HOME/.config/goose/config.yaml"
grep -q 'lead: openai/gpt-5.2-pro' "$YES_OUT"
grep -q 'planner: anthropic/claude-sonnet-4-20250514' "$YES_OUT"
grep -q 'worker: ollama/gemma4:26b' "$YES_OUT"
test -d "$ROOT_DIR/logs/Goose Logs"
test -f "$ROOT_DIR/.cache/angella/control-plane/current-selection.json"

if command -v rg >/dev/null 2>&1; then
  ! rg -q '__ANGELLA_ROOT__|__PYTHON_CMD__|__RENDERED_RECIPE_PATH__|__RENDERED_HARNESS_SELF_OPTIMIZE_PATH__' "$YES_HOME/.config/goose"
else
  ! grep -REq '__ANGELLA_ROOT__|__PYTHON_CMD__|__RENDERED_RECIPE_PATH__|__RENDERED_HARNESS_SELF_OPTIMIZE_PATH__' "$YES_HOME/.config/goose"
fi

grep -q "Goose config installed to" "$YES_OUT"
grep -q "Rendered recipe installed to" "$YES_OUT"

python3 "$ROOT_DIR/scripts/test_control_plane_logging.py"
python3 "$ROOT_DIR/scripts/test_meta_loop_admin.py"
python3 "$ROOT_DIR/scripts/test_harness_self_optimize_adapter.py"

echo "setup flow tests passed"
