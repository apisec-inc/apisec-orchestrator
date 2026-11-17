"""External Integrations helpers."""

import json
import urllib.error

import pytest

from apisec_orgscan import integrations
from apisec_orgscan.integrations import _integrations_base

ENV = {
    "APISEC_INTEGRATIONS_URL": "http://eis",
    "APISEC_PAT": "pat",
    "APISEC_CONNECTION_ID": "conn-1",
    "GITHUB_RUN_ID": "42",
}


class _Resp:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def _report(env, exit_code):
    integrations.report_scan_failed(
        env, repo_id="7", full_name="o/r", repo_path=".", exit_code=exit_code, message="x" * 600
    )


def test_integrations_base_explicit() -> None:
    assert _integrations_base({"APISEC_INTEGRATIONS_URL": "http://localhost:8080"}) == "http://localhost:8080"


def test_integrations_base_from_applications_endpoint() -> None:
    env = {"APISEC_ENDPOINT": "https://api.example.com/v1/applications"}
    assert _integrations_base(env) == "https://api.example.com"


@pytest.mark.parametrize("code", sorted(integrations.CLI_REPORTED_EXIT_CODES))
def test_report_scan_failed_skips_codes_the_cli_reports(monkeypatch, code) -> None:
    monkeypatch.setattr(integrations.urllib.request, "urlopen", lambda *_, **__: pytest.fail("posted"))
    _report(ENV, code)


def test_report_scan_failed_skips_without_connection_id(monkeypatch) -> None:
    monkeypatch.setattr(integrations.urllib.request, "urlopen", lambda *_, **__: pytest.fail("posted"))
    _report({k: v for k, v in ENV.items() if k != "APISEC_CONNECTION_ID"}, 4)


@pytest.mark.parametrize("code", [4, 5, 137])
def test_report_scan_failed_posts_for_failures_the_cli_cannot_report(monkeypatch, code) -> None:
    sent = []
    monkeypatch.setattr(integrations, "_git_head_sha", lambda _path: "abc")
    monkeypatch.setattr(integrations.urllib.request, "urlopen", lambda req, **_: sent.append(req) or _Resp())
    _report(ENV, code)
    (req,) = sent
    body = json.loads(req.data)
    assert req.full_url == "http://eis/v1/integrations/github/scan-result"
    assert req.get_header("Authorization") == "Bearer pat"
    assert body == {
        "canonicalRepoId": "github:7",
        "fullName": "o/r",
        "status": "FAILED",
        "commitSha": "abc",
        "clientSource": "orchestrator",
        "message": "x" * 500,
        "exitCode": code,
        "runId": "42",
    }


def test_report_scan_failed_never_raises(monkeypatch) -> None:
    def _fail(*_, **__):
        raise urllib.error.URLError("down")

    monkeypatch.setattr(integrations.urllib.request, "urlopen", _fail)
    _report(ENV, 4)
