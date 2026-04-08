#!/usr/bin/env python3
"""Regression checks for shared knowledge path overrides."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "mcp-servers"))

import llmwiki_compiler_ops  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp_root:
        knowledge_dir = Path(tmp_root) / "shared-knowledge"
        tmp_project_root = Path(tmp_root) / "project-root"
        tmp_project_root.mkdir(parents=True, exist_ok=True)
        repo_local_knowledge = tmp_project_root / "knowledge"
        original_env = os.environ.get("ANGELLA_KNOWLEDGE_DIR")
        original_project_root = llmwiki_compiler_ops.PROJECT_ROOT
        original_run = llmwiki_compiler_ops.subprocess.run
        captured: dict[str, object] = {}

        def fake_run(cmd, cwd, capture_output, text, env):
            captured["cmd"] = cmd
            captured["cwd"] = cwd
            captured["env_knowledge_dir"] = env.get("ANGELLA_KNOWLEDGE_DIR")

            class Result:
                returncode = 0
                stdout = "ok"
                stderr = ""

            return Result()

        llmwiki_compiler_ops.PROJECT_ROOT = tmp_project_root
        llmwiki_compiler_ops.subprocess.run = fake_run
        try:
            os.environ.pop("ANGELLA_KNOWLEDGE_DIR", None)
            default_output = llmwiki_compiler_ops.run_npx_llmwiki(["query", "repo local knowledge"])
            assert default_output == "ok"
            assert Path(str(captured["cwd"])).resolve() == repo_local_knowledge.resolve()
            assert captured["env_knowledge_dir"] is None

            os.environ["ANGELLA_KNOWLEDGE_DIR"] = str(knowledge_dir)
            output = llmwiki_compiler_ops.run_npx_llmwiki(["query", "shared knowledge"])
            assert output == "ok"
            assert captured["cmd"] == ["npx", "--yes", "llm-wiki-compiler", "query", "shared knowledge"]
            assert Path(str(captured["cwd"])).resolve() == knowledge_dir.resolve()
            assert captured["env_knowledge_dir"] == str(knowledge_dir)

            response = llmwiki_compiler_ops.handle_request(
                {
                    "type": "call_tool",
                    "name": "llmwiki_save_note",
                    "arguments": {
                        "title": "Shared Knowledge Note",
                        "content": "Angella shared wiki override works.",
                    },
                }
            )
        finally:
            llmwiki_compiler_ops.PROJECT_ROOT = original_project_root
            llmwiki_compiler_ops.subprocess.run = original_run
            if original_env is None:
                os.environ.pop("ANGELLA_KNOWLEDGE_DIR", None)
            else:
                os.environ["ANGELLA_KNOWLEDGE_DIR"] = original_env

        saved_note = knowledge_dir / "sources" / "Shared_Knowledge_Note.md"
        assert saved_note.is_file()
        assert "shared wiki override works" in saved_note.read_text(encoding="utf-8")
        assert "Successfully saved note" in response["content"][0]["text"]

    print("optional provider tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
