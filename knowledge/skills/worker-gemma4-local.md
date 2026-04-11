# Worker Skill: SuperGemma 4 V2 Local Reasoning

- **Confidence**: high (based on SuperGemma 4 V2 benchmarks: Code 98.6, Logic 95.2)
- use as the main local implementation and reasoning worker when Angella needs an on-device path
- prefer privacy-constrained, token-constrained, or local knowledge tasks over general frontier-primary execution
- prefer SuperGemma 4 V2 over apfel for edits, refactors, schema work, and multi-step tool use
- keep context compact and focused around the benchmark contract
- use apfel only for short low-latency confirmation or question-answer assist

## Counter-arguments
- Local inference latency may still exceed frontier-flash models for extremely large contexts.
- MLX/Ollama setup requires specific local hardware (M3+ recommended).

## Data Gaps
- Long-term stability under continuous 24/7 swarm coordination not yet fully benchmarked.
