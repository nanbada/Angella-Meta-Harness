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
{"models":[{"name":"qwen2.5-coder:32b"},{"name":"gemma4:26b"}]}
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

chmod +x "$FAKE_BIN/brew" "$FAKE_BIN/goose" "$FAKE_BIN/ollama" "$FAKE_BIN/curl" "$FAKE_BIN/python3"

CHECK_HOME="$TMP_ROOT/home-check"
YES_HOME="$TMP_ROOT/home-yes"
mkdir -p "$CHECK_HOME" "$YES_HOME"

export PATH="$FAKE_BIN:$PATH"

CHECK_OUT="$TMP_ROOT/check.out"
CHECK_ERR="$TMP_ROOT/check.err"

(
  cd "$ROOT_DIR"
  HOME="$CHECK_HOME" bash setup.sh --check >"$CHECK_OUT" 2>"$CHECK_ERR"
)

grep -q "Template rendering checks passed" "$CHECK_OUT"
grep -q "Model 'qwen2.5-coder:32b' already pulled" "$CHECK_OUT"
grep -q "Model 'gemma4:26b' already pulled" "$CHECK_OUT"

YES_OUT="$TMP_ROOT/yes.out"
YES_ERR="$TMP_ROOT/yes.err"

(
  cd "$ROOT_DIR"
  HOME="$YES_HOME" bash setup.sh --yes >"$YES_OUT" 2>"$YES_ERR"
)

test -f "$YES_HOME/.config/goose/config.yaml"
test -f "$YES_HOME/.config/goose/recipes/autoresearch-loop.yaml"
test -f "$YES_HOME/.config/goose/recipes/sub/code-optimize.yaml"
test -f "$YES_HOME/.config/goose/recipes/sub/evaluate-metric.yaml"
test -d "$ROOT_DIR/logs/Goose Logs"

if command -v rg >/dev/null 2>&1; then
  ! rg -q '__ANGELLA_ROOT__|__PYTHON_CMD__|__RENDERED_RECIPE_PATH__' "$YES_HOME/.config/goose"
else
  ! grep -REq '__ANGELLA_ROOT__|__PYTHON_CMD__|__RENDERED_RECIPE_PATH__' "$YES_HOME/.config/goose"
fi

grep -q "Goose config installed to" "$YES_OUT"
grep -q "Rendered recipe installed to" "$YES_OUT"

echo "setup flow tests passed"
