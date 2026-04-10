#!/usr/bin/env python3
"""
MCP Server for Knowledge Archivist operations.
Automates knowledge distillation, source management, and health checks.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"
SOURCES_DIR = KNOWLEDGE_DIR / "sources"
RAW_SOURCES_DIR = SOURCES_DIR / "raw"
SOPS_DIR = KNOWLEDGE_DIR / "sops"
RESEARCH_DIR = KNOWLEDGE_DIR / "research"
TELEMETRY_DIR = PROJECT_ROOT / "telemetry"
LOGS_DIR = TELEMETRY_DIR / "logs"

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)

def _safe_note_stem(title: str) -> str:
    # Convert non-alphanumeric to hyphens, lowercase
    stem = re.sub(r"[^a-z0-9]+", "-", title.strip().lower())
    return stem.strip("-")

def _record_event(kind: str, payload: dict[str, Any]) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / "archivist_log.jsonl"
    event = {
        "timestamp": _utc_now().isoformat(),
        "kind": kind,
        "payload": payload
    }
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

def list_raw_sources() -> list[str]:
    if not RAW_SOURCES_DIR.exists():
        return []
    return [str(p.relative_to(PROJECT_ROOT)) for p in RAW_SOURCES_DIR.glob("*.md")]

def process_raw_to_source(raw_path_str: str) -> str:
    raw_path = PROJECT_ROOT / raw_path_str
    if not raw_path.exists():
        raise FileNotFoundError(f"Raw source not found: {raw_path}")
    
    content = raw_path.read_text(encoding="utf-8")
    title = raw_path.stem
    stem = _safe_note_stem(title)
    target_path = SOURCES_DIR / f"source-external-{stem}.md"
    
    # Check if already processed
    if target_path.exists():
        return f"Already processed: {target_path.relative_to(PROJECT_ROOT)}"
    
    # Basic distillation (can be enhanced with LLM later)
    structured_content = f"""---
title: "{title}"
source_path: "{raw_path_str}"
processed_at: "{_utc_now().isoformat()}"
status: "distilled"
---

# Source: {title}

{content}

