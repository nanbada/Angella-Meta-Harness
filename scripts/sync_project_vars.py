#!/usr/bin/env python3
"""Synchronize project variables from config/project-vars.json into documentation files."""

import json
import re
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
VARS_FILE = ROOT_DIR / "config" / "project-vars.json"

TARGET_FILES = [
    "README.md",
    "docs/arch-snapshot.md",
    "docs/setup-gemma4-mlx.md",
    "docs/setup-gemma4-ollama.md",
    ".env.mlx.example",
    ".gemini/agents/angella-researcher.md",
    ".gemini/agents/angella-implementer.md",
    ".gemini/agents/angella-reviewer.md",
    ".gemini/agents/angella-archivist.md",
    ".gemini/skills/angella-core.md",
]

def sync_file(file_path: Path, variables: dict[str, str]) -> None:
    if not file_path.exists():
        print(f"Skipping {file_path.name} (not found)")
        return

    content = file_path.read_text(encoding="utf-8")
    
    for key, value in variables.items():
        # 1. Inline Markdown text: <!--VAR:KEY-->value<!--/VAR-->
        pattern_html = re.compile(rf"<!--VAR:{key}-->.*?<!--/VAR-->", flags=re.DOTALL)
        content = pattern_html.sub(f"<!--VAR:{key}-->{value}<!--/VAR-->", content)
        
        # 2. Bash assignments: export VAR=value # AUTO_SYNC:KEY
        pattern_bash = re.compile(rf"^(\s*(?:export\s+)?[\w_]+=).*?( # AUTO_SYNC:{key})$", flags=re.MULTILINE)
        content = pattern_bash.sub(rf"\g<1>{value}\g<2>", content)
        
        # 3. Command line arguments: ... --flag value # AUTO_SYNC:KEY
        pattern_cmd = re.compile(rf"(--[\w-]+[= ])([^=\s]+)( # AUTO_SYNC:{key})$", flags=re.MULTILINE)
        content = pattern_cmd.sub(rf"\g<1>{value}\g<3>", content)

    file_path.write_text(content, encoding="utf-8")
    print(f"Synced {file_path.name}")

def main() -> None:
    if not VARS_FILE.exists():
        print(f"Error: {VARS_FILE} not found.")
        return

    variables = json.loads(VARS_FILE.read_text(encoding="utf-8"))
    
    for relative_path in TARGET_FILES:
        target = ROOT_DIR / relative_path
        sync_file(target, variables)

if __name__ == "__main__":
    main()
