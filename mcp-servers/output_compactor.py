#!/usr/bin/env python3
"""Deterministic output compaction helpers for Angella."""

from __future__ import annotations

import math
import re
from collections import OrderedDict
from typing import Any


_FAILURE_KEYWORDS = (
    "fail",
    "failed",
    "error",
    "panic",
    "assert",
    "traceback",
    "warning",
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


def _prioritize_failure_lines(lines: list[str]) -> list[str]:
    selected = [line for line in lines if any(keyword in line.lower() for keyword in _FAILURE_KEYWORDS)]
    return selected or lines


def _group_path_lines(lines: list[str]) -> list[str]:
    groups: "OrderedDict[str, list[str]]" = OrderedDict()
    passthrough: list[str] = []
    for line in lines:
        match = re.search(r"([A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+)", line)
        if not match:
            passthrough.append(line)
            continue
        relpath = match.group(1).strip("/")
        bucket = relpath.split("/", 1)[0]
        groups.setdefault(bucket, []).append(line)

    grouped: list[str] = []
    for bucket, items in groups.items():
        grouped.append(f"{bucket}/ ({len(items)} lines)")
        grouped.extend(items[:3])
        if len(items) > 3:
            grouped.append(f"... {len(items) - 3} more lines in {bucket}/")
    grouped.extend(passthrough)
    return grouped


def _dedupe_lines(lines: list[str]) -> list[str]:
    counts: "OrderedDict[str, tuple[str, int]]" = OrderedDict()
    for line in lines:
        normalized = _normalize_whitespace(line)
        if not normalized:
            continue
        if normalized not in counts:
            counts[normalized] = (line.rstrip(), 1)
            continue
        original, count = counts[normalized]
        counts[normalized] = (original, count + 1)

    output: list[str] = []
    for original, count in counts.values():
        if count == 1:
            output.append(original)
            continue
        output.append(f"{original} (x{count})")
    return output


def _truncate_text(text: str, budget_chars: int) -> str:
    if budget_chars <= 0 or len(text) <= budget_chars:
        return text
    if budget_chars <= 40:
        return text[:budget_chars].rstrip()
    head = max(20, int(budget_chars * 0.65))
    tail = max(10, budget_chars - head - 5)
    return f"{text[:head].rstrip()}\n...\n{text[-tail:].lstrip()}"


def _preprocess_lines(kind: str, text: str) -> list[str]:
    lines = [_strip_ansi(line.rstrip()) for line in text.splitlines()]
    lines = [line for line in lines if not _is_noise(line)]
    if kind in {"test_output", "benchmark_output"}:
        lines = _prioritize_failure_lines(lines)
    if kind in {"git_status", "rg", "ls_find"}:
        lines = _group_path_lines(lines)
    return _dedupe_lines(lines)


def compact_output(
    kind: str,
    text: str,
    *,
    budget_chars: int = 600,
) -> dict[str, Any]:
    raw = text or ""
    cleaned = _preprocess_lines(kind, raw)
    compacted = "\n".join(cleaned).strip()
    if not compacted:
        compacted = _normalize_whitespace(raw)
    compacted = _truncate_text(compacted, budget_chars).strip()
    if kind == "summary":
        compacted = compacted.replace("\n...\n", " ... ").replace("\n", " ").strip()

    raw_chars = len(raw)
    compact_chars = len(compacted)
    ratio = 1.0 if raw_chars == 0 else round(compact_chars / raw_chars, 4)
    estimated_tokens_saved = max(0, int(math.ceil(max(0, raw_chars - compact_chars) / 4)))
    return {
        "kind": kind,
        "text": compacted,
        "raw_chars": raw_chars,
        "compact_chars": compact_chars,
        "compaction_ratio": ratio,
        "estimated_tokens_saved": estimated_tokens_saved,
    }


def telemetry_block(compacted: dict[str, Any]) -> dict[str, Any]:
    return {
        "raw_chars": compacted.get("raw_chars", 0),
        "compact_chars": compacted.get("compact_chars", 0),
        "compaction_ratio": compacted.get("compaction_ratio", 1.0),
        "estimated_tokens_saved": compacted.get("estimated_tokens_saved", 0),
    }
