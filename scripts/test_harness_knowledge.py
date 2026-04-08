#!/usr/bin/env python3
"""Regression checks for v2 knowledge helpers and parser utilities."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "mcp-servers"))

import llmwiki_compiler_ops  # noqa: E402
import personal_context_ops  # noqa: E402
import tool_parser_wrapper  # noqa: E402
from output_compactor import compact_output  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp_root:
        tmp_project_root = Path(tmp_root) / "project-root"
        tmp_project_root.mkdir(parents=True, exist_ok=True)
        knowledge_dir = tmp_project_root / "knowledge"
        original_env = os.environ.get("ANGELLA_KNOWLEDGE_DIR")
        original_project_root = llmwiki_compiler_ops.PROJECT_ROOT
        os.environ["ANGELLA_KNOWLEDGE_DIR"] = str(knowledge_dir)
        llmwiki_compiler_ops.PROJECT_ROOT = tmp_project_root

        try:
            note_response = llmwiki_compiler_ops.handle_request(
                {
                    "type": "call_tool",
                    "name": "llmwiki_save_note",
                    "arguments": {
                        "title": "Setup Check Notes",
                        "content": "Keep setup output compact and deterministic.",
                    },
                }
            )
            note_path = knowledge_dir / "sources" / "Setup_Check_Notes.md"
            assert note_path.is_file()
            assert "deterministic" in note_path.read_text(encoding="utf-8")
            assert "Successfully saved note" in note_response["content"][0]["text"]

            original_raw_dir = personal_context_ops.RAW_DIR
            original_personal_project_root = personal_context_ops.PROJECT_ROOT
            personal_context_ops.PROJECT_ROOT = tmp_project_root
            personal_context_ops.RAW_DIR = knowledge_dir / "sources"
            personal_context_ops.RAW_DIR.mkdir(parents=True, exist_ok=True)
            try:
                ingest_result = personal_context_ops.ingest_to_raw(
                    "clipboard_dump",
                    "alpha\nbeta\n",
                    False,
                )
            finally:
                personal_context_ops.RAW_DIR = original_raw_dir
                personal_context_ops.PROJECT_ROOT = original_personal_project_root

            assert "Successfully ingested into raw" in ingest_result
            ingested = sorted((knowledge_dir / "sources").glob("*clipboard_dump.md"))
            assert ingested
            assert "alpha" in ingested[0].read_text(encoding="utf-8")
        finally:
            llmwiki_compiler_ops.PROJECT_ROOT = original_project_root
            if original_env is None:
                os.environ.pop("ANGELLA_KNOWLEDGE_DIR", None)
            else:
                os.environ["ANGELLA_KNOWLEDGE_DIR"] = original_env

        compacted = compact_output(
            "test_output",
            "warning: flaky\nwarning: flaky\nassertion failed\nassertion failed\n",
            budget_chars=120,
        )
        assert compacted["estimated_tokens_saved"] > 0
        assert "(x2)" in compacted["text"]

        raw_tool_output = '<|tool_call|>{"name":"compact_output_text","arguments":{"kind":"summary"}}<|/tool_call|>'
        parsed = tool_parser_wrapper.intercept_gemma4_tool_call(raw_tool_output)
        assert parsed.startswith('{"name":"compact_output_text"')

        wrapped = tool_parser_wrapper.handle_request(
            {
                "type": "call_tool",
                "name": "parse_gemma4_output",
                "arguments": {"output": raw_tool_output},
            }
        )
        assert "compact_output_text" in wrapped["content"][0]["text"]

    print("harness knowledge tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
