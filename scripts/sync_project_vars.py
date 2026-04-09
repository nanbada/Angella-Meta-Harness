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
        # This matches from the equals sign to the comment, allowing any variable name.
        pattern_bash = re.compile(rf"^(.*?)=(.*?)( # AUTO_SYNC:{key})$", flags=re.MULTILINE)
        content = pattern_bash.sub(rf"\1={value}\3", content)
        
        # 3. Simple text replacement inside Markdown backticks if marked. 
        # For commands like `bash setup.sh --worker-model mlx_gemma4_26b_it_gguf # AUTO_SYNC:MLX_MODEL_ID`
        pattern_cmd = re.compile(rf"^(.*?)( \S+)( # AUTO_SYNC:{key})$", flags=re.MULTILINE)
        # Replaces the last word before the comment with the value
        content = pattern_cmd.sub(rf"\1 {value}\3", content)

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
