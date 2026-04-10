#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TMP_ROOT="$(mktemp -d)"
# trap 'rm -rf "$TMP_ROOT"' EXIT

VARS_JSON="$ROOT_DIR/config/project-vars.json"
MLX_MODEL_ID=$(python3 -c "import json; print(json.load(open('$VARS_JSON'))['MLX_MODEL_ID'])")
MLX_MODEL_NAME=$(python3 -c "import json; print(json.load(open('$VARS_JSON'))['MLX_MODEL_NAME'])")
OLLAMA_MODEL_ID=$(python3 -c "import json; print(json.load(open('$VARS_JSON'))['OLLAMA_MODEL_ID'])")
OLLAMA_MODEL_NAME=$(python3 -c "import json; print(json.load(open('$VARS_JSON'))['OLLAMA_MODEL_NAME'])")

FAKE_BIN="$TMP_ROOT/bin"
mkdir -p "$FAKE_BIN"

# --- Mocking binaries ---
cat >"$FAKE_BIN/curl" <<EOF
#!/usr/bin/env bash
if [[ "\$*" == *"localhost:11434/api/tags"* ]]; then
  echo "\$ANGELLA_OLLAMA_TAGS_JSON"
  exit 0
fi
if [[ "\$*" == *"127.0.0.1:11435/v1/models"* ]]; then
  if [[ "\${ANGELLA_MLX_HEALTHCHECK_OK:-0}" == "1" ]]; then
    echo '{"data":[]}'
    exit 0
  else
    exit 1
  fi
fi
exec curl "\$@"
EOF
chmod +x "$FAKE_BIN/curl"

cat >"$FAKE_BIN/brew" <<EOF
#!/usr/bin/env bash
exit 0
EOF
chmod +x "$FAKE_BIN/brew"

cat >"$FAKE_BIN/goose" <<EOF
#!/usr/bin/env bash
exit 0
EOF
chmod +x "$FAKE_BIN/goose"

cat >"$FAKE_BIN/ollama" <<EOF
#!/usr/bin/env bash
exit 0
EOF
chmod +x "$FAKE_BIN/ollama"

export PATH="$FAKE_BIN:$PATH"

CHECK_HOME="$TMP_ROOT/home-check"
BOOTSTRAP_HOME="$TMP_ROOT/home-bootstrap"
INSTALL_HOME="$TMP_ROOT/home-install"
mkdir -p "$CHECK_HOME" "$BOOTSTRAP_HOME" "$INSTALL_HOME"

# Base variables for all runs
export GOOGLE_KEY_NAME="GOOGLE_API_KEY"
export OPENAI_KEY_NAME="OPENAI_API_KEY"
export ANTHROPIC_KEY_NAME="ANTHROPIC_API_KEY"
export "$GOOGLE_KEY_NAME"="test-google-key"
export "$OPENAI_KEY_NAME"="test-openai-key"
export "$ANTHROPIC_KEY_NAME"="test-anthropic-key"
export ANGELLA_OLLAMA_TAGS_JSON="{\"models\":[{\"name\":\"$OLLAMA_MODEL_NAME\"}]}"

# Use temporary cache directory for tests
export ANGELLA_CACHE_DIR="$TMP_ROOT/cache"
mkdir -p "$ANGELLA_CACHE_DIR"
export ANGELLA_CONTROL_INSTALL_SUMMARY_PATH="$ANGELLA_CACHE_DIR/control-plane/install/summary.json"
export ANGELLA_CONTROL_INSTALL_TELEMETRY_PATH="$ANGELLA_CACHE_DIR/control-plane/install/telemetry.jsonl"

echo "[TEST] Starting setup flow tests..."

CHECK_OUT="$TMP_ROOT/check.out"
CHECK_ERR="$TMP_ROOT/check.err"

echo "[TEST] Running setup --check..."
(
  cd "$ROOT_DIR"
  HOME="$CHECK_HOME" bash setup.sh --check >"$CHECK_OUT" 2>"$CHECK_ERR"
)

