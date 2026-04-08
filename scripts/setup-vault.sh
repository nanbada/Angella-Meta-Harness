#!/usr/bin/env bash

# Angella Secure Vault Setup for Personal Agents
# Generates a unified .env.agents file to safely orchestrate multiple provider tiers.

set -euo pipefail

VAULT_FILE=".env.agents"

echo "============================================="
echo " Angella Personal Agent - Vault Generator "
echo "============================================="
echo "This script safely configures your API keys for the Multi-Tier harness."
echo "Your keys will be saved to ${VAULT_FILE} (which is ignored by Git)."
echo ""

prompt_for_key() {
    local provider=$1
    local env_var=$2
    local current_val=""

    if [ -f "$VAULT_FILE" ]; then
        current_val=$(grep "^${env_var}=" "$VAULT_FILE" | cut -d '=' -f 2- || true)
    fi

    if [ -n "$current_val" ]; then
        echo "[$provider] Key is already configured. Press Enter to keep it, or paste a new one:"
    else
        echo "[$provider] Please enter your API key (or press Enter to skip):"
    fi

    local input
    read -r -s input

    if [ -n "$input" ]; then
        echo "$input"
    else
        echo "$current_val"
    fi
}

GOOGLE_API_KEY=$(prompt_for_key "Google Gemini" "GOOGLE_API_KEY")
echo ""
ANTHROPIC_API_KEY=$(prompt_for_key "Anthropic Claude" "ANTHROPIC_API_KEY")
echo ""
OPENAI_API_KEY=$(prompt_for_key "OpenAI" "OPENAI_API_KEY")
echo ""

echo "Saving configurations to ${VAULT_FILE}..."

cat > "$VAULT_FILE" << EOF
# Angella Vault - DO NOT COMMIT THIS FILE
GOOGLE_API_KEY=${GOOGLE_API_KEY}
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
OPENAI_API_KEY=${OPENAI_API_KEY}
EOF

# Ensure restricted permissions
chmod 600 "$VAULT_FILE"

echo "Vault generation complete. Access restricted to current user."
echo "You can now run Goose using: source ${VAULT_FILE} && goose run ..."
echo "============================================="
