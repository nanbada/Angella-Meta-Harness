#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DEST_DIR="${1:-$ROOT_DIR/vendor/wheels}"

mkdir -p "$DEST_DIR"

if command -v uv >/dev/null 2>&1; then
    uv pip download -r "$ROOT_DIR/mcp-servers/requirements.txt" --dest "$DEST_DIR"
else
    python3 -m pip download -r "$ROOT_DIR/mcp-servers/requirements.txt" -d "$DEST_DIR"
fi

echo "Wheelhouse populated at $DEST_DIR"
