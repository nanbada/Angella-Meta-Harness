#!/usr/bin/env bash
# ============================================================
# Angella Satellite Init Script
# Usage: ./scripts/setup-satellite.sh <target_project_path>
# ============================================================

set -euo pipefail

ANGELLA_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET_DIR="${1:-}"

if [[ -z "$TARGET_DIR" ]]; then
    echo "Usage: $0 <target_project_path>"
    exit 1
fi

TARGET_DIR="$(cd "$TARGET_DIR" && pwd)"
echo "🚀 Initializing Angella Satellite Harness at: $TARGET_DIR"

# 1. Create directory structure
mkdir -p "$TARGET_DIR/.gemini/agents"
mkdir -p "$TARGET_DIR/scripts"
mkdir -p "$TARGET_DIR/telemetry/logs"

# 2. Copy core instructions (Intelligence)
cp "$ANGELLA_ROOT/GEMINI.md" "$TARGET_DIR/"
cp "$ANGELLA_ROOT/.gemini/agents/"*.md "$TARGET_DIR/.gemini/agents/"

# 3. Create repo-checks.sh template (Relentless Loop Anchor)
if [[ ! -f "$TARGET_DIR/scripts/repo-checks.sh" ]]; then
    cat > "$TARGET_DIR/scripts/repo-checks.sh" <<EOF
#!/usr/bin/env bash
# Angella Relentless Loop Verification Script
# Exit with 0 if all checks pass, non-zero otherwise.

set -e

echo "Running project-specific checks..."
# Add your commands here, e.g.:
# npm test
# pytest
# flake8 .

echo "✅ All checks passed!"
EOF
    chmod +x "$TARGET_DIR/scripts/repo-checks.sh"
fi

# 4. Create .env.angella for the target project
cat > "$TARGET_DIR/.env.angella" <<EOF
# Angella Satellite Config
export ANGELLA_ROOT="$ANGELLA_ROOT"
# Use the same Python environment as Angella
export PYTHONPATH="\$ANGELLA_ROOT/mcp-servers:\$ANGELLA_ROOT/mcp-servers/utils:\$PYTHONPATH"
EOF

echo ""
echo "✅ Satellite Harness Initialized!"
echo "--------------------------------------------------------"
echo "Next steps for your project at $TARGET_DIR:"
echo "1. Edit scripts/repo-checks.sh to fit your build/test flow."
echo "2. Run 'source .env.angella' to link with Angella core."
echo "3. Use 'gemini' command to start optimizing your project!"
echo "--------------------------------------------------------"
