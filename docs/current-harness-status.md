# Current Harness Status

This file is a handoff snapshot for the current Angella architecture.

## Architecture Paradigm Shift

Angella has transitioned from a rigid Autoresearch "Meta-Loop" (which relied on heavy Python test-driven scaffolding) to a **Personal Agent & LLM-Wiki** paradigm. 
- Over 160KB of legacy over-engineered code (e.g., `meta_loop_ops.py`, `control_plane.py`) has been **purged** to maximize token efficiency.
- The primary operation mode is now the `personal-agent-loop`, optimized for Apple Silicon (Mac M3 Pro).

## Hardware & Model Policy (Gemma 4 + MLX + TurboQuant)

- **Target Hardware:** MacBook Pro M3 36GB
- **Target Model:** `dealignai/Gemma-4-31B-JANG_4M-CRACK` (approx. 18GB VRAM usage, leaving ~18GB for macOS and KV Cache).
- **Tooling Constraints:** Since Gemma 4 native tool-calling (`<|tool_call|>`) is not fully parsed by standard `mlx-lm` yet, the Angella Harness provides scaffolding via `personal-agent-loop` to intercept and safely process tool calls.
- **Engine:** Requires `vMLX 1.3.26+` or equivalent advanced inference servers to support the Gemma 4 Sliding Window Attention structures.

## Verified Paths & Components

- **LLM-Wiki Compiler:** Replaced legacy RAG and SQLite Vector DBs with `npx llm-wiki-compiler`. The agent autonomously updates interconnected markdown files in `knowledge/sources/`.
- **Output Compactor:** Repaired `mcp-servers/output_compactor.py` to function natively via MCP stdio, successfully shrinking large output dumps (e.g., grep, terminal outputs) to drastically save LLM tokens.
- **Personal Context Integrations:** OS-level integrations via AppleScript (Calendar events, Reminders) are fully functional through `personal_context_ops.py`.
- **Secrets Management:** Managed securely away from Git via `.env.agents` logic.

## Next Likely Tasks

1. Extend `llmwiki_compiler_ops.py` to seamlessly execute vector semantic searches using the newly structured wiki.
2. Setup and integrate the local vMLX API server endpoint into `config/harness-profiles.yaml` for Gemma 4.
3. Observe and mitigate potential Gemma 4 4-bit hallucination during deep reasoning by heavily enforcing the Karpathy "ingest & compile" wiki workflow.
