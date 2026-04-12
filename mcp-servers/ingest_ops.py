#!/usr/bin/env python3
"""
MCP Server for Knowledge Ingestion Operations.
Automates capturing clipboard, X (Twitter) articles, and vision images.
"""

from __future__ import annotations

import json
import os
import re
import sys
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"
SOURCES_DIR = KNOWLEDGE_DIR / "sources"
RAW_SOURCES_DIR = SOURCES_DIR / "raw"

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)

def _safe_stem(title: str) -> str:
    stem = re.sub(r"[^a-z0-9]+", "-", title.strip().lower())
    return stem.strip("-")

def _save_raw(stem_hint: str, content: str, source_type: str) -> str:
    RAW_SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = _utc_now().strftime("%Y%m%d%H%M%S")
    file_name = f"{source_type}-{stem_hint}-{timestamp}.md"
    target_path = RAW_SOURCES_DIR / file_name
    
    target_path.write_text(content, encoding="utf-8")
    return str(target_path.relative_to(PROJECT_ROOT))

def ingest_clipboard() -> str:
    """Uses macOS pbpaste to get clipboard string."""
    try:
        result = subprocess.run(["pbpaste"], capture_output=True, text=True, check=True)
        content = result.stdout.strip()
        if not content:
            return "Clipboard is empty."
        
        # Determine a quick stem
        first_line = content.splitlines()[0] if content else "snippet"
        stem = _safe_stem(first_line[:20]) or "snippet"
        
        md_content = f"# Clipboard Snippet\nIngested: {_utc_now().isoformat()}\n\n{content}\n"
        saved_path = _save_raw(stem, md_content, "clipboard")
        return f"Successfully ingested clipboard to {saved_path}"
    except Exception as e:
        return f"Failed to ingest clipboard: {e}"

def ingest_x_article(url: str) -> str:
    """Uses vxtwitter.com to extract tweet data."""
    if "twitter.com" in url:
        api_url = url.replace("twitter.com", "api.vxtwitter.com")
    elif "x.com" in url:
        api_url = url.replace("x.com", "api.vxtwitter.com")
    else:
        return "Not a valid X/Twitter URL."
        
    try:
        req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            
        author = data.get("user_name", "Unknown")
        text = data.get("text", "")
        date = data.get("date", "")
        media = data.get("mediaURLs", [])
        
        media_md = "\n".join([f"![Media]({m})" for m in media])
        
        md_content = f"# Tweet by {author}\nOriginal URL: {url}\nDate: {date}\n\n{text}\n\n{media_md}\n"
        stem = _safe_stem(author) + "-tweet"
        saved_path = _save_raw(stem, md_content, "x-article")
        return f"Successfully ingested X article to {saved_path}"
    except urllib.error.URLError as e:
        return f"Failed to fetch from vxtwitter: {e}"
    except Exception as e:
        return f"Error parsing X article: {e}"

def ingest_image_vision(image_path: str, context: str = "") -> str:
    """Uses Gemini API to transcribe an image to markdown."""
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return "Error: GOOGLE_API_KEY environment variable is required for Vision ingestion."
        
    abs_path = PROJECT_ROOT / image_path
    if not abs_path.exists():
        return f"Error: Image not found at {abs_path}"
        
    # In a real implementation we would base64 encode and use the gemini API.
    # For now, we drop a placeholder raw file that archivist will handle, 
    # or rely on the actual proxy if we implement the HTTP call.
    import base64
    with open(abs_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()
        
    payload = {
        "contents": [{
            "parts": [
                {"text": f"Please describe this image in detail. Extract any text, diagrams, or UI components. Context: {context}"},
                {"inline_data": {"mime_type": "image/jpeg", "data": img_b64}}
            ]
        }]
    }
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-pro:generateContent?key={api_key}"
    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode())
            text = result["candidates"][0]["content"]["parts"][0]["text"]
            
        md_content = f"# Vision Analysis: {abs_path.name}\nContext: {context}\n\n## Gemini Analysis\n{text}\n"
        stem = _safe_stem(abs_path.stem)
        saved_path = _save_raw(stem, md_content, "vision")
        return f"Successfully ingested vision analysis to {saved_path}"
    except Exception as e:
        return f"Failed to analyze image via Gemini: {e}"

def handle_request(request: dict) -> dict:
    if request.get("type") != "call_tool":
        return {"error": "Only call_tool requests are supported."}

    tool = request.get("name")
    args = request.get("arguments", {})

    try:
        if tool == "ingest_clipboard":
            res = ingest_clipboard()
            return {"content": [{"type": "text", "text": res}]}
            
        elif tool == "ingest_x_article":
            url = args.get("url")
            if not url: return {"error": "Missing param: url"}
            res = ingest_x_article(url)
            return {"content": [{"type": "text", "text": res}]}
            
        elif tool == "ingest_image_vision":
            path = args.get("image_path")
            ctx = args.get("context", "")
            if not path: return {"error": "Missing param: image_path"}
            res = ingest_image_vision(path, ctx)
            return {"content": [{"type": "text", "text": res}]}
            
        else:
            return {"error": f"Unknown tool: {tool}"}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--describe":
        print(json.dumps({
            "tools": [
                {
                    "name": "ingest_clipboard",
                    "description": "Captures the current macOS clipboard text and ingests it into the knowledge raw folder.",
                    "inputSchema": {"type": "object", "properties": {}}
                },
                {
                    "name": "ingest_x_article",
                    "description": "Ingests a Twitter/X thread or post by URL into the knowledge base using a proxy API.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string", "description": "The x.com or twitter.com URL."}
                        },
                        "required": ["url"]
                    }
                },
                {
                    "name": "ingest_image_vision",
                    "description": "Analyzes an image file using Gemini Vision and saves the markdown transcription.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "image_path": {"type": "string", "description": "Relative path to the image file."},
                            "context": {"type": "string", "description": "Optional context to guide the vision analysis."}
                        },
                        "required": ["image_path"]
                    }
                }
            ]
        }))
        sys.exit(0)

    for line in sys.stdin:
        if not line.strip(): continue
        try:
            req = json.loads(line)
            res = handle_request(req)
            print(json.dumps(res), flush=True)
        except Exception as e:
            print(json.dumps({"error": str(e)}), flush=True)
