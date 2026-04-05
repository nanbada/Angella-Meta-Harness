# Failure Harvest And Promotion SOP

When the same failure class appears in at least two runs:

1. normalize the failure artifact
2. link reproduction and observed/expected output
3. check whether an accepted fix already exists
4. generate a control-plane draft under `.cache/angella/control-plane/knowledge/`
5. if the promotion rule is satisfied, promote the draft into tracked `knowledge/sops/` or `knowledge/skills/`
6. if the tracked target already exists, append a run-scoped addendum instead of silently skipping the promotion
7. periodically prune stale draft and queue artifacts once they are no longer actionable

Promotion triggers:

- same failure class appears at least twice
- the same worker model has accepted fixes in at least two runs
- or the operator explicitly confirms the pattern is reusable
