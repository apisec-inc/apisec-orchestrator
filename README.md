# APIsec Surface org scan

Scans the repositories in your GitHub organization every night with [APIsec Surface](https://www.apisec.ai)
and uploads the results to APIsec. Only repositories pushed to since the last scan are analyzed.

It runs in your organization, on your runners, with your secrets. Only the Surface analysis results are
sent to APIsec.

## Setup

1. Create a repository in your org from the
   [template](https://github.com/apisec-inc/apisec-surface-scan-template) (**Use this template**), or create
   any repository and add [`templates/apisec-scan.yml`](templates/apisec-scan.yml) as
   `.github/workflows/apisec-scan.yml`.
2. Add secrets (Settings → Secrets and variables → Actions, at org or repository level):

   | Secret | Value |
   |---|---|
   | `APISEC_TOKEN` | APIsec personal access token |
   | `ORG_READ_TOKEN` | Fine-grained GitHub PAT for the org with **Contents: read** and **Metadata: read** |

3. Add the variable `APISEC_ENDPOINT` with your APIsec API URL, e.g. `https://api.apisecapps.com`.
4. Actions → **APIsec Surface org scan** → **Run workflow**. Optionally enable **dry_run** first to
   verify setup (repos are analyzed locally; nothing is uploaded to APIsec).
5. Run without **dry_run** to upload results. After that, scans run nightly at 02:00 UTC.

For a first scan of a large org, set **max_repos** (e.g. `100`) and run until the plan is empty. To
queue those runs with one command instead, see [Scanning a large org in batches](#scanning-a-large-org-in-batches).

### Optional variables

| Variable | Default | Purpose |
|---|---|---|
| `THROUGHPUT` | `2` | Repositories scanned in parallel (1–10) |
| `ORCHESTRATOR_RUNNER` | `github-hosted` | `self-hosted` runs every job on runners labelled `self-hosted` and `apisec` |
| `APISEC_RUN_PROFILE` | `surface` | `legacy` publishes only a committed OpenAPI contract |
| `TARGET_ORG` | this org | Scan a different org |
| `EXCLUDE_REPOS` | | Comma-separated `owner/repo` names to skip |
| `APISEC_LLM_ENRICHMENT` | on | `0` keeps source snippets out of LLM-assisted route discovery |
| `APISEC_CLI_VERSION` | pinned | Override the Surface CLI version |

Self-hosted runners need Python 3.10+, git, and outbound access to GitHub, PyPI and `APISEC_ENDPOINT`.

## Scanning a large org in batches

[`tools/surface_backfill.py`](tools/surface_backfill.py) runs the workflow several times in a row
from your machine with the GitHub CLI, each run with its own **max_repos** and parallel scans. Each
run starts when the previous one has finished, so it skips what the previous run scanned. The series
stops early once there is nothing left to scan.

```
python3 surface_backfill.py OWNER/REPO --batch 25:2,100:4,200:6x5 --preview   # show the plan
python3 surface_backfill.py OWNER/REPO --batch 25:2,100:4,200:6x5             # run it
```

A batch is `MAX_REPOS[:PARALLEL][xCOUNT]`: `200:6x5` is five runs of up to 200 repositories, 6 at a
time. It needs Python 3.9+ and `gh` logged in with write access to OWNER/REPO, the repository that
runs this workflow. Keep it running until the series ends. Runs that are already going continue on
GitHub if it stops, and you can run it again with the batches that are left.

PARALLEL is passed as the workflow's **throughput** input. Workflows made from an older template
have no such input; for them, the script sets the repository variable `THROUGHPUT` for each run
and restores it at the end, which requires admin access. If the script is interrupted before
restoring it, run it again with `--restore-throughput`.

## Updates

Your workflow calls `scan.yml@v1`. Each release moves `v1`, so fixes reach you on the next nightly run
with no change on your side. Breaking changes ship as `v2`. To control updates yourself, replace `@v1`
with a release tag such as `@v1.0.0`.

## Organizations that only allow their own workflows

If your org policy blocks workflows from `apisec-inc`, use
[`templates/apisec-scan-standalone.yml`](templates/apisec-scan-standalone.yml) instead. It runs the
same jobs inline and installs the latest `apisec-orgscan` 1.x from PyPI on each run, so fixes still
arrive without editing it. Setup is otherwise identical.

## Moving from the zip version

Either way, applications in APIsec are matched by each scanned repository's GitHub id, so no duplicates
are created.

- **Start fresh:** delete the old orchestrator repository and follow [Setup](#setup). The first run
  rescans every repository once.
- **Keep your repository:** replace `.github/workflows/orchestrator.yml` with
  [`templates/apisec-scan.yml`](templates/apisec-scan.yml) and delete `scripts/`. Secrets, variables and
  the record of scanned repositories carry over, so nothing is rescanned.

If APIsec created applications for your repositories from OpenAPI specs before you used this workflow,
ask APIsec to link them to their repositories before the first full scan.

## Development

```
pip install -e ".[dev]"
ruff check . && ruff format --check . && pytest
```

`src/apisec_orgscan` holds the logic (`plan`, `scan`, `record`, `merge`); `.github/workflows/scan.yml`
holds the GitHub-only parts (matrix fan-out, runners, artifacts).

### Releasing

1. Set `__version__` in `src/apisec_orgscan/__init__.py` and run `python scripts/sync_templates.py`
   (pins the workflow and regenerates the standalone template).
2. Merge, then push tag `vX.Y.Z`. The release workflow tests, publishes to PyPI and moves `vX`.

Tags such as `v1.1.0rc1` publish a pre-release without moving `v1`; point a test caller at that tag.
