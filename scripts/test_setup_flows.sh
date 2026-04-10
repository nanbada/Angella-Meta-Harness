#!/usr/bin/env bash
set -euo pipefail

if [[ "${GITHUB_ACTIONS:-}" == "true" ]]; then
  set -x
fi

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TMP_ROOT="$(mktemp -d)"
trap 'rm -rf "$TMP_ROOT"' EXIT

VARS_JSON="$ROOT_DIR/config/project-vars.json"
PYTHON_BIN=$(command -v python3 || command -v python)
MLX_MODEL_ID=$($PYTHON_BIN -c "import json; print(json.load(open('$VARS_JSON'))['MLX_MODEL_ID'])")
MLX_MODEL_NAME=$($PYTHON_BIN -c "import json; print(json.load(open('$VARS_JSON'))['MLX_MODEL_NAME'])")
OLLAMA_MODEL_ID=$($PYTHON_BIN -c "import json; print(json.load(open('$VARS_JSON'))['OLLAMA_MODEL_ID'])")
OLLAMA_MODEL_NAME=$($PYTHON_BIN -c "import json; print(json.load(open('$VARS_JSON'))['OLLAMA_MODEL_NAME'])")

FAKE_BIN="$TMP_ROOT/bin"
mkdir -p "$FAKE_BIN"

# Diagnostic checks
echo "DEBUG: PATH=$PATH"
echo "DEBUG: python3=$(command -v python3 || echo 'not found')"
echo "DEBUG: python=$(command -v python || echo 'not found')"
echo "DEBUG: ROOT_DIR=$ROOT_DIR"

# --- Mocking binaries ---
REAL_CURL=$(command -v curl || echo "/usr/bin/curl")
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
exec "$REAL_CURL" "\$@"
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

fail_test() {
  local msg=$1
  echo -e "\n[ERROR] $msg" >&2
  echo "--- ENVIRONMENT (ANGELLA_*) ---"
  env | grep ANGELLA || true
  echo "--- DIRECTORY STRUCTURE ($TMP_ROOT) ---"
  ls -R "$TMP_ROOT"
  if [ -f "$TMP_ROOT/check.out" ]; then echo "--- check.out ---"; cat "$TMP_ROOT/check.out"; fi
  if [ -f "$TMP_ROOT/check.err" ]; then echo "--- check.err ---"; cat "$TMP_ROOT/check.err"; fi
  if [ -f "$TMP_ROOT/models.out" ]; then echo "--- models.out ---"; cat "$TMP_ROOT/models.out"; fi
  if [ -f "$TMP_ROOT/profiles.out" ]; then echo "--- profiles.out ---"; cat "$TMP_ROOT/profiles.out"; fi
  if [ -f "$TMP_ROOT/mlx-models.out" ]; then echo "--- mlx-models.out ---"; cat "$TMP_ROOT/mlx-models.out"; fi
  if [ -f "$TMP_ROOT/mlx-profiles.out" ]; then echo "--- mlx-profiles.out ---"; cat "$TMP_ROOT/mlx-profiles.out"; fi
  exit 1
}

log_step() {
  echo "[TEST] $(date '+%Y-%m-%d %H:%M:%S') $1"
}

log_step "Starting setup flow tests..."

CHECK_OUT="$TMP_ROOT/check.out"
CHECK_ERR="$TMP_ROOT/check.err"

log_step "Running setup --check..."
(
  cd "$ROOT_DIR"
  HOME="$CHECK_HOME" bash setup.sh --check >"$CHECK_OUT" 2>"$CHECK_ERR"
) || fail_test "setup --check failed"

grep -q "Template rendering checks passed" "$CHECK_OUT" || fail_test "missing expected success message in check.out"

MODELS_OUT="$TMP_ROOT/models.out"
log_step "Listing models..."
(
  cd "$ROOT_DIR"
  HOME="$CHECK_HOME" bash setup.sh --list-models >"$MODELS_OUT" 2>&1
) || fail_test "setup --list-models failed"
grep -q "google_gemini_2_5_pro" "$MODELS_OUT" || fail_test "google_gemini_2_5_pro missing in models list"
grep -q "$OLLAMA_MODEL_ID" "$MODELS_OUT" || fail_test "$OLLAMA_MODEL_ID missing in models list"
grep -q "openai_gpt_5_2_pro: roles=lead,planner,worker" "$MODELS_OUT" || fail_test "openai_gpt_5_2_pro missing or incorrect roles"
grep -q "$MLX_MODEL_ID: .*ANGELLA_LOCAL_WORKER_BACKEND=mlx" "$MODELS_OUT" || fail_test "MLX model backend info missing"
grep -q "$MLX_MODEL_ID: .*ANGELLA_MLX_BASE_URL" "$MODELS_OUT" || fail_test "MLX model base URL info missing"

