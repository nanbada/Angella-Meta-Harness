#!/usr/bin/env python3
"""Regression checks for the safe MLX runtime probe."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "scripts"))

import check_mlx_runtime  # noqa: E402


def main() -> int:
    success = check_mlx_runtime.run_probe(
        sys.executable,
        probe_code='import json; print(json.dumps({"mlx":"stub-mlx","mlx_lm":"stub-mlx-lm"}))',
    )
    assert success["success"] is True
    assert success["versions"]["mlx"] == "stub-mlx"
    assert success["versions"]["mlx_lm"] == "stub-mlx-lm"
    assert "succeeded" in check_mlx_runtime.format_probe_report(success)

    missing = check_mlx_runtime.run_probe("/tmp/angella-missing-python")
    assert missing["success"] is False
    assert missing["category"] == "python_missing"

    crash = check_mlx_runtime.run_probe(
        sys.executable,
        probe_code='import sys; sys.stderr.write("NSRangeException Metal device init\\n"); raise SystemExit(134)',
    )
    assert crash["success"] is False
    assert crash["category"] == "metal_device_init_crash"
    assert "sandbox or Metal device visibility" in crash["hint"]

    invalid = check_mlx_runtime.run_probe(
        sys.executable,
        probe_code='print("not-json")',
    )
    assert invalid["success"] is False
    assert invalid["category"] == "invalid_probe_output"

    print("mlx runtime probe tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
