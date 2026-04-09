#!/usr/bin/env python3
"""
Advanced Output Compactor for Angella.
Implements context-aware compression to maximize Signal-to-Noise Ratio (SNR).
"""

from __future__ import annotations

import json
import math
import re
import sys
from collections import OrderedDict
from typing import Any


_FAILURE_KEYWORDS = (
    "fail", "failed", "error", "panic", "assert", "traceback", "warning", "exception", "fatal",
)

_NOISE_PATTERNS = (
    re.compile(r"^\s*$"),
    re.compile(r"^\s*Enumerating objects:"),
    re.compile(r"^\s*Counting objects:"),
    re.compile(r"^\s*Compressing objects:"),
    re.compile(r"^\s*Delta compression"),
    re.compile(r"^\s*Receiving objects:"),
    re.compile(r"^\s*Resolving deltas:"),
    re.compile(r"^\s*remote:\s*$"),
    re.compile(r"^\s*Using\s"),
)


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _strip_ansi(value: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", value)


def _is_noise(line: str) -> bool:
    return any(pattern.search(line) for pattern in _NOISE_PATTERNS)


def _extract_windows(lines: list[str], window_size: int = 2) -> list[str]:
    """Keeps lines matching keywords plus context around them."""
    if not lines:
        return []
    
    indices = [i for i, line in enumerate(lines) if any(kw in line.lower() for kw in _FAILURE_KEYWORDS)]
    if not indices:
        return lines[:10] + ["... (no errors found, showing first 10 lines)"] if len(lines) > 10 else lines

    keep = set()
    for idx in indices:
        for offset in range(-window_size, window_size + 1):
            target = idx + offset
            if 0 <= target < len(lines):
                keep.add(target)
    
    output = []
    last_idx = -1
    for idx in sorted(list(keep)):
        if last_idx != -1 and idx > last_idx + 1:
            output.append("---")
        output.append(lines[idx])
        last_idx = idx
    return output


def _bucketize_paths(lines: list[str]) -> list[str]:
    """Groups path-heavy lines (like find or git status) into tree-like buckets."""
    tree: dict[str, Any] = {}
    other: list[str] = []
    
    for line in lines:
        match = re.search(r"([A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+)", line)
        if not match:
            other.append(line)
            continue
        
        parts = match.group(1).split("/")
        curr = tree
        for p in parts[:-1]:
            curr = curr.setdefault(p, {})
        curr.setdefault("__files__", []).append(parts[-1])

    result = []
    def flatten(d: dict, indent: str = ""):
        for k, v in sorted(d.items()):
            if k == "__files__":
                if len(v) > 5:
                    result.append(f"{indent}  + {len(v)} files...")
                else:
                    for f in v: result.append(f"{indent}  - {f}")
            else:
                result.append(f"{indent}{k}/")
                flatten(v, indent + "  ")
    
    flatten(tree)
    return result + other


def _dedupe_lines(lines: list[str]) -> list[str]:
    counts: OrderedDict[str, tuple[str, int]] = OrderedDict()
    for line in lines:
        normalized = _normalize_whitespace(line)
        if not normalized: continue
        if normalized not in counts:
            counts[normalized] = (line.rstrip(), 1)
        else:
            original, count = counts[normalized]
            counts[normalized] = (original, count + 1)

    output = []
    for original, count in counts.values():
        output.append(original if count == 1 else f"{original} (x{count})")
    return output


def _truncate_smart(text: str, budget: int) -> str:
    if len(text) <= budget: return text
    head = int(budget * 0.7)
    tail = budget - head - 5
    return f"{text[:head].rstrip()}\n\n[... Truncated to fit token budget ...]\n\n{text[-tail:].lstrip()}"


def compact_output(kind: str, text: str, budget_chars: int = 1000) -> dict[str, Any]:
    raw = text or ""
    lines = [_strip_ansi(l) for l in raw.splitlines() if not _is_noise(l)]
    
    if kind == "mask":
        compacted = f"[OBSERVATION MASKED] {len(lines)} lines omitted."
    elif kind in {"test_output", "benchmark_output"}:
        compacted = "\n".join(_dedupe_lines(_extract_windows(lines)))
    elif kind in {"git_status", "ls_find", "rg"}:
        compacted = "\n".join(_bucketize_paths(lines))
    else:
        compacted = "\n".join(_dedupe_lines(lines))

    compacted = _truncate_smart(compacted, budget_chars).strip()
    
    raw_len, comp_len = len(raw), len(compacted)
    ratio = round(comp_len / max(1, raw_len), 4)
    tokens = max(0, int((raw_len - comp_len) / 4))
    
    return {
        "text": compacted,
        "estimated_tokens_saved": tokens,
        "metrics": {"raw": raw_len, "compact": comp_len, "ratio": ratio, "saved_tokens": tokens}
    }


def handle_request(request: dict) -> dict:
    if request.get("type") != "call_tool": return {"error": "Invalid request"}
    args = request.get("arguments", {})
    try:
        res = compact_output(args.get("kind", "summary"), args.get("text", ""), args.get("budget_chars", 1000))
        text = f"### Compacted Output ({args.get('kind')})\n{res['text']}\n\n"
        text += f"**Efficiency**: {res['metrics']['ratio']*100}% of original size. ~{res['metrics']['saved_tokens']} tokens saved."
        return {"content": [{"type": "text", "text": text}]}
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--describe":
        print(json.dumps({
            "tools": [{
                "name": "compact_output_text",
                "description": "Surgically compacts text to maximize information density.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "kind": {"type": "string", "enum": ["summary", "test_output", "benchmark_output", "git_status", "ls_find", "rg", "mask"]},
                        "text": {"type": "string"},
                        "budget_chars": {"type": "integer"}
                    },
                    "required": ["kind", "text"]
                }
            }]
        }))
        sys.exit(0)

    for line in sys.stdin:
        if not line.strip(): continue
        try:
            print(json.dumps(handle_request(json.loads(line))), flush=True)
        except:
            pass