## Archivist Metadata
- Automatically ingested from raw export.
"""
    target_path.write_text(structured_content, encoding="utf-8")
    _record_event("distill_source", {"raw": raw_path_str, "target": str(target_path.relative_to(PROJECT_ROOT))})
    return f"Distilled to: {target_path.relative_to(PROJECT_ROOT)}"

def health_check() -> str:
    report = ["# Archivist Health Report", f"Generated: {_utc_now().isoformat()}", ""]
    
    # 1. Check for missing links in index
    index_path = SOURCES_DIR / "index.md"
    index_content = index_path.read_text(encoding="utf-8") if index_path.exists() else ""
    
    missing_links = []
    for p in SOURCES_DIR.glob("*.md"):
        if p.name == "index.md": continue
        if p.name not in index_content:
            missing_links.append(p.name)
    
    if missing_links:
        report.append("## Missing Links in index.md")
        for link in missing_links:
            report.append(f"- [ ] {link}")
    else:
        report.append("## Index Integrity: OK")
        
    # 2. Check for empty sources
    empty_sources = []
    for p in SOURCES_DIR.glob("*.md"):
        if p.stat().st_size < 50:
            empty_sources.append(p.name)
            
    if empty_sources:
        report.append("\n## Low Density Sources")
        for s in empty_sources:
            report.append(f"- [ ] {s} (very small)")
            
    _record_event("health_check", {"missing_links_count": len(missing_links), "low_density_count": len(empty_sources)})
    return "\n".join(report)

def handle_request(request: dict) -> dict:
    if request.get("type") != "call_tool":
        return {"error": "Only call_tool requests are supported."}

    tool = request.get("name")
    args = request.get("arguments", {})

    try:
        if tool == "archivist_list_unprocessed":
            raw_files = list_raw_sources()
            processed_stems = [p.stem.replace("source-external-", "") for p in SOURCES_DIR.glob("source-external-*.md")]
            unprocessed = [f for f in raw_files if _safe_note_stem(Path(f).stem) not in processed_stems]
            return {"content": [{"type": "text", "text": json.dumps(unprocessed, indent=2)}]}
            
        elif tool == "archivist_distill":
            target = args.get("target")
            if not target: return {"error": "Missing target"}
            res = process_raw_to_source(target)
            return {"content": [{"type": "text", "text": res}]}
            
        elif tool == "archivist_health_check":
            res = health_check()
            return {"content": [{"type": "text", "text": res}]}
            
        elif tool == "archivist_get_reconciliation_context":
            wiki_path_str = args.get("wiki_path")
            if not wiki_path_str: return {"error": "Missing wiki_path"}
            
            wiki_path = PROJECT_ROOT / wiki_path_str
            if not wiki_path.exists(): return {"error": f"File not found: {wiki_path_str}"}
            
            wiki_content = wiki_path.read_text(encoding="utf-8")
            
            # Find linked sources in content
            # Pattern: [Source: ...](source-path.md) or Source: source-path.md
            sources = re.findall(r"source-[\w-]+\.md", wiki_content)
            source_contexts = {}
            for s in set(sources):
                s_path = SOURCES_DIR / s
                if s_path.exists():
                    # If it's a distilled source, try to find its raw source too
                    s_content = s_path.read_text(encoding="utf-8")
                    raw_match = re.search(r'source_path: "(.*?)"', s_content)
                    raw_content = ""
                    if raw_match:
                        raw_file_path = PROJECT_ROOT / raw_match.group(1)
                        if raw_file_path.exists():
                            raw_content = raw_file_path.read_text(encoding="utf-8")
                    
                    source_contexts[s] = {
                        "distilled_content": s_content,
                        "raw_source_content": raw_content
                    }
            
            res_data = {
                "wiki_content": wiki_content,
                "linked_sources": source_contexts
            }
            return {"content": [{"type": "text", "text": json.dumps(res_data, indent=2, ensure_ascii=False)}]}

        elif tool == "archivist_audit_citations":
            # Scan wiki and sops for grounding
            audit_report = ["# Citation Audit Report", f"Generated: {_utc_now().isoformat()}", ""]
            
            missing_citation = []
            files_to_check = list(KNOWLEDGE_DIR.glob("wiki/**/*.md")) + list(SOPS_DIR.glob("*.md"))
            
            for p in files_to_check:
                if p.name == "index.md" or p.name == "schema.md": continue
                content = p.read_text(encoding="utf-8")
                # Look for "Evidence:", "Source:", or [[source-]]
                if not re.search(r"(Evidence:|Source:|source-[\w-]+\.md|\[\[source-)", content, re.IGNORECASE):
                    missing_citation.append(str(p.relative_to(PROJECT_ROOT)))
            
            if missing_citation:
                audit_report.append("## Files Lacking Grounding (No Citations found)")
                for f in missing_citation:
                    audit_report.append(f"- [ ] {f}")
            else:
                audit_report.append("## Citation Integrity: All pages appear grounded.")
                
            return {"content": [{"type": "text", "text": "\n".join(audit_report)}]}

        elif tool == "archivist_distill_lessons":
            log_path = KNOWLEDGE_DIR / "log.md"
            if not log_path.exists(): return {"error": "log.md not found"}
            
            log_content = log_path.read_text(encoding="utf-8")
            # Extract run summaries
            entries = re.split(r"\n## ", log_content)
            
            lessons = []
            for entry in entries[1:]: # Skip header
                lines = entry.splitlines()
                title = lines[0]
                content = "\n".join(lines[1:])
                
                # Heuristic: only look at accepted or verification runs with specific keywords
                if "accepted" in title or "failed" in content.lower() or "error" in content.lower():
                    lessons.append(f"### {title}\n{content.strip()}")
            
            lessons_file = KNOWLEDGE_DIR / "lessons.md"
            output = [
                "# Angella Meta-Learning: Lessons Learned",
                f"Last distilled: {_utc_now().isoformat()}",
                "",
                "> This file is automatically evolved by the Archivist Loop based on historical run logs.",
                "",
                "\n\n".join(lessons[-10:]) # Keep last 10 distilled lessons for context efficiency
            ]
            lessons_file.write_text("\n".join(output), encoding="utf-8")
            _record_event("distill_lessons", {"entries_processed": len(lessons)})
            
            return {"content": [{"type": "text", "text": f"Successfully distilled {len(lessons)} lessons to {lessons_file.relative_to(PROJECT_ROOT)}"}]}
            
        else:
            return {"error": f"Unknown tool: {tool}"}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--describe":
        print(json.dumps({
            "tools": [
                {
                    "name": "archivist_list_unprocessed",
                    "description": "Lists raw sources that haven't been distilled into structured source files yet.",
                    "inputSchema": {"type": "object", "properties": {}}
                },
                {
                    "name": "archivist_distill",
                    "description": "Transforms a raw markdown export into a structured LLM-Wiki source file.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "target": {"type": "string", "description": "The relative path to the raw source file."}
                        },
                        "required": ["target"]
                    }
                },
                {
                    "name": "archivist_health_check",
                    "description": "Runs a health check on the knowledge base to find missing links or low-density content.",
                    "inputSchema": {"type": "object", "properties": {}}
                },
                {
                    "name": "archivist_get_reconciliation_context",
                    "description": "Gathers wiki content and all linked raw source contents for a reconciliation (hallucination check) pass.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "wiki_path": {"type": "string", "description": "The relative path to the wiki or SOP file to reconcile."}
                        },
                        "required": ["wiki_path"]
                    }
                },
                {
                    "name": "archivist_audit_citations",
                    "description": "Audits the knowledge base to ensure all derived content has proper citations to sources.",
                    "inputSchema": {"type": "object", "properties": {}}
                },
                {
                    "name": "archivist_distill_lessons",
                    "description": "Analyzes the run log to extract key patterns, successes, and failures into a consolidated lessons.md file.",
                    "inputSchema": {"type": "object", "properties": {}}
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
