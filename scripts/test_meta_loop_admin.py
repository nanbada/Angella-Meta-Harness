#!/usr/bin/env python3
"""Validate retired meta-loop surfaces remain inactive and docs are aligned."""

from __future__ import annotations

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def main() -> int:
    # Verify legacy Goose configuration files are removed
    assert not (ROOT_DIR / "config" / "goose-config.yaml").exists(), "Legacy goose-config.yaml should be removed"
    assert not (ROOT_DIR / ".goosehints").exists(), "Legacy .goosehints should be removed"

    # We keep the MCP servers for now but they should be decoupled from Goose
    assert (ROOT_DIR / "mcp-servers" / "meta_loop_ops.py").exists()
    assert (ROOT_DIR / "mcp-servers" / "control_plane_admin.py").exists()

    parity_text = (ROOT_DIR / "docs" / "PARITY.md").read_text(encoding="utf-8")
    assert "Canonical document: `docs/PARITY.md`" in parity_text
    assert "scripts/run_harness_parity_diff.py" in parity_text
    assert "Lane 7 — dedicated agent specialized delegation" in parity_text
    assert "Lane 6 — google scion coordination (file-backed mvp)" in parity_text

    arch_text = (ROOT_DIR / "docs" / "arch-snapshot.md").read_text(encoding="utf-8")
    assert "Meta-Harness" in arch_text
    assert "knowledge/" in arch_text
    assert "Brains" in arch_text
    assert "Hands" in arch_text
    assert "archivist_ops.py" in arch_text
    assert "project-vars.json" in arch_text

    print("meta-loop admin removal checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
