#!/usr/bin/env python3
"""MCP Server for Personal OS Context & LLM-Wiki Ingestion."""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _project_root() -> Path:
    return PROJECT_ROOT.resolve()


def _raw_dir() -> Path:
    raw_dir = (_project_root() / "knowledge" / "sources").resolve()
    raw_dir.mkdir(parents=True, exist_ok=True)
    return raw_dir


def read_clipboard() -> str:
    """Reads the current macOS clipboard content using pbpaste."""
    try:
        result = subprocess.run(["pbpaste"], capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except Exception as e:
        return f"Error reading clipboard: {e}"


def read_calendar_events() -> str:
    """Reads today's macOS Calendar events via AppleScript."""
    script = '''
    set todayStart to (current date)
    set time of todayStart to 0
    set todayEnd to todayStart + 1 * days
    set output to ""
    tell application "Calendar"
        repeat with c in calendars
            try
                set evts to (events of c whose start date >= todayStart and start date < todayEnd)
                repeat with e in evts
                    set output to output & (name of c as string) & " - " & (summary of e as string) & " (" & (start date of e as string) & ")\\n"
                end repeat
            on error
                -- ignore protected or inaccessible calendars
            end try
        end repeat
    end tell
    if output is "" then return "No events scheduled for today."
    return output
    '''
    try:
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        if result.returncode != 0:
            return f"Error accessing Calendar: {result.stderr}"
        return result.stdout.strip()
    except Exception as e:
        return f"Execution exception: {e}"


def read_reminders() -> str:
    """Reads incomplete macOS Reminders via AppleScript."""
    script = '''
    set output to ""
    tell application "Reminders"
        try
            set incompleteTasks to (reminders whose completed is false)
            repeat with t in incompleteTasks
                set output to output & "- " & (name of t as string) & "\\n"
            end repeat
        on error
            return "Could not access Reminders."
        end try
    end tell
    if output is "" then return "No incomplete reminders."
    return output
    '''
    try:
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        if result.returncode != 0:
            return f"Error accessing Reminders: {result.stderr}"
        return result.stdout.strip()
    except Exception as e:
        return f"Execution exception: {e}"


def ingest_to_raw(source_identifier: str, content: str = None, is_file_path: bool = False) -> str:
    """
    Ingests text or copies a file into the knowledge/sources/ directory for the LLM-Wiki.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c if c.isalnum() else "_" for c in source_identifier)
    target_filename = f"{timestamp}_{safe_name}.md"
    target_path = _raw_dir() / target_filename

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
        
        return f"Successfully ingested into raw: {target_path.relative_to(_project_root())}"
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
    elif tool == "read_calendar_events":
        content = read_calendar_events()
        return {"content": [{"type": "text", "text": content}]}
    elif tool == "read_reminders":
        content = read_reminders()
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
                    "name": "read_calendar_events",
                    "description": "Reads the user's macOS Calendar to get today's scheduled events.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {}
                    }
                },
                {
                    "name": "read_reminders",
                    "description": "Reads the user's macOS Reminders to get a list of active/incomplete tasks.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {}
                    }
                },
                {
                    "name": "ingest_to_raw",
                    "description": "Ingests text content or copies an external file into the immutable `knowledge/sources/` directory for the LLM-Wiki. The agent should use this before synthesizing new wiki pages.",
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
