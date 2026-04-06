#!/usr/bin/env python3
"""Regression checks for optional qmd integrations."""

from __future__ import annotations

import os
import stat
import sys
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "mcp-servers"))

from meta_loop_ops import search_harness_knowledge  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp_root:
        root = Path(tmp_root)
        repo = root / "repo"
        repo.mkdir()
        (repo / "knowledge").mkdir()
        (repo / "knowledge" / "index.md").write_text("# Index\n\nAuthentication and setup-check notes\n", encoding="utf-8")
        (repo / "knowledge" / "log.md").write_text("# Log\n", encoding="utf-8")
        (repo / "knowledge" / "schema.md").write_text("# Schema\n", encoding="utf-8")
        (repo / "config").mkdir()
        (repo / "config" / "knowledge-policy.yaml").write_text(
            '{"knowledge_policy":{"indexed_paths":["knowledge"],"canonical_entrypoints":["knowledge/index.md","knowledge/log.md"],"search_provider":"builtin","snippet_chars":240}}',
            encoding="utf-8",
        )
        (repo / "PARITY.md").write_text("# Parity\n", encoding="utf-8")

        fallback = search_harness_knowledge("authentication", provider="qmd", repo_root=repo)
        assert fallback["success"] is True
        assert fallback["provider"] == "builtin"
        assert fallback["fallback_reason"] == "qmd_not_installed"

        fake_bin = root / "bin"
        fake_bin.mkdir()
        qmd = fake_bin / "qmd"
        qmd.write_text(
            "#!/usr/bin/env bash\n"
            "echo '[{\"path\":\"knowledge/index.md\",\"title\":\"Index\",\"category\":\"knowledge\",\"snippet\":\"authentication flow\"}]'\n",
            encoding="utf-8",
        )
        qmd.chmod(qmd.stat().st_mode | stat.S_IEXEC)
        original_path = os.environ.get("PATH", "")
        os.environ["PATH"] = f"{fake_bin}:{original_path}"
        try:
            qmd_result = search_harness_knowledge("authentication", provider="qmd", repo_root=repo)
            assert qmd_result["provider"] == "qmd"
            assert qmd_result["results"][0]["relpath"] == "knowledge/index.md"

        finally:
            os.environ["PATH"] = original_path

    print("optional provider tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