grep -q "Template rendering checks passed" "$CHECK_OUT"

MODELS_OUT="$TMP_ROOT/models.out"
echo "[TEST] Listing models..."
(
  cd "$ROOT_DIR"
  HOME="$CHECK_HOME" bash setup.sh --list-models >"$MODELS_OUT" 2>/dev/null
)
grep -q "google_gemini_2_5_pro" "$MODELS_OUT"
grep -q "$OLLAMA_MODEL_ID" "$MODELS_OUT"
grep -q "openai_gpt_5_2_pro: roles=lead,planner,worker" "$MODELS_OUT"
grep -q "$MLX_MODEL_ID: .*ANGELLA_LOCAL_WORKER_BACKEND=mlx" "$MODELS_OUT"
grep -q "$MLX_MODEL_ID: .*ANGELLA_MLX_BASE_URL" "$MODELS_OUT"

MLX_MODELS_OUT="$TMP_ROOT/mlx-models.out"
echo "[TEST] Listing MLX models..."
(
  cd "$ROOT_DIR"
  HOME="$CHECK_HOME" \
  ANGELLA_LOCAL_WORKER_BACKEND=mlx \
  ANGELLA_MLX_BASE_URL=http://127.0.0.1:11435/v1 \
  ANGELLA_MLX_MODEL=$MLX_MODEL_NAME \
  ANGELLA_MLX_HEALTHCHECK_OK=1 \
  bash setup.sh --list-models >"$MLX_MODELS_OUT" 2>/dev/null
)
grep -q "$MLX_MODEL_ID: .*provider=angella_mlx_local" "$MLX_MODELS_OUT"
grep -q "$MLX_MODEL_ID: .*status=enabled" "$MLX_MODELS_OUT"

PROFILES_OUT="$TMP_ROOT/profiles.out"
echo "[TEST] Listing harness profiles..."
(
  cd "$ROOT_DIR"
  HOME="$CHECK_HOME" bash setup.sh --list-harness-profiles >"$PROFILES_OUT" 2>/dev/null
)
grep -q "frontier_default: .*worker=openai_gpt_5_2" "$PROFILES_OUT"
grep -q "local_lab: .*worker=$OLLAMA_MODEL_ID" "$PROFILES_OUT"

MLX_PROFILES_OUT="$TMP_ROOT/mlx-profiles.out"
echo "[TEST] Listing MLX harness profiles..."
(
  cd "$ROOT_DIR"
  HOME="$CHECK_HOME" \
  ANGELLA_LOCAL_WORKER_BACKEND=mlx \
  ANGELLA_MLX_BASE_URL=http://127.0.0.1:11435/v1 \
  ANGELLA_MLX_MODEL=$MLX_MODEL_NAME \
  ANGELLA_MLX_HEALTHCHECK_OK=1 \
  ANGELLA_OLLAMA_TAGS_JSON="" \
  bash setup.sh --list-harness-profiles >"$MLX_PROFILES_OUT" 2>/dev/null
)
grep -q "local_lab: .*worker=$MLX_MODEL_ID" "$MLX_PROFILES_OUT"

echo "[TEST] Checking legacy profile error..."
LEGACY_PROFILE_ERR="$TMP_ROOT/legacy-profile.err"
if (
  cd "$ROOT_DIR"
  HOME="$CHECK_HOME" bash setup.sh --check --harness-profile default >/dev/null 2>"$LEGACY_PROFILE_ERR"
); then
  echo "legacy profile unexpectedly succeeded" >&2
  exit 1
fi
grep -q 'Legacy harness profile `default` has been removed' "$LEGACY_PROFILE_ERR"

