# Source: Worker Pattern: SuperGemma 4 V2 (Ollama)

- source type: `tracked_knowledge`
- source path: `knowledge/skills/worker-ollama-gemma4-26b.md`
- source id: `source-knowledge-skills-worker-ollama-gemma4-26b-md`

## Summary

- Worker pattern for setup tasks using SuperGemma 4 V2 via Ollama.

## Mirror Content
- **Confidence**: high (migrated from gemma4:26b with verified benchmark improvements)
- Generated from accepted run `angella-live-setup-yes-warm-20260405-2342`.

### Use When
- objective component is `setup-yes-warm`
- worker id is `ollama_gemma4_26b` (resolves to supergemma4-26b-uncensored-v2)
- accepted run evidence count is `2`

### Execution Pattern
- accepted evidence summary: Accepted live setup-yes-warm fix for stale config overwrite under --yes install-only.
- keep prompts and eval scope tight around the repeated harness operation
- prefer deterministic benchmark and finalize paths over exploratory branching

### Counter-arguments
- Higher parameter efficiency may occasionally lead to over-confidence in edge cases compared to the more conservative base IT model.

### Data Gaps
- Tool-call stability under the specific `ollama_proxy.py` parsing logic for V2 needs continuous monitoring.

## Backlinks

- [knowledge/index.md](../index.md)
- [knowledge/log.md](../log.md)
