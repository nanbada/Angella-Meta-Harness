#!/usr/bin/env python3
"""
Obsidian Auto-Log MCP Server
==============================
Autoresearch loop의 Transparency를 구현합니다.
매 iteration마다 ratchet 결과 + git diff + metric을 
Obsidian vault (또는 로컬 logs/ 디렉토리)에 자동 저장.

환경변수:
  OBSIDIAN_VAULT_PATH — Obsidian vault 경로 (기본값: ./logs)
"""

import datetime
import os
import json

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

server = Server("obsidian-auto-log")

VAULT_PATH = os.environ.get("OBSIDIAN_VAULT_PATH", "./logs")


def _get_log_dir() -> str:
    """로그 디렉토리 경로 반환 (Goose Logs 하위)"""
    log_dir = os.path.join(VAULT_PATH, "Goose Logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="save_loop_log",
            description="Self-Optimize Loop의 iteration 결과를 Obsidian vault (또는 로컬 로그)에 Markdown으로 저장합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {
                        "type": "string",
                        "description": "프로젝트 이름",
                    },
                    "iteration": {
                        "type": "integer",
                        "description": "현재 iteration 번호",
                    },
                    "metric_key": {
                        "type": "string",
                        "description": "측정한 메트릭 키",
                    },
                    "metric_value": {
                        "type": "number",
                        "description": "현재 메트릭 값",
                    },
                    "baseline_value": {
                        "type": "number",
                        "description": "baseline 메트릭 값",
                    },
                    "improvement": {
                        "type": "boolean",
                        "description": "개선 여부 (keep/revert)",
                    },
                    "git_diff": {
                        "type": "string",
                        "description": "변경 사항 (git diff 출력)",
                        "default": "",
                    },
                    "summary": {
                        "type": "string",
                        "description": "이번 iteration 요약",
                    },
                    "proposals": {
                        "type": "string",
                        "description": "시도한 개선 아이디어들",
                        "default": "",
                    },
                },
                "required": ["project_name", "iteration", "metric_key", "metric_value", "improvement", "summary"],
            },
        ),
        types.Tool(
            name="save_final_report",
            description="Self-Optimize Loop 완료 후 최종 보고서를 저장합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {
                        "type": "string",
                        "description": "프로젝트 이름",
                    },
                    "total_iterations": {
                        "type": "integer",
                        "description": "총 iteration 횟수",
                    },
                    "initial_metric": {
                        "type": "number",
                        "description": "시작 메트릭 값",
                    },
                    "final_metric": {
                        "type": "number",
                        "description": "최종 메트릭 값",
                    },
                    "metric_key": {
                        "type": "string",
                        "description": "메트릭 키",
                    },
                    "improvements_kept": {
                        "type": "integer",
                        "description": "keep된 개선 횟수",
                    },
                    "full_git_diff": {
                        "type": "string",
                        "description": "전체 git diff (시작~종료)",
                        "default": "",
                    },
                    "summary": {
                        "type": "string",
                        "description": "최종 요약",
                    },
                },
                "required": ["project_name", "total_iterations", "initial_metric", "final_metric", "metric_key", "summary"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "save_loop_log":
        project_name = arguments["project_name"]
        iteration = arguments["iteration"]
        metric_key = arguments["metric_key"]
        metric_value = arguments["metric_value"]
        baseline = arguments.get("baseline_value", 0)
        improvement = arguments["improvement"]
        git_diff = arguments.get("git_diff", "")
        summary = arguments["summary"]
        proposals = arguments.get("proposals", "")

        today = datetime.date.today().isoformat()
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        filename = f"{today}-autoresearch-{project_name}.md"
        filepath = os.path.join(_get_log_dir(), filename)

        verdict = "✅ KEEP (ratchet forward)" if improvement else "❌ REVERT (no improvement)"

        content = f"""
---

## Iteration {iteration} — {now}

| Key | Value |
|-----|-------|
| **Metric** | `{metric_key}` |
| **Baseline** | `{baseline}` |
| **Current** | `{metric_value}` |
| **Verdict** | {verdict} |

### Summary
{summary}

"""
        if proposals:
            content += f"""### Proposals Tried
{proposals}

"""
        if git_diff:
            content += f"""### Git Diff
```diff
{git_diff[:3000]}
```

"""
        content += "*Generated by Goose M3 Autoresearch Loop (MLX Optimized)*\n"

        # 파일이 없으면 헤더 추가
        if not os.path.exists(filepath):
            header = f"""# 🔬 Autoresearch Loop — {project_name}
**Date**: {today}
**Metric**: `{metric_key}`
**Engine**: Goose M3 Autoresearch (MLX Optimized)

"""
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(header)

        with open(filepath, "a", encoding="utf-8") as f:
            f.write(content)

        return [types.TextContent(
            type="text",
            text=json.dumps({
                "status": "saved",
                "filepath": os.path.abspath(filepath),
                "iteration": iteration,
                "verdict": verdict,
            }, ensure_ascii=False)
        )]

    elif name == "save_final_report":
        project_name = arguments["project_name"]
        total = arguments["total_iterations"]
        initial = arguments["initial_metric"]
        final = arguments["final_metric"]
        metric_key = arguments["metric_key"]
        kept = arguments.get("improvements_kept", 0)
        git_diff = arguments.get("full_git_diff", "")
        summary = arguments["summary"]

        lower_is_better = metric_key in ("build_time", "latency_ms", "bundle_size")
        if initial > 0:
            if lower_is_better:
                change_pct = round(((initial - final) / initial) * 100, 2)
            else:
                change_pct = round(((final - initial) / initial) * 100, 2)
        else:
            change_pct = 0.0

        today = datetime.date.today().isoformat()
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        filename = f"{today}-autoresearch-{project_name}-FINAL.md"
        filepath = os.path.join(_get_log_dir(), filename)

        content = f"""# 🏁 Autoresearch Final Report — {project_name}

**Completed**: {now}
**Total Iterations**: {total}
**Improvements Kept**: {kept} / {total}

## Results

| Metric | Initial | Final | Change |
|--------|---------|-------|--------|
| `{metric_key}` | {initial} | {final} | **{'+' if change_pct > 0 else ''}{change_pct}%** |

## Summary
{summary}

"""
        if git_diff:
            content += f"""## Full Git Diff (Start → End)
```diff
{git_diff[:5000]}
```

"""
        content += """---
*Generated by Goose M3 Autoresearch Loop (MLX Optimized)*
"""

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        return [types.TextContent(
            type="text",
            text=json.dumps({
                "status": "final_report_saved",
                "filepath": os.path.abspath(filepath),
                "total_iterations": total,
                "improvement_percent": change_pct,
            }, ensure_ascii=False)
        )]

    return [types.TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
