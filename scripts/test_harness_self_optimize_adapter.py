#!/usr/bin/env python3
"""Smoke checks for current benchmark adapters and v2 recipe wiring."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
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

    autoresearch_text = (ROOT_DIR / "recipes" / "autoresearch-loop.yaml").read_text(encoding="utf-8")
    personal_text = (ROOT_DIR / "recipes" / "personal-agent-loop.yaml").read_text(encoding="utf-8")
    goose_text = (ROOT_DIR / "config" / "goose-config.yaml").read_text(encoding="utf-8")

    for expected in (
        "name: metric-benchmark",
        "name: llm-wiki-compiler",
        "name: output-compactor",
        "name: scion-coordination",
    ):
        assert expected in autoresearch_text

    for expected in (
        "name: personal-context",
        "name: llm-wiki-compiler",
        "name: output-compactor",
        "name: scion-coordination",
    ):
        assert expected in personal_text

    for text in (autoresearch_text, personal_text, goose_text):
        assert "meta_loop_ops" not in text
        assert "control-plane-admin" not in text
        assert "control_plane_admin.py" not in text
        assert "harness-self-optimize" not in text

    assert "name: metric-benchmark" in goose_text
    assert "name: obsidian-auto-log" in goose_text

    print("harness self-optimize adapter tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
