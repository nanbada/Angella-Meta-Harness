# Angella Core Skill

This skill provides the **Hand** interface for the Angella Autoresearch Loop. Use this skill to interact with the Angella execution environment and persistent state.

## Runtime Configuration
- **Worker Model**: `<!--VAR:OLLAMA_MODEL_NAME-->gemma-4-26B-A4B-it-GGUF<!--/VAR-->` (Tier: `local`)
- **Backend**: `ollama` (Port: `11434`)
- **Base URL**: `http://127.0.0.1:11434`

## Available Resources
- `knowledge/log.md`: The append-only event stream for the current session.
- `knowledge/lessons.md`: The canonical store of technical meta-learning.
- `mcp-servers/*.py`: Specialized tools for metrics, coordination, and compaction.

## Tool Execution Rules
1. **Context Compaction**: When processing large outputs (build logs, git diffs), ALWAYS call `compact_output` to maintain token efficiency.
2. **State Persistence**: Never end a turn after a significant decision without calling `save_loop_log` or updating the session state.
3. **Coordination**: In multi-agent scenarios, use `scion_claim_files` to prevent concurrent write collisions.

## Common Workflows

### Running a Benchmark
1. Ensure the worktree is on the target commit.
2. Call `run_benchmark(command, metric_key, working_directory)`.
3. Call `compare_metrics(baseline, current, metric_key, threshold_percent)`.

### Memory Retrieval
1. Call `llmwiki_query(query, folder="lessons")`.
2. Analyze the result for "Negative Memory" (past failures to avoid).

### Meta-Learning
1. Call `archivist_health_check` to validate the knowledge graph.
2. Call `distill_lessons` (if implemented in MCP) to extract patterns.
