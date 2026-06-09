# Xero CI

F0002 adds a GitHub Actions pipeline at `.github/workflows/ci.yml`.

## Required Checks

Configure a GitHub repository ruleset or branch protection rule for `main` that requires these status checks before merge:

- `backend`
- `frontend`
- `docker-build`
- `compose-e2e`

Use strict required status checks when the repository is hosted on GitHub so pull requests must be up to date before merging.

## Local Validation

The primary local checks are:

```powershell
cd platform
python scripts/ci.py backend-lint
python scripts/ci.py openapi-check
python scripts/ci.py backend-unit
python scripts/ci.py backend-behave
python scripts/ci.py frontend-lint
python scripts/ci.py frontend-test
python scripts/ci.py frontend-build
docker compose up -d --build
python scripts/ci.py backend-integration
python scripts/ci.py playwright
```

To run the GitHub workflow locally, install `act` and run:

```powershell
winget install --id nektos.act --exact
act push
```

If using the GitHub CLI extension instead:

```powershell
gh extension install nektos/gh-act
gh act push
```

This repository includes `.actrc` defaults for the `catthehacker/ubuntu:act-latest` runner image. The same workflow can be inspected or run job-by-job with:

```powershell
gh act push --list
gh act push --job backend
gh act push --job frontend
gh act push --job docker-build
gh act push --job compose-e2e
```

The compose E2E job uses `COMPOSE_PROJECT_NAME=xero-ci`, `BACKEND_PORT=18000`, and `FRONTEND_PORT=13000` so local workflow runs do not collide with the default developer stack. Local `act` runs skip GitHub artifact upload steps because `act` does not provide GitHub's `ACTIONS_RUNTIME_TOKEN`; hosted GitHub Actions runs still upload the configured artifacts. In a workspace without `.git` metadata, `act` can also print ref/revision warnings while still running the jobs.

## Artifacts

The `docker-build` job uploads Docker image metadata. The `compose-e2e` job uploads Compose logs and Playwright failure artifacts when a smoke test fails.
