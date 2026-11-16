"""External Integrations inventory APIs (scan-plan, scan-result). Optional; fallback to cache."""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Mapping
from typing import Any

UPLOAD_EXIT_CODE = 2


def _integrations_base(env: Mapping[str, str]) -> str | None:
    explicit = (env.get("APISEC_INTEGRATIONS_URL") or "").strip().rstrip("/")
    if explicit:
        return explicit
    endpoint = (env.get("APISEC_ENDPOINT") or "").strip().rstrip("/")
    if not endpoint:
        return None
    for suffix in ("/v1/applications", "/applications"):
        if endpoint.endswith(suffix):
            return endpoint[: -len(suffix)]
    return endpoint


def _auth_pat(env: Mapping[str, str]) -> str:
    return (env.get("APISEC_PAT") or env.get("APISEC_TOKEN") or "").strip()


def _connection_id(env: Mapping[str, str]) -> str:
    return (env.get("APISEC_CONNECTION_ID") or "").strip()


def plan_candidates(
    env: Mapping[str, str],
    *,
    scan_mode: str,
    max_repos: int,
    force_full_scan: bool,
) -> list[dict[str, Any]] | None:
    """Return matrix candidates from APIsec scan-plan, or None to use the local cache."""
    base = _integrations_base(env)
    connection_id = _connection_id(env)
    pat = _auth_pat(env)
    if not base or not connection_id or not pat:
        return None

    body = json.dumps(
        {
            "connectionId": connection_id,
            "scanMode": scan_mode or "default",
            "maxRepos": max_repos,
            "forceFullScan": force_full_scan,
        }
    ).encode("utf-8")
    url = f"{base}/v1/integrations/github/scan-plan"
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {pat}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TimeoutError) as exc:
        print(
            f"APIsec scan-plan unavailable ({exc}); using push-timestamp cache.",
            file=sys.stderr,
        )
        return None

    repos = payload.get("repositories") or []
    candidates: list[dict[str, Any]] = []
    for row in repos:
        full_name = (row.get("fullName") or "").strip()
        if not full_name:
            continue
        github_id = row.get("githubRepoId")
        if github_id is None:
            continue
        candidates.append(
            {
                "repo_id": str(github_id),
                "repo_full_name": full_name,
                "repo_name": full_name.split("/")[-1],
                "pushed_at": row.get("pushedAt") or "",
            }
        )
    print(
        f"APIsec scan-plan: {len(candidates)} repo(s) "
        f"(mode={payload.get('scanMode', scan_mode)}, source={payload.get('source', 'apisec')}).",
        file=__import__("sys").stderr,
    )
    return candidates


def _git_head_sha(repo_path: str) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", repo_path, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def report_scan_failed(
    env: Mapping[str, str],
    *,
    repo_id: str,
    full_name: str,
    repo_path: str,
    exit_code: int,
    message: str,
) -> None:
    """Best-effort inventory update when Surface did not report (orchestrator path)."""
    base = _integrations_base(env)
    pat = _auth_pat(env)
    if not base or not pat:
        return
    failure_type = "TEMPORARY" if exit_code == UPLOAD_EXIT_CODE else "PERMANENT"
    body = {
        "canonicalRepoId": f"github:{repo_id}",
        "fullName": full_name,
        "status": "FAILED",
        "commitSha": _git_head_sha(repo_path) or "unknown",
        "clientSource": "orchestrator",
        "message": message[:500],
        "exitCode": exit_code,
        "failureType": failure_type,
        "runId": (env.get("GITHUB_RUN_ID") or "").strip() or None,
    }
    body = {k: v for k, v in body.items() if v is not None}
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        f"{base}/v1/integrations/github/scan-result",
        data=data,
        headers={
            "Authorization": f"Bearer {pat}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60):
            pass
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        pass