MLX_MODELS_OUT="$TMP_ROOT/mlx-models.out"
log_step "Listing MLX models..."
(
  cd "$ROOT_DIR"
  HOME="$CHECK_HOME" \
  ANGELLA_LOCAL_WORKER_BACKEND=mlx \
  ANGELLA_MLX_BASE_URL=http://127.0.0.1:11435/v1 \
  ANGELLA_MLX_MODEL=$MLX_MODEL_NAME \
  ANGELLA_MLX_HEALTHCHECK_OK=1 \
  bash setup.sh --list-models >"$MLX_MODELS_OUT" 2>&1
) || fail_test "setup --list-models with MLX env failed"
grep -q "$MLX_MODEL_ID: .*provider=angella_mlx_local" "$MLX_MODELS_OUT" || fail_test "MLX provider info missing in list"
grep -q "$MLX_MODEL_ID: .*status=enabled" "$MLX_MODELS_OUT" || fail_test "MLX status not enabled"

PROFILES_OUT="$TMP_ROOT/profiles.out"
log_step "Listing harness profiles..."
(
  cd "$ROOT_DIR"
  HOME="$CHECK_HOME" bash setup.sh --list-harness-profiles >"$PROFILES_OUT" 2>&1
) || fail_test "setup --list-harness-profiles failed"
grep -q "frontier_default: .*worker=openai_gpt_5_2" "$PROFILES_OUT" || fail_test "frontier_default missing or incorrect worker"
grep -q "local_lab: .*worker=$OLLAMA_MODEL_ID" "$PROFILES_OUT" || fail_test "local_lab missing or incorrect worker"

MLX_PROFILES_OUT="$TMP_ROOT/mlx-profiles.out"
log_step "Listing MLX harness profiles..."
(
  cd "$ROOT_DIR"
  HOME="$CHECK_HOME" \
  ANGELLA_LOCAL_WORKER_BACKEND=mlx \
  ANGELLA_MLX_BASE_URL=http://127.0.0.1:11435/v1 \
  ANGELLA_MLX_MODEL=$MLX_MODEL_NAME \
  ANGELLA_MLX_HEALTHCHECK_OK=1 \
  ANGELLA_OLLAMA_TAGS_JSON="" \
  bash setup.sh --list-harness-profiles >"$MLX_PROFILES_OUT" 2>&1
) || fail_test "setup --list-harness-profiles with MLX env failed"
grep -q "local_lab: .*worker=$MLX_MODEL_ID" "$MLX_PROFILES_OUT" || fail_test "local_lab failed to resolve to MLX worker"

log_step "Checking legacy profile error..."
LEGACY_PROFILE_ERR="$TMP_ROOT/legacy-profile.err"
if (
  cd "$ROOT_DIR"
  HOME="$CHECK_HOME" bash setup.sh --check --harness-profile default >/dev/null 2>"$LEGACY_PROFILE_ERR"
); then
  fail_test "legacy profile unexpectedly succeeded"
fi
grep -q 'Legacy harness profile `default` has been removed' "$LEGACY_PROFILE_ERR" || fail_test "incorrect error message for legacy profile"

MLX_CHECK_OUT="$TMP_ROOT/mlx-check.out"
MLX_CHECK_ERR="$TMP_ROOT/mlx-check.err"
log_step "Checking MLX worker resolution..."
(
  cd "$ROOT_DIR"
  HOME="$CHECK_HOME" \
  ANGELLA_LOCAL_WORKER_BACKEND=mlx \
  ANGELLA_MLX_BASE_URL=http://127.0.0.1:11435/v1 \
  ANGELLA_MLX_MODEL=$MLX_MODEL_NAME \
  ANGELLA_MLX_HEALTHCHECK_OK=1 \
  bash setup.sh --check --worker-model $MLX_MODEL_ID >"$MLX_CHECK_OUT" 2>"$MLX_CHECK_ERR"
) || fail_test "setup --check with MLX worker override failed"
grep -q "Template rendering checks passed" "$MLX_CHECK_OUT" || fail_test "MLX check output missing success message"
grep -q "worker: angella_mlx_local/$MLX_MODEL_NAME" "$MLX_CHECK_OUT" || fail_test "MLX worker resolution mismatch"

