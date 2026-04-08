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
        (root / "docs").mkdir(parents=True, exist_ok=True)
        (root / "scripts").mkdir(parents=True, exist_ok=True)
        (root / "README.md").write_text("# Temp\n", encoding="utf-8")
        (root / "docs" / "arch-snapshot.md").write_text("# Snapshot\n", encoding="utf-8")
        (root / "docs" / "PARITY.md").write_text(
            "# Parity Status — Temp\n\n"
            "- Canonical document: `docs/PARITY.md`\n"
            "- Validator: `scripts/run_harness_parity_diff.py`\n\n"
            "## Lane 1 — setup path\n\n"
            "- Status: implemented\n"
            "- Evidence: `README.md`\n\n"
            "## Lane 2 — docs path\n\n"
            "- Status: implemented\n"
            "- Evidence: `docs/arch-snapshot.md`\n",
            encoding="utf-8",
        )

        scenario_path = root / "scripts" / "scenarios.json"
        scenario_path.write_text(
            json.dumps(
                {
                    "lanes": [
                        {
                            "id": 1,
                            "title": "setup path",
                            "status": "implemented",
                            "evidence": ["README.md"],
                        },
                        {
                            "id": 2,
                            "title": "docs path",
                            "status": "implemented",
                            "evidence": ["docs/arch-snapshot.md"],
                        },
                    ]
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        control_plane = root / ".cache" / "angella" / "control-plane"
        ok = subprocess.run(
            [
                sys.executable,
                str(RUNNER),
                "--parity-file",
                str(root / "docs" / "PARITY.md"),
                "--scenario-file",
                str(scenario_path),
            ],
            text=True,
            capture_output=True,
            check=False,
            env={**os.environ, "ANGELLA_CONTROL_PLANE_DIR": str(control_plane)},
        )
        assert ok.returncode == 0, ok.stderr
        state = json.loads((control_plane / "parity-state.json").read_text(encoding="utf-8"))
        assert state["lane_count"] == 2
        assert state["lanes"][0]["status"] == "implemented"

        (root / "docs" / "PARITY.md").write_text(
            "# Parity Status — Temp\n\n"
            "- Canonical document: `docs/PARITY.md`\n"
            "- Validator: `scripts/run_harness_parity_diff.py`\n\n"
            "## Lane 1 — setup path\n\n"
            "- Status: draft\n"
            "- Evidence: `README.md`\n\n"
            "## Lane 2 — docs path\n\n"
            "- Status: implemented\n"
            "- Evidence: `docs/arch-snapshot.md`\n",
            encoding="utf-8",
        )
        mismatch = subprocess.run(
            [
                sys.executable,
                str(RUNNER),
                "--parity-file",
                str(root / "docs" / "PARITY.md"),
                "--scenario-file",
                str(scenario_path),
            ],
            text=True,
            capture_output=True,
            check=False,
            env={**os.environ, "ANGELLA_CONTROL_PLANE_DIR": str(control_plane)},
        )
        assert mismatch.returncode != 0
        mismatch_state = json.loads((control_plane / "parity-state.json").read_text(encoding="utf-8"))
        assert mismatch_state["lanes"][0]["status"] == "failed"
        assert (control_plane / "failures" / "open" / "parity-lane-1.json").is_file()

    print("harness parity diff tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
