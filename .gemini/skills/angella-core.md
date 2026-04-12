# Angella Core Skill

This skill provides the **Hand** interface for the Angella Autoresearch Loop. Use this skill to interact with the Angella execution environment and persistent state.

## Runtime Configuration
- **Worker Model**: `<!--VAR:OLLAMA_MODEL_NAME-->supergemma4-26b-uncensored-v2<!--/VAR-->` (Tier: `local`)
- **Backend**: `ollama` (Port: `11434`)
- **Base URL**: `http://127.0.0.1:11434`

## Specialized MCP Tools (mcp-servers/)
- **`metric_benchmark.py`**: Executes performance tests and returns standardized JSON payloads.
- **`output_compactor.py`**: Summarizes massive text blobs into high-signal updates.
- **`scion_coordination_ops.py`**: Manages file claims and swarm-wide heartbeats.
- **`llmwiki_compiler_ops.py`**: Acts as the bridge to the permanent knowledge base (lessons/SOPs).
- **`archivist_ops.py`**: Performs health checks and meta-learning distillation.
- **`obsidian_auto_log.py`**: Formats and stores session records for human review.

## Available Resources
- `knowledge/log.md`: The append-only event stream for the current session.
- `knowledge/lessons.md`: The canonical store of technical meta-learning.

## Tool Execution Rules
1. **Context Compaction**: When processing large outputs (build logs, git diffs), ALWAYS call `compact_output` to maintain token efficiency.
2. **State Persistence**: Never end a turn after a significant decision without updating the session state or logs.
3. **Coordination**: In multi-agent scenarios, use `scion_claim_files` before editing shared project files.

## Common Workflows

### Running a Benchmark
1. Call `run_benchmark(command, metric_key, working_directory)`.
2. Call `compare_metrics(baseline, current, metric_key, threshold_percent)`.

### Memory Retrieval
1. Call `llmwiki_query(query, folder="lessons")` or search `knowledge/`.
2. Analyze the result for "Negative Memory" (past failures to avoid).

### Meta-Learning
1. Call `archivist_health_check` to validate the knowledge graph.
2. Call `distill_lessons` to extract patterns from recent logs.