MLX_FAIL_ERR="$TMP_ROOT/mlx-fail.err"
log_step "Checking MLX worker failure..."
if (
  cd "$ROOT_DIR"
  HOME="$CHECK_HOME" \
  ANGELLA_LOCAL_WORKER_BACKEND=mlx \
  ANGELLA_MLX_BASE_URL=http://127.0.0.1:11435/v1 \
  ANGELLA_MLX_MODEL=$MLX_MODEL_NAME \
  ANGELLA_MLX_HEALTHCHECK_OK=0 \
  bash setup.sh --check --worker-model $MLX_MODEL_ID >/dev/null 2>"$MLX_FAIL_ERR"
); then
  fail_test "mlx worker check unexpectedly succeeded"
fi
grep -q 'ANGELLA_LOCAL_WORKER_BACKEND=mlx and ANGELLA_MLX_BASE_URL' "$MLX_FAIL_ERR" || fail_test "missing MLX specific error message on failure"

OLLAMA_CHECK_OUT="$TMP_ROOT/ollama-check.out"
OLLAMA_CHECK_ERR="$TMP_ROOT/ollama-check.err"
log_step "Checking Ollama worker resolution..."
(
  cd "$ROOT_DIR"
  HOME="$CHECK_HOME" bash setup.sh --check --worker-model $OLLAMA_MODEL_ID >"$OLLAMA_CHECK_OUT" 2>"$OLLAMA_CHECK_ERR"
) || fail_test "setup --check with Ollama worker override failed"
grep -q "worker: ollama/$OLLAMA_MODEL_NAME" "$OLLAMA_CHECK_OUT" || fail_test "Ollama worker resolution mismatch"
if ! grep -q "existing .env.mlx detected" "$OLLAMA_CHECK_OUT"; then
  grep -q "cp $ROOT_DIR/.env.mlx.example $ROOT_DIR/.env.mlx" "$OLLAMA_CHECK_OUT" || fail_test "missing .env.mlx creation instruction"
fi

BOOTSTRAP_OUT="$TMP_ROOT/bootstrap.out"
BOOTSTRAP_ERR="$TMP_ROOT/bootstrap.err"

log_step "Running --bootstrap-only..."
(
  cd "$ROOT_DIR"
  HOME="$BOOTSTRAP_HOME" bash setup.sh --bootstrap-only >"$BOOTSTRAP_OUT" 2>"$BOOTSTRAP_ERR"
) || fail_test "setup --bootstrap-only failed"

test -f "$ANGELLA_CACHE_DIR/bootstrap.env" || fail_test "bootstrap.env not created"
test -f "$ANGELLA_CACHE_DIR/bootstrap-venv/bin/python" || fail_test "bootstrap venv python not found"
grep -q "ANGELLA_HARNESS_PROFILE_ID=.*frontier_default" "$ANGELLA_CACHE_DIR/bootstrap.env" || fail_test "incorrect profile in bootstrap.env"
grep -q "ANGELLA_EXECUTION_MODE=.*frontier_primary" "$ANGELLA_CACHE_DIR/bootstrap.env" || fail_test "incorrect mode in bootstrap.env"
grep -q "Bootstrap Complete" "$BOOTSTRAP_OUT" || fail_test "missing Bootstrap Complete message"

INSTALL_OUT="$TMP_ROOT/install.out"
INSTALL_ERR="$TMP_ROOT/install.err"

log_step "Running --install-only..."
(
  cd "$ROOT_DIR"
  HOME="$INSTALL_HOME" bash setup.sh --install-only >"$INSTALL_OUT" 2>"$INSTALL_ERR"
) || fail_test "setup --install-only failed"

