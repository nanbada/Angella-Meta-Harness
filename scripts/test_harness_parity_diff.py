#!/usr/bin/env python3
"""Regression checks for the harness parity diff runner."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
RUNNER = ROOT_DIR / "scripts" / "run_harness_parity_diff.py"


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp_root:
        root = Path(tmp_root)
        (root / "scripts").mkdir(parents=True, exist_ok=True)
        (root / "docs").mkdir(parents=True, exist_ok=True)
        (root / "knowledge").mkdir(parents=True, exist_ok=True)
        (root / "docs" / "evidence.md").write_text("# Evidence\n", encoding="utf-8")
        (root / "knowledge" / "schema.md").write_text(
            "# Angella Harness Wiki Schema\n\n## Layers\n\n## Entry Points\n\n## Component Pages\n\n## Linking Rules\n\n## Log Rules\n\n## Addendum Rules\n\n## Search Rules\n\n## Non-Goals\n",
            encoding="utf-8",
        )
        (root / "knowledge" / "index.md").write_text("# Index\n", encoding="utf-8")
        (root / "knowledge" / "log.md").write_text("# Log\n", encoding="utf-8")
        (root / "config").mkdir(parents=True, exist_ok=True)
        (root / "config" / "knowledge-policy.yaml").write_text(
            json.dumps(
                {
                    "knowledge_policy": {
                        "indexed_paths": ["knowledge", "docs/evidence.md", "PARITY.md"],
                        "canonical_entrypoints": ["knowledge/index.md", "knowledge/log.md"],
                        "search_provider": "builtin",
                        "snippet_chars": 240,
                    }
                }
            ),
            encoding="utf-8",
        )
        control_plane = root / ".cache" / "angella" / "control-plane"

        scenario_path = root / "scripts" / "scenarios.json"
        scenario_path.write_text(
            json.dumps(
                {
                    "lanes": [
                        {
                            "id": 1,
                            "title": "example lane",
                            "status": "implemented",
                            "evidence": ["docs/evidence.md"],
                        }
                    ]
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        parity_path = root / "PARITY.md"
        parity_path.write_text(
            "# Parity Status — Temp\n\n"
            "- Canonical document: `scripts/run_harness_parity_diff.py`\n\n"
            "## Lane 1 — example lane\n\n"
            "- Status: implemented\n"
            "- Evidence: `docs/evidence.md`\n",
            encoding="utf-8",
        )

        ok = subprocess.run(
            [sys.executable, str(RUNNER), "--parity-file", str(parity_path), "--scenario-file", str(scenario_path)],
            text=True,
            capture_output=True,
            check=False,
            env={**os.environ, "ANGELLA_CONTROL_PLANE_DIR": str(control_plane)},
        )
        assert ok.returncode == 0, ok.stderr
        state = json.loads((control_plane / "parity-state.json").read_text(encoding="utf-8"))
        assert state["lane_count"] == 1
        assert state["lanes"][0]["status"] == "implemented"

        parity_path.write_text(
            "# Parity Status — Temp\n\n"
            "- Canonical document: `scripts/run_harness_parity_diff.py`\n\n"
            "## Lane 1 — example lane\n\n"
            "- Status: draft\n"
            "- Evidence: `docs/evidence.md`\n",
            encoding="utf-8",
        )
        mismatch = subprocess.run(
            [sys.executable, str(RUNNER), "--parity-file", str(parity_path), "--scenario-file", str(scenario_path)],
            text=True,
            capture_output=True,
            check=False,
            env={**os.environ, "ANGELLA_CONTROL_PLANE_DIR": str(control_plane)},
        )
        assert mismatch.returncode != 0
        assert "status mismatch" in mismatch.stderr
        mismatch_state = json.loads((control_plane / "parity-state.json").read_text(encoding="utf-8"))
        assert mismatch_state["lanes"][0]["status"] == "failed"
        assert (control_plane / "failures" / "open" / "parity-lane-1.json").is_file()

    print("harness parity diff tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
