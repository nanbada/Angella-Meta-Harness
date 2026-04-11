#!/usr/bin/env python3
"""MCP Server for LLM-Wiki Compiler."""

import json
import os
import subprocess
import sys
from pathlib import Path

# Try to import our new fast indexer, fallback if not found (though it should be)
try:
    import knowledge_index
except ImportError:
    knowledge_index = None

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def _load_runtime_env() -> dict[str, str]:
    env = os.environ.copy()
    env_agents = PROJECT_ROOT / ".env.agents"
    if env_agents.exists():
        for line in env_agents.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()

    # Knowledge lives in the repo-local tree; do not forward retired overrides.
    env.pop("ANGELLA_KNOWLEDGE_DIR", None)
    return env


def _knowledge_dir() -> Path:
    knowledge_dir = (PROJECT_ROOT / "knowledge").resolve()
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    return knowledge_dir


def _sources_dir() -> Path:
    sources_dir = (_knowledge_dir() / "sources").resolve()
    sources_dir.mkdir(parents=True, exist_ok=True)
    return sources_dir


def _safe_note_stem(title: str) -> str:
    stem = "".join(ch if ch.isalnum() else "_" for ch in title.strip())
    stem = stem.strip("._")
    while "__" in stem:
        stem = stem.replace("__", "_")
    if not stem:
        raise ValueError("Title must include at least one letter or number.")
    return stem


def _note_path(title: str, category: str = "sources") -> Path:
    knowledge_dir = _knowledge_dir()
    if category == "research":
        target_dir = (knowledge_dir / "research").resolve()
    else:
        target_dir = (knowledge_dir / "sources").resolve()
    
    target_dir.mkdir(parents=True, exist_ok=True)
    path = (target_dir / f"{_safe_note_stem(title)}.md").resolve()
    
    if not str(path).startswith(str(knowledge_dir)):
        raise ValueError("Refusing to write outside knowledge directory.")
    return path


def run_npx_llmwiki(args: list) -> str:
    """Invokes llm-wiki-compiler from the repo-local knowledge directory."""

    env = _load_runtime_env()
    knowledge_dir = _knowledge_dir()

    try:
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
        if knowledge_index:
            knowledge_index.build_index()
        return {"content": [{"type": "text", "text": output}]}
        
    elif tool == "llmwiki_compile":
        output = run_npx_llmwiki(["compile"])
        if knowledge_index:
            count = knowledge_index.build_index()
            output += f"\n[Optimization] Fast SQLite Index rebuilt with {count} documents."
        return {"content": [{"type": "text", "text": output}]}
        
    elif tool == "llmwiki_query":
        question = args.get("question")
        save = args.get("save", False)
        if not question:
            return {"error": "Missing 'question' argument."}
            
        # Fast Path: SQLite FTS5 Query (Zero-Overhead)
        if knowledge_index and not save:
            try:
                results = knowledge_index.query_index(question, limit=3)
                if isinstance(results, dict) and "error" in results:
                    raise Exception(results["error"])
                
                if not results:
                    return {"content": [{"type": "text", "text": "No matching knowledge found in fast index."}]}
                
                formatted_out = []
                for r in results:
                    formatted_out.append(f"### {r.get('title', 'Unknown')} ({r.get('path')})\n{r.get('matched_content')}\n")
                
                return {"content": [{"type": "text", "text": "\n".join(formatted_out)}]}
            except Exception as e:
                # Fallback to slow npx method if SQLite fails
                pass

        # Slow Path / Save Path
        cmd_args = ["query", question]
        if save:
            cmd_args.append("--save")
        output = run_npx_llmwiki(cmd_args)
        
        if save and knowledge_index:
            knowledge_index.build_index()
            
        return {"content": [{"type": "text", "text": output}]}
        
    elif tool == "llmwiki_save_note":
        title = args.get("title")
        content = args.get("content")
        category = args.get("category", "sources") # default to wiki sources
        if not title or not content:
            return {"error": "Missing 'title' or 'content' argument."}

        try:
            file_path = _note_path(title, category=category)
        except ValueError as exc:
            return {"error": str(exc)}

        file_path.write_text(f"# {title}\n\n{content}", encoding="utf-8")
        
        if knowledge_index:
            knowledge_index.build_index()
            
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Successfully saved note to {file_path}. Category: {category}",
                }
            ]
        }
        
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
                },
                {
                    "name": "llmwiki_save_note",
                    "description": "Saves raw text content directly as a new source file in the knowledge base (wiki sources or research).",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "A descriptive title for the note."},
                            "content": {"type": "string", "description": "The markdown content of the note."},
                            "category": {"type": "string", "enum": ["sources", "research"], "description": "Category: 'sources' for wiki knowledge, 'research' for performance studies/external research."}
                        },
                        "required": ["title", "content"]
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