MLX_CHECK_OUT="$TMP_ROOT/mlx-check.out"
MLX_CHECK_ERR="$TMP_ROOT/mlx-check.err"
echo "[TEST] Checking MLX worker resolution..."
(
  cd "$ROOT_DIR"
  HOME="$CHECK_HOME" \
  ANGELLA_LOCAL_WORKER_BACKEND=mlx \
  ANGELLA_MLX_BASE_URL=http://127.0.0.1:11435/v1 \
  ANGELLA_MLX_MODEL=$MLX_MODEL_NAME \
  ANGELLA_MLX_HEALTHCHECK_OK=1 \
  bash setup.sh --check --worker-model $MLX_MODEL_ID >"$MLX_CHECK_OUT" 2>"$MLX_CHECK_ERR"
)
grep -q "Template rendering checks passed" "$MLX_CHECK_OUT"
grep -q "worker: angella_mlx_local/$MLX_MODEL_NAME" "$MLX_CHECK_OUT"

MLX_FAIL_ERR="$TMP_ROOT/mlx-fail.err"
echo "[TEST] Checking MLX worker failure..."
if (
  cd "$ROOT_DIR"
  HOME="$CHECK_HOME" \
  ANGELLA_LOCAL_WORKER_BACKEND=mlx \
  ANGELLA_MLX_BASE_URL=http://127.0.0.1:11435/v1 \
  ANGELLA_MLX_MODEL=$MLX_MODEL_NAME \
  ANGELLA_MLX_HEALTHCHECK_OK=0 \
  bash setup.sh --check --worker-model $MLX_MODEL_ID >/dev/null 2>"$MLX_FAIL_ERR"
); then
  echo "mlx worker check unexpectedly succeeded" >&2
  exit 1
fi
grep -q 'ANGELLA_LOCAL_WORKER_BACKEND=mlx and ANGELLA_MLX_BASE_URL' "$MLX_FAIL_ERR"

OLLAMA_CHECK_OUT="$TMP_ROOT/ollama-check.out"
OLLAMA_CHECK_ERR="$TMP_ROOT/ollama-check.err"
echo "[TEST] Checking Ollama worker resolution..."
(
  cd "$ROOT_DIR"
  HOME="$CHECK_HOME" bash setup.sh --check --worker-model $OLLAMA_MODEL_ID >"$OLLAMA_CHECK_OUT" 2>"$OLLAMA_CHECK_ERR"
)
grep -q "worker: ollama/$OLLAMA_MODEL_NAME" "$OLLAMA_CHECK_OUT"
if ! grep -q "existing .env.mlx detected" "$OLLAMA_CHECK_OUT"; then
  grep -q "cp $ROOT_DIR/.env.mlx.example $ROOT_DIR/.env.mlx" "$OLLAMA_CHECK_OUT"
fi

BOOTSTRAP_OUT="$TMP_ROOT/bootstrap.out"
BOOTSTRAP_ERR="$TMP_ROOT/bootstrap.err"

echo "[TEST] Running --bootstrap-only..."
(
  cd "$ROOT_DIR"
  HOME="$BOOTSTRAP_HOME" bash setup.sh --bootstrap-only >"$BOOTSTRAP_OUT" 2>"$BOOTSTRAP_ERR"
)

test -f "$ANGELLA_CACHE_DIR/bootstrap.env"
test -f "$ANGELLA_CACHE_DIR/bootstrap-venv/bin/python"
grep -q "ANGELLA_HARNESS_PROFILE_ID=.*frontier_default" "$ANGELLA_CACHE_DIR/bootstrap.env"
grep -q "ANGELLA_EXECUTION_MODE=.*frontier_primary" "$ANGELLA_CACHE_DIR/bootstrap.env"
grep -q "Bootstrap Complete" "$BOOTSTRAP_OUT"

INSTALL_OUT="$TMP_ROOT/install.out"
INSTALL_ERR="$TMP_ROOT/install.err"

echo "[TEST] Running --install-only..."
(
  cd "$ROOT_DIR"
  HOME="$INSTALL_HOME" bash setup.sh --install-only >"$INSTALL_OUT" 2>"$INSTALL_ERR"
)

