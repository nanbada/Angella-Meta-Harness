#!/usr/bin/env python3
"""MCP Server for Personal OS Context & LLM-Wiki Ingestion."""

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Setup raw directory mapping
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "knowledge" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)


def read_clipboard() -> str:
    """Reads the current macOS clipboard content using pbpaste."""
    try:
        result = subprocess.run(["pbpaste"], capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except Exception as e:
        return f"Error reading clipboard: {e}"


def ingest_to_raw(source_identifier: str, content: str = None, is_file_path: bool = False) -> str:
    """
    Ingests text or copies a file into the knowledge/raw directory for the LLM-Wiki.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c if c.isalnum() else "_" for c in source_identifier)
    target_filename = f"{timestamp}_{safe_name}.md"
    target_path = RAW_DIR / target_filename

    try:
        if is_file_path and content is None:
            source_path = Path(source_identifier)
            if not source_path.exists():
                return f"Error: Source file {source_path} not found."
            # Read content from file
            text_content = source_path.read_text(encoding="utf-8", errors="replace")
            target_path.write_text(text_content, encoding="utf-8")
        else:
            if content is None:
                content = ""
            target_path.write_text(content, encoding="utf-8")
        
        return f"Successfully ingested into raw: {target_path.relative_to(PROJECT_ROOT)}"
    except Exception as e:
        return f"Error ingesting to raw: {e}"


def handle_request(request: dict) -> dict:
    if request.get("type") != "call_tool":
        return {"error": "Only call_tool requests are supported."}

    tool = request.get("name")
    args = request.get("arguments", {})

    if tool == "read_clipboard":
        content = read_clipboard()
        return {"content": [{"type": "text", "text": content}]}
    elif tool == "ingest_to_raw":
        source_id = args.get("source_identifier", "unnamed")
        content = args.get("content")
        is_file = args.get("is_file_path", False)
        result = ingest_to_raw(source_id, content, is_file)
        return {"content": [{"type": "text", "text": result}]}
    else:
        return {"error": f"Unknown tool: {tool}"}


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--describe":
        print(json.dumps({
            "tools": [
                {
                    "name": "read_clipboard",
                    "description": "Reads the current contents of the user's macOS clipboard to quickly pull in external context.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {}
                    }
                },
                {
                    "name": "ingest_to_raw",
                    "description": "Ingests text content or copies an external file into the immutable `knowledge/raw/` directory for the LLM-Wiki. The agent should use this before synthesizing new wiki pages.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "source_identifier": {"type": "string", "description": "A short, descriptive name for the source (e.g., 'article_title' or 'clipboard_dump')."},
                            "content": {"type": "string", "description": "The raw text content to ingest. Leave empty if reading from a file path."},
                            "is_file_path": {"type": "boolean", "description": "Set to true if source_identifier is actually an absolute file path to read from."}
                        },
                        "required": ["source_identifier"]
                    }
                }
            ]
        }))
        sys.exit(0)

    # Standard stdio server loop for Goose MCP
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            res = handle_request(req)
            print(json.dumps(res), flush=True)
        except Exception as e:
            print(json.dumps({"error": str(e)}), flush=True)
