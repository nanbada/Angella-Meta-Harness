# Worker Pattern: ollama_gemma4_26b

Generated from accepted run `angella-live-setup-yes-warm-20260405-2342`.

## Use When

- objective component is `setup-yes-warm`
- worker id is `ollama_gemma4_26b`
- accepted run evidence count is `2`

## Resolved model

- provider: `ollama`
- model: `gemma4:26b`

## Execution Pattern

- accepted evidence summary: Accepted live setup-yes-warm fix for stale config overwrite under --yes install-only.
- keep prompts and eval scope tight around the repeated harness operation
- prefer deterministic benchmark and finalize paths over exploratory branching

## Avoid When

- Do not change normal interactive overwrite prompts
- Do not alter accepted-run export policy

## Validation

- install-only yes stale-config check passes
- setup flow tests pass