test -f "$INSTALL_HOME/.config/goose/config.yaml" || fail_test "goose config.yaml not installed"
test -f "$INSTALL_HOME/.config/goose/recipes/autoresearch-loop.yaml" || fail_test "recipe not installed"
test -f "$ANGELLA_CACHE_DIR/control-plane/install/summary.json" || fail_test "install summary.json not found"
test -f "$ANGELLA_CACHE_DIR/control-plane/install/telemetry.jsonl" || fail_test "telemetry.jsonl not found"
grep -q '"rendered_hashes"' "$ANGELLA_CACHE_DIR/control-plane/install/summary.json" || fail_test "hashes missing in summary"
grep -q '"overwrite_mode": "installed_new"' "$ANGELLA_CACHE_DIR/control-plane/install/summary.json" || fail_test "incorrect overwrite_mode in summary"
grep -q "Setup Complete" "$INSTALL_OUT" || fail_test "missing Setup Complete message"

MLX_INSTALL_HOME="$TMP_ROOT/home-install-mlx"
mkdir -p "$MLX_INSTALL_HOME"
MLX_INSTALL_OUT="$TMP_ROOT/install-mlx.out"
MLX_INSTALL_ERR="$TMP_ROOT/install-mlx.err"
log_step "Running MLX --install-only..."
(
  cd "$ROOT_DIR"
  HOME="$MLX_INSTALL_HOME" \
  ANGELLA_LOCAL_WORKER_BACKEND=mlx \
  ANGELLA_MLX_BASE_URL=http://127.0.0.1:11435/v1 \
  ANGELLA_MLX_MODEL=$MLX_MODEL_NAME \
  ANGELLA_MLX_HEALTHCHECK_OK=1 \
  bash setup.sh --install-only --worker-model $MLX_MODEL_ID --yes >"$MLX_INSTALL_OUT" 2>"$MLX_INSTALL_ERR"
) || fail_test "setup --install-only for MLX failed"
test -f "$MLX_INSTALL_HOME/.config/goose/custom_providers/angella_mlx_local.json" || fail_test "MLX custom provider config not installed"
grep -q '"base_url": "http://127.0.0.1:11435/v1"' "$MLX_INSTALL_HOME/.config/goose/custom_providers/angella_mlx_local.json" || fail_test "MLX base_url mismatch"
grep -q "\"model\": \"$MLX_MODEL_NAME\"" "$MLX_INSTALL_HOME/.config/goose/custom_providers/angella_mlx_local.json" || fail_test "MLX model mismatch"
grep -q "GOOSE_MODEL: \"$MLX_MODEL_NAME\"" "$MLX_INSTALL_HOME/.config/goose/config.yaml" || fail_test "Goose config not updated for MLX"

AUTO_YES_HOME="$TMP_ROOT/home-auto-yes-overwrite"
mkdir -p "$AUTO_YES_HOME/.config/goose/recipes"
cat >"$AUTO_YES_HOME/.config/goose/config.yaml" <<'EOF'
GOOSE_PROVIDER: "openai"
GOOSE_MODEL: "gpt-4"
EOF

AUTO_YES_OUT="$TMP_ROOT/auto-yes.out"
AUTO_YES_ERR="$TMP_ROOT/auto-yes.err"
log_step "Running --auto-yes overwrite..."
(
  cd "$ROOT_DIR"
  HOME="$AUTO_YES_HOME" \
  bash setup.sh --install-only --yes >"$AUTO_YES_OUT" 2>"$AUTO_YES_ERR"
) || fail_test "setup --install-only with --yes failed"

grep -q "AUTO_YES=true -> overwriting existing Goose config" "$AUTO_YES_OUT" || fail_test "missing overwrite confirmation message"
if grep -q "ANGELLA_LOCAL_WORKER_BACKEND=mlx" "$AUTO_YES_HOME/.config/goose/config.yaml"; then
  # If MLX env was present in the test environment, it might have been rendered
  ! grep -REq '__ANGELLA_ROOT__|__PYTHON_CMD__|__RENDERED_RECIPE_PATH__|__ANGELLA_MLX_BASE_URL__' "$AUTO_YES_HOME/.config/goose" || fail_test "unresolved placeholders in overwritten config (MLX mode)"
else
  ! grep -REq '__ANGELLA_ROOT__|__PYTHON_CMD__|__RENDERED_RECIPE_PATH__' "$AUTO_YES_HOME/.config/goose" || fail_test "unresolved placeholders in overwritten config"
fi

grep -qE "Goose config (installed to|updated)" "$AUTO_YES_OUT" || fail_test "missing config installation confirmation"
grep -q "Rendered recipe installed to" "$AUTO_YES_OUT" || fail_test "missing recipe installation confirmation"

log_step "setup flow tests passed"
