#!/usr/bin/env python3
"""Regression checks for retired meta-loop surface removal and v2 docs."""

from __future__ import annotations

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent


def main() -> int:
    assert not (ROOT_DIR / "mcp-servers" / "meta_loop_ops.py").exists()
    assert not (ROOT_DIR / "mcp-servers" / "control_plane_admin.py").exists()
    assert not (ROOT_DIR / "recipes" / "harness-self-optimize.yaml").exists()

    goose_text = (ROOT_DIR / "config" / "goose-config.yaml").read_text(encoding="utf-8")
    assert "control-plane-admin" not in goose_text
    assert "control_plane_admin.py" not in goose_text
    assert "meta_loop_ops" not in goose_text

    goosehints_text = (ROOT_DIR / ".goosehints").read_text(encoding="utf-8")
    assert "README.md" in goosehints_text
    assert "docs/arch-snapshot.md" in goosehints_text
    assert "plan.md" in goosehints_text
    assert "docs/spec-contracts.md" in goosehints_text
    assert "knowledge/sops/harness-philosophy.md" in goosehints_text
    assert "meta_loop_ops.py" in goosehints_text
    assert "control_plane_admin.py" in goosehints_text
    assert "harness-self-optimize.yaml" in goosehints_text
    assert "참조하지 마세요" in goosehints_text

    parity_text = (ROOT_DIR / "docs" / "PARITY.md").read_text(encoding="utf-8")
    assert "Canonical document: `docs/PARITY.md`" in parity_text
    assert "scripts/run_harness_parity_diff.py" in parity_text
    assert "retired on 2026-04-07" in parity_text
    assert "Lane 7 — retired meta-loop/control-plane surface removed" in parity_text
    assert "Lane 6 — google scion coordination (file-backed mvp)" in parity_text

    arch_text = (ROOT_DIR / "docs" / "arch-snapshot.md").read_text(encoding="utf-8")
    assert "file-backed coordination MVP" in arch_text
    assert "공유 wiki 저장소 (현재 repo 내부 디렉터리)" in arch_text
    assert "다른 프로젝트와 외부 채널" in arch_text
    assert "다시 외부 경로 symlink로 바꿀 수" in arch_text
    assert "ANGELLA_LOCAL_WORKER_BACKEND=mlx" in arch_text or "ANGELLA_LOCAL_WORKER_BACKEND" in arch_text

    mlx_guide = (ROOT_DIR / "docs" / "setup-gemma4-mlx.md").read_text(encoding="utf-8")
    assert "ANGELLA_LOCAL_WORKER_BACKEND=mlx" in mlx_guide
    assert "ANGELLA_MLX_BASE_URL" in mlx_guide
    assert "ANGELLA_MLX_MODEL" in mlx_guide
    assert "angella_mlx_local" in mlx_guide
    assert "git checkout codex/gemma4-default-finalize-meta-loop" not in mlx_guide
    assert "config/harness-models.yaml" in mlx_guide
    assert "수동 편집할 필요가 없습니다" in mlx_guide

    roadmap_text = (ROOT_DIR / "plan.md").read_text(encoding="utf-8")
    assert "Phase 7 (진행 중)" in roadmap_text
    assert "file-backed coordination MVP" in roadmap_text

    print("meta loop admin tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
