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
2. Give the workflow read access to the repositories to scan, either with a GitHub App (recommended) or a
   personal access token. See [GitHub access](#github-access).
3. Add the secret `APISEC_TOKEN` (your APIsec personal access token) and the variable `APISEC_ENDPOINT`
   (your APIsec API URL, e.g. `https://api.apisecapps.com`). Use Settings → Secrets and variables →
   Actions, at org or repository level.
4. Actions → **APIsec Surface org scan** → **Run workflow**. Optionally enable **dry_run** first to
   verify setup (repos are analyzed locally; nothing is uploaded to APIsec).
5. Run without **dry_run** to upload results. After that, scans run nightly at 02:00 UTC.

For a first scan of a large org, set **max_repos** (e.g. `100`) and run until the plan is empty.

### GitHub access

**GitHub App (recommended).** The app belongs to the org rather than to a person, its key does not
expire, and the repositories selected on its installation are exactly what gets scanned.

1. Org → Settings → Developer settings → GitHub Apps → **New GitHub App**. Any name and homepage URL;
   untick **Webhook → Active**. Repository permissions: **Contents: Read-only** and **Metadata:
   Read-only**, nothing else. Install only on this account.
2. **Generate a private key** (a `.pem` file downloads), then **Install App** on the org and choose
   **All repositories** or the repositories to scan.
3. Add the variable `ORCHESTRATOR_APP_ID` with the app's App ID or Client ID, and the secret
   `ORCHESTRATOR_APP_PRIVATE_KEY` with the full contents of the `.pem` file. If you add the secret at
   org level, limit its access to the repository that runs this workflow.

Each job mints its own short-lived installation token, and each scan job's token can read only the
repository it scans. Use a dedicated app for this rather than one that serves other purposes, so it
holds no more access than the scan needs.

To rotate the key, generate a second private key on the app, replace the secret, confirm a run
succeeds, then delete the old key.

**Personal access token.** Instead of an app, add the secret `ORG_READ_TOKEN`: a fine-grained PAT
for the org with **Contents: read** and **Metadata: read** on the repositories to scan. Some orgs must
approve fine-grained PATs first. The token stops working when it expires or when its owner loses
access to the org. If both are set, the app is used.

### Optional variables

| Variable | Default | Purpose |
|---|---|---|
| `THROUGHPUT` | `2` | Repositories scanned in parallel (1–10) |
| `ORCHESTRATOR_RUNNER` | `github-hosted` | `self-hosted` runs every job on runners labelled `self-hosted` and `apisec` |
| `APISEC_RUN_PROFILE` | `surface` | `legacy` publishes only a committed OpenAPI contract |
| `TARGET_ORG` | this org | Scan a different org (the GitHub App must be installed there) |
| `EXCLUDE_REPOS` | | Comma-separated `owner/repo` names to skip |
| `APISEC_LLM_ENRICHMENT` | on | `0` keeps source snippets out of LLM-assisted route discovery |
| `APISEC_REGISTRATION_CODE` | `ci-orchestrator` | Registration code the scanned apps are registered with |
| `APISEC_CLI_VERSION` | newest 1.x | Pin the Surface CLI to one release, e.g. `1.2.0`, for change control or to hold back a bad release |

Self-hosted runners must run Linux (x64 or arm64) with git, and need outbound access to GitHub, PyPI and
`APISEC_ENDPOINT`; each job installs its own Python. macOS runners are not supported: there,
`actions/setup-python` installs Python only under `/Users/runner/hostedtoolcache`.

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
   (sets the workflow's `apisec-orgscan` range, e.g. `>=1.1,<2`, and regenerates the standalone template).
   Runs use the newest release in that range, so a patch or minor release reaches `@v1` callers
   without a new tag; a workflow change still needs one.
2. Merge, then push tag `vX.Y.Z`. The release workflow tests, publishes to PyPI and moves `vX`.

Tags such as `v1.1.0rc1` publish a pre-release without moving `v1`; point a test caller at that tag.
