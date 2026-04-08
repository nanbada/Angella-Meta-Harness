# `setup.sh --check` Optimization History

This document captures the optimization history that was executed in a clean temp run repository derived from commit `b999b49`'s working tree predecessor, using the run branch `angella/run-20260405-161927`.

The run was executed in a disposable clone at `/tmp/angella-e2e.QMd1Qf` so the primary repository worktree could remain untouched while benchmarking and ratcheting candidate changes.

## Objective

- Target command: `bash setup.sh --check`
- Metric: `build_time`
- Keep threshold: `1.0%`
- Non-goals:
  - changing setup semantics
  - weakening template validation
  - removing runtime safety checks
  - relying on dirty worktrees or manual shortcuts

## Baseline

- Start commit: `a194039c2d66f5f389c397be2ad2b632c6c2d0b0`
- Baseline wall-clock: `0.74s`
- Clean run branch: `angella/run-20260405-161927`

## Accepted Iterations

### Iteration 1

- Commit: `6d499be5ec76188ea35ebbcb0c107a5cb4fe720e`
- Change: cache Ollama `/api/tags` output and reuse it for model existence checks instead of calling `ollama list`
- Result:
  - cold run: `0.39s`
  - follow-up runs: `0.29s`, `0.28s`
- Improvement vs previous baseline: `47.3%`

### Iteration 2

- Commit: `df9f656d7a81cc80c96d20157a462a07a65ccdb3`
- Change: replace `python -m pip --version` with `python -c "import pip"` for pip availability probing
- Result:
  - cold run: `0.25s`
  - follow-up runs: `0.19s`, `0.18s`
- Improvement vs previous baseline: `35.9%`

### Iteration 3

- Commit: `ec0416b4690eee938afe0ac263cfd6294facba6e`
- Change: replace external `sed` invocation in `escape_sed_replacement` with shell parameter expansion
- Result:
  - cold run: `0.23s`
  - follow-up runs: `0.18s`, `0.19s`, `0.17s`, `0.17s`
- Improvement vs previous baseline: `8.0%`

## Rejected Candidates

These candidates were measured and intentionally not kept because their cold-run result did not improve on the accepted baseline:

- skip Homebrew / version probes in `--check`
- skip only `goose --version` in `--check`
- skip only `ollama --version` in `--check`
- batch template verification changes that worsened cold-run latency

## Final Outcome

- Final accepted commit on temp run branch: `ec0416b4690eee938afe0ac263cfd6294facba6e`
- Final measured cold-run time: `0.23s`
- Overall improvement from `0.74s` to `0.23s`: `68.92%`

## Notes

- Goose CLI recipe execution was attempted directly, but the CLI entered an interactive state and did not progress reliably past the first shell tool call in this automation session.
- To preserve the intended ratchet contract, the iterations were executed manually against the same run rules: clean worktree, dedicated run branch, baseline-first measurement, one change per iteration, keep only on measured improvement.
- The accepted changes from this temp run have already been incorporated into the primary repository history; this branch exists to preserve the experimental history in a durable, reviewable form.
