#!/usr/bin/env python3
"""MCP Server for LLM-Wiki Compiler."""
import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def run_npx_llmwiki(args: list) -> str:
    """Invokes the llm-wiki-compiler via npx from the knowledge directory."""
    cmd = ["npx", "llm-wiki-compiler"] + args
    knowledge_dir = PROJECT_ROOT / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    
    # Load .env.agents if it exists to supply API keys
    env = os.environ.copy()
    env_agents = PROJECT_ROOT / ".env.agents"
    if env_agents.exists():
        for line in env_agents.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()

    try:
        # Prompting npm/npx might ask "Need to install the following packages... Ok to proceed? (y)"
        # Use --yes flag for npx
        cmd = ["npx", "--yes", "llm-wiki-compiler"] + args
        result = subprocess.run(
            cmd,
            cwd=knowledge_dir,
            capture_output=True,
            text=True,
            env=env
        )
        if result.returncode != 0:
            return f"Error executing llm-wiki-compiler:\n{result.stderr}"
        return result.stdout.strip() or "Command completed successfully."
    except Exception as e:
        return f"Execution exception: {e}"

def handle_request(request: dict) -> dict:
    if request.get("type") != "call_tool":
        return {"error": "Only call_tool requests are supported."}

    tool = request.get("name")
    args = request.get("arguments", {})

    if tool == "llmwiki_ingest":
        target = args.get("target")
        if not target:
            return {"error": "Missing 'target' argument."}
        output = run_npx_llmwiki(["ingest", target])
        return {"content": [{"type": "text", "text": output}]}
        
    elif tool == "llmwiki_compile":
        output = run_npx_llmwiki(["compile"])
        return {"content": [{"type": "text", "text": output}]}
        
    elif tool == "llmwiki_query":
        question = args.get("question")
        save = args.get("save", False)
        if not question:
            return {"error": "Missing 'question' argument."}
        cmd_args = ["query", question]
        if save:
            cmd_args.append("--save")
        output = run_npx_llmwiki(cmd_args)
        return {"content": [{"type": "text", "text": output}]}
        
    else:
        return {"error": f"Unknown tool: {tool}"}

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--describe":
        print(json.dumps({
            "tools": [
                {
                    "name": "llmwiki_ingest",
                    "description": "Downloads and adds a new source document/URL to the LLM-Wiki sources directory.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "target": {"type": "string", "description": "The URL or path to the file to ingest."}
                        },
                        "required": ["target"]
                    }
                },
                {
                    "name": "llmwiki_compile",
                    "description": "Compiles all sources into interlinked Wikipedia-style markdown pages. Run this after ingesting sources or making manual edits to sources.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {}
                    }
                },
                {
                    "name": "llmwiki_query",
                    "description": "Queries the compiled wiki knowledge base for an answer.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "question": {"type": "string", "description": "The question to ask the wiki."},
                            "save": {"type": "boolean", "description": "If true, the answer will be permanently saved as a new wiki page for future compounding knowledge."}
                        },
                        "required": ["question"]
                    }
                }
            ]
        }))
        sys.exit(0)

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
