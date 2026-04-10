#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TMP_MATCHES="$(mktemp)"
trap 'rm -f "$TMP_MATCHES"' EXIT

PATTERN='AIza[0-9A-Za-z_-]{35}|ghp_[A-Za-z0-9]{36}|gho_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{20,}|BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY|OPENAI_API_KEY[[:space:]]*=[[:space:]]*[^[:space:]]+|GOOGLE_API_KEY[[:space:]]*=[[:space:]]*[^[:space:]]+|ANTHROPIC_API_KEY[[:space:]]*=[[:space:]]*[^[:space:]]+|AWS_SECRET_ACCESS_KEY[[:space:]]*=[[:space:]]*[^[:space:]]+'

cd "$ROOT_DIR"

if command -v rg >/dev/null 2>&1; then
  rg -n --hidden \
    --glob '!.git/**' \
    --glob '!.config/**' \
    --glob '!.cache/**' \
    --glob '!logs/**' \
    --glob '!__pycache__/**' \
    --glob '!*.pyc' \
    --glob '!*.example' \
    --glob '!.env*' \
    --glob '!scripts/setup-vault.sh' \
    --glob '!scripts/test_setup_flows.sh' \
    --glob '!*.sample' \
    --glob '!*.md' \
    "$PATTERN" . >"$TMP_MATCHES" || true
else
  grep -RInE \
    --exclude-dir=.git \
    --exclude-dir=.config \
    --exclude-dir=.cache \
    --exclude-dir=logs \
    --exclude-dir=__pycache__ \
    --exclude='*.pyc' \
    --exclude='*.example' \
    --exclude='.env*' \
    --exclude='setup-vault.sh' \
    --exclude='scripts/test_setup_flows.sh' \
    --exclude='*.sample' \
    --exclude='*.md' \
    "$PATTERN" . >"$TMP_MATCHES" || true
fi

if [ -s "$TMP_MATCHES" ]; then
  echo "Potential secret material detected:"
  cat "$TMP_MATCHES"
  exit 1
fi

echo "No secret patterns detected."
