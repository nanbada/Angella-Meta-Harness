# Worker Pattern: SuperGemma 4 V2 (Ollama)

- **Confidence**: high (migrated from gemma4:26b with verified benchmark improvements)
- Generated from accepted run `angella-live-setup-yes-warm-20260405-2342`.

## Use When

- objective component is `setup-yes-warm`
- worker id is `ollama_gemma4_26b` (resolves to supergemma4-26b-uncensored-v2)
- accepted run evidence count is `2`

## Resolved model

- provider: `ollama`
- model: `supergemma4-26b-uncensored-v2`

## Execution Pattern

- accepted evidence summary: Accepted live setup-yes-warm fix for stale config overwrite under --yes install-only.
- keep prompts and eval scope tight around the repeated harness operation
- prefer deterministic benchmark and finalize paths over exploratory branching

## Avoid When

- Do not change normal interactive overwrite prompts
- Do not alter accepted-run export policy

## Counter-arguments
- Higher parameter efficiency may occasionally lead to over-confidence in edge cases compared to the more conservative base IT model.

## Data Gaps
- Tool-call stability under the specific `ollama_proxy.py` parsing logic for V2 needs continuous monitoring.

## Validation

- install-only yes stale-config check passes
- setup flow tests pass
