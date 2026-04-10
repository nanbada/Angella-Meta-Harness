# Security Notes

## Local secrets

- Do not commit `.env`, `.env.*`, private keys, certificates, or local-only model files.
- Use [`.env.mlx.example`](.env.mlx.example) as the tracked template and keep the real `.env.mlx` local only.
- `reference.md` is treated as a local-only scratch file and is ignored.

## Local safeguards

- Secret scanning script: [`scripts/check-secrets.sh`](scripts/check-secrets.sh)
- Commit hook entrypoint: [`.githooks/pre-commit`](.githooks/pre-commit)
- Hook installer: [`scripts/install-hooks.sh`](scripts/install-hooks.sh)
- CI checks: [`.github/workflows/repo-checks.yml`](.github/workflows/repo-checks.yml)

To enable the repository-local hooks:

```bash
bash scripts/install-hooks.sh
```

## GitHub settings that still need manual enforcement

The repository is private and the GitHub API currently returns a `403` when querying branch protection for `main`, which indicates branch protection/ruleset enforcement is not available on the current plan for this repository.

Manual follow-up:

1. Upgrade to a plan that supports branch protection on private repositories, or make the repository public if that is acceptable.
2. Enable a ruleset or branch protection for `main`:
   - require pull requests
   - block direct pushes
   - block force pushes
   - require passing status checks
3. Enable GitHub secret scanning / push protection if the plan supports it.

## History rewrite note

The previously tracked `.env.mlx` file was removed from git history and all active remote branches were force-pushed.

If you already have a local clone, resync with:

```bash
git fetch --all --prune
git switch main
git reset --hard origin/main
```
