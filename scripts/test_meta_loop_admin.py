#!/usr/bin/env python3
"""Validate retired meta-loop surfaces remain inactive and docs are aligned."""

from __future__ import annotations

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def main() -> int:
    # We no longer assert the absence of these files as they are maintained for transparency
    # assert not (ROOT_DIR / "mcp-servers" / "meta_loop_ops.py").exists()
    # assert not (ROOT_DIR / "mcp-servers" / "control_plane_admin.py").exists()
    # assert not (ROOT_DIR / "recipes" / "harness-self-optimize.yaml").exists()

    goose_text = (ROOT_DIR / "config" / "goose-config.yaml").read_text(encoding="utf-8")
    assert "control-plane-admin" not in goose_text
    assert "control_plane_admin.py" not in goose_text
    assert "meta_loop_ops" not in goose_text

    goosehints_text = (ROOT_DIR / ".goosehints").read_text(encoding="utf-8")
    assert "1. `GEMINI.md`" in goosehints_text
    assert "2. `README.md`" in goosehints_text
    assert "3. `docs/arch-snapshot.md`" in goosehints_text
    assert "4. `plan.md`" in goosehints_text

    assert "meta_loop_ops.py" in goosehints_text
    assert "control_plane_admin.py" in goosehints_text
    assert "harness-self-optimize.yaml" in goosehints_text
    assert "참조하지 마세요" in goosehints_text

    parity_text = (ROOT_DIR / "docs" / "PARITY.md").read_text(encoding="utf-8")
    assert "Canonical document: `docs/PARITY.md`" in parity_text
    assert "scripts/run_harness_parity_diff.py" in parity_text
    assert "Lane 7 — retired meta-loop/control-plane surface removed" in parity_text
    assert "Lane 6 — google scion coordination (file-backed mvp)" in parity_text

    arch_text = (ROOT_DIR / "docs" / "arch-snapshot.md").read_text(encoding="utf-8")
    assert "Personal Agent & LLM-Wiki" in arch_text
    assert "knowledge/" in arch_text
    assert "sources/" in arch_text
    assert "archivist_ops.py" in arch_text
    assert "project-vars.json" in arch_text

    print("meta-loop admin removal checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
