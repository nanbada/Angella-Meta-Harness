#!/usr/bin/env python3
"""Smoke checks for benchmark adapters and harness-self-optimize recipe wiring."""

from __future__ import annotations

import asyncio
import json
import os
import importlib.util
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
BOOTSTRAP_PYTHON = ROOT_DIR / ".cache" / "angella" / "bootstrap-venv" / "bin" / "python"

if importlib.util.find_spec("mcp") is None and BOOTSTRAP_PYTHON.exists():
    current = Path(sys.executable).resolve()
    target = BOOTSTRAP_PYTHON.resolve()
    if current != target:
        os.execv(str(target), [str(target), __file__, *sys.argv[1:]])

sys.path.insert(0, str(ROOT_DIR / "mcp-servers"))

import metric_benchmark  # noqa: E402
import metric_benchmark_python  # noqa: E402
from meta_loop_ops import harness_component_context  # noqa: E402


def _payload(contents) -> dict:
    return json.loads(contents[0].text)


async def main() -> int:
    generic = _payload(
        await metric_benchmark.call_tool(
            "run_benchmark",
            {
                "command": "python3 -c \"print('build time: 0.05 s')\"",
                "metric_key": "build_time",
                "working_directory": str(ROOT_DIR),
                "timeout_seconds": 30,
            },
        )
    )
    assert generic["success"] is True
    assert generic["metric_key"] == "build_time"
    assert generic["metric_value"] > 0

    python_payload = _payload(
        await metric_benchmark_python.call_tool(
            "run_benchmark",
            {
                "command": "python3 -c \"print('tokens/s: 42')\"",
                "metric_key": "tokens_per_second",
                "working_directory": str(ROOT_DIR),
                "runs": 1,
                "timeout_seconds": 30,
            },
        )
    )
    assert python_payload["success"] is True
    assert python_payload["metric_key"] == "tokens_per_second"
    assert python_payload["metric_value"] == 42.0

    recipe_runtime = harness_component_context("recipe-runtime")
    assert recipe_runtime["metric_key"] == "build_time"
    assert recipe_runtime["benchmark_command"].endswith(" scripts/test_harness_self_optimize_adapter.py")
    assert ".cache/angella/bootstrap-venv/bin/python" in recipe_runtime["benchmark_command"]
    assert "mcp-servers/meta_loop_ops.py" in recipe_runtime["priority_files"]
    assert recipe_runtime["success_signal"]
    assert recipe_runtime["allowed_fix_surface"]

    profile_resolution = harness_component_context("profile-resolution")
    assert profile_resolution["benchmark_command"].endswith(" scripts/harness_catalog.py list-profiles")
    assert profile_resolution["success_signal"]
    assert profile_resolution["allowed_fix_surface"]
    legacy_python = Path("/usr/bin/python3")
    if legacy_python.exists():
        subprocess.run(
            [str(legacy_python), str(ROOT_DIR / "scripts" / "harness_catalog.py"), "list-profiles"],
            cwd=str(ROOT_DIR),
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    recipe_text = (ROOT_DIR / "recipes" / "harness-self-optimize.yaml").read_text(encoding="utf-8")
    assert "name: metric-benchmark" in recipe_text
    assert "name: control-plane-admin" in recipe_text
    assert "finalize_accepted_meta_loop_run" in recipe_text
    assert "inspect_control_plane" in recipe_text
    assert "search_harness_knowledge" in recipe_text
    assert "describe_harness_component" in recipe_text
    assert "format=markdown" in recipe_text
    assert "record_verification_only_run" in recipe_text
    assert "knowledge/sops/" in recipe_text
    assert "knowledge/skills/" in recipe_text

    print("harness self-optimize adapter tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
