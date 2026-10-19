# Release 1.0.0 — team review

**Status:** Not published. No PyPI release and no `v1` tag until this review is approved.

## What changed

- **Distribution:** Zip copy in customer repos → public reusable workflow `@v1` + PyPI package `apisec-orgscan` + [template repo](https://github.com/apisec-inc/apisec-surface-scan-template).
- **Old repo:** `apisec-inc/apisec-orchestrator` renamed and archived as [`apisec-orchestrator-internal`](https://github.com/apisec-inc/apisec-orchestrator-internal) (zip demos still work there).
- **Customer keeps:** One short workflow file; secrets `APISEC_TOKEN`, `ORG_READ_TOKEN`; variable `APISEC_ENDPOINT`.
- **Fallback:** `templates/apisec-scan-standalone.yml` for orgs that block `apisec-inc/*` workflows.

## QA testing (`apisec-fixtures`)

Cross-org caller → `apisec-inc/apisec-orchestrator` (`test` branch installs package from GitHub; `@v1` will use PyPI after publish).

| Check | Result |
|---|---|
| Zip → short caller migration (secrets/vars/cache kept) | Pass |
| Dry run (full org plan + analyze, no upload) | Pass (168/171 jobs; 3 repo failures in Surface CLI) |
| Real upload (`max_repos=5`, QA endpoint) | Pass |
| Second run skips unchanged repos | Pass (5 excluded from plan) |
| Scan failures fail the job (not hidden) | Pass |

**Surface CLI 1.0.0 (not orchestrator):** analysis errors on `cx-jaxrs-modeshape`, `cx-spring-conductor` (`substring not found`), `cx-dotnet-practical.cleanarchitecture` (`is_relative_to`). One repo (`cx-micronaut-kestra`) took ~25 min on upload (orchestrator scan job timeout is 30 min).

## Publish checklist (after approval)

1. Set `__version__` to `1.0.0`, run `python scripts/sync_templates.py`, merge.
2. Sync [apisec-surface-scan-template](https://github.com/apisec-inc/apisec-surface-scan-template) if caller template changed.
3. Tag `v1.0.0` → approve **pypi** environment → PyPI publish + move `v1`.
4. Smoke test in `apisec-fixtures` with `@v1` (not `test` branch).
5. CS: template link + zip migration section in README.

## Review focus

- Reusable workflow: secrets by name, permissions, artifact store, throughput cap 10.
- Security: only analysis results leave the org; token handling on artifact restore.
- Onboarding: README + template sufficient for CS.