test -f "$INSTALL_HOME/.config/goose/config.yaml"
test -f "$INSTALL_HOME/.config/goose/recipes/autoresearch-loop.yaml"
test -f "$ANGELLA_CACHE_DIR/control-plane/install/summary.json"
test -f "$ANGELLA_CACHE_DIR/control-plane/install/telemetry.jsonl"
grep -q '"rendered_hashes"' "$ANGELLA_CACHE_DIR/control-plane/install/summary.json"
grep -q '"overwrite_mode": "installed_new"' "$ANGELLA_CACHE_DIR/control-plane/install/summary.json"
grep -q "Setup Complete" "$INSTALL_OUT"

MLX_INSTALL_HOME="$TMP_ROOT/home-install-mlx"
mkdir -p "$MLX_INSTALL_HOME"
MLX_INSTALL_OUT="$TMP_ROOT/install-mlx.out"
MLX_INSTALL_ERR="$TMP_ROOT/install-mlx.err"
echo "[TEST] Running MLX --install-only..."
(
  cd "$ROOT_DIR"
  HOME="$MLX_INSTALL_HOME" \
  ANGELLA_LOCAL_WORKER_BACKEND=mlx \
  ANGELLA_MLX_BASE_URL=http://127.0.0.1:11435/v1 \
  ANGELLA_MLX_MODEL=$MLX_MODEL_NAME \
  ANGELLA_MLX_HEALTHCHECK_OK=1 \
  bash setup.sh --install-only --worker-model $MLX_MODEL_ID --yes >"$MLX_INSTALL_OUT" 2>"$MLX_INSTALL_ERR"
)
test -f "$MLX_INSTALL_HOME/.config/goose/custom_providers/angella_mlx_local.json"
grep -q '"base_url": "http://127.0.0.1:11435/v1"' "$MLX_INSTALL_HOME/.config/goose/custom_providers/angella_mlx_local.json"
grep -q "\"model\": \"$MLX_MODEL_NAME\"" "$MLX_INSTALL_HOME/.config/goose/custom_providers/angella_mlx_local.json"
grep -q "GOOSE_MODEL: \"$MLX_MODEL_NAME\"" "$MLX_INSTALL_HOME/.config/goose/config.yaml"

AUTO_YES_HOME="$TMP_ROOT/home-auto-yes-overwrite"
mkdir -p "$AUTO_YES_HOME/.config/goose/recipes"
cat >"$AUTO_YES_HOME/.config/goose/config.yaml" <<'EOF'
GOOSE_PROVIDER: "openai"
GOOSE_MODEL: "gpt-4"
EOF

AUTO_YES_OUT="$TMP_ROOT/auto-yes.out"
AUTO_YES_ERR="$TMP_ROOT/auto-yes.err"
echo "[TEST] Running --auto-yes overwrite..."
(
  cd "$ROOT_DIR"
  HOME="$AUTO_YES_HOME" \
  bash setup.sh --install-only --yes >"$AUTO_YES_OUT" 2>"$AUTO_YES_ERR"
)

grep -q "AUTO_YES=true -> overwriting existing Goose config" "$AUTO_YES_OUT"
if grep -q "ANGELLA_LOCAL_WORKER_BACKEND=mlx" "$AUTO_YES_HOME/.config/goose/config.yaml"; then
  # If MLX env was present in the test environment, it might have been rendered
  ! grep -REq '__ANGELLA_ROOT__|__PYTHON_CMD__|__RENDERED_RECIPE_PATH__|__ANGELLA_MLX_BASE_URL__' "$AUTO_YES_HOME/.config/goose"
else
  ! grep -REq '__ANGELLA_ROOT__|__PYTHON_CMD__|__RENDERED_RECIPE_PATH__' "$AUTO_YES_HOME/.config/goose"
fi

grep -qE "Goose config (installed to|updated)" "$AUTO_YES_OUT"
grep -q "Rendered recipe installed to" "$AUTO_YES_OUT"

echo "setup flow tests passed"
