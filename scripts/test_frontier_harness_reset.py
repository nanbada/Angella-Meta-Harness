#!/usr/bin/env python3
"""Regression checks for the frontier-first harness reset."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
HARNESS_CATALOG = ROOT_DIR / "scripts" / "harness_catalog.py"


def _run(args: list[str], *, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HARNESS_CATALOG), *args],
        cwd=str(ROOT_DIR),
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def main() -> int:
    env = dict(os.environ)
    env["GOOGLE_API_KEY"] = "test-google"
    env["OPENAI_API_KEY"] = "test-openai"
    env["ANTHROPIC_API_KEY"] = "test-anthropic"
    env["ANGELLA_OLLAMA_TAGS_JSON"] = '{"models":[{"name":"gemma4:26b"}]}'

    default = _run(["resolve", "--format", "json"], env=env)
    assert default.returncode == 0, default.stderr
    payload = json.loads(default.stdout)
    assert payload["profile"]["id"] == "frontier_default"
    assert payload["worker"]["provider"] == "openai"
    assert payload["routing"]["execution_mode"] == "frontier_primary"
    assert payload["routing"]["worker_tier"] == "frontier_primary"

    private_env = dict(env)
    private_env["ANGELLA_PRIVATE_MODE"] = "true"
    private = _run(["resolve", "--profile", "frontier_private_fallback", "--format", "json"], env=private_env)
    assert private.returncode == 0, private.stderr
    private_payload = json.loads(private.stdout)
    assert private_payload["worker"]["provider"] == "ollama"
    assert private_payload["routing"]["worker_tier"] == "local_fallback"
    assert private_payload["routing"]["fallback_reason"] == "private_mode"

    legacy = _run(["resolve", "--profile", "default"], env=env)
    assert legacy.returncode != 0
    assert "Legacy harness profile `default` has been removed" in legacy.stderr

    saver = _run(["resolve", "--profile", "frontier_token_saver_lab", "--format", "json"], env=env)
    assert saver.returncode == 0, saver.stderr
    saver_payload = json.loads(saver.stdout)
    assert saver_payload["routing"]["token_saver_enabled"] is True

    print("frontier harness reset tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
