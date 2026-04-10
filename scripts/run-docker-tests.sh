#!/usr/bin/env bash
# ============================================================
# Angella — Dockerized CI Test Runner
# ============================================================
# This script builds and runs the test suite in an Ubuntu 24.04
# container to ensure absolute parity with GitHub Actions.
# ============================================================

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
IMAGE_NAME="angella-ci-test"

echo "[DOCKER] Building CI replication image..."
docker build -t "$IMAGE_NAME" -f "$ROOT_DIR/Dockerfile.test" "$ROOT_DIR"

echo "[DOCKER] Running tests in Ubuntu 24.04 container..."
docker run --rm "$IMAGE_NAME"

echo ""
echo "[OK] Dockerized tests passed. Environment parity verified."
