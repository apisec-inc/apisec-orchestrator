import argparse
import json
import urllib.request
from pathlib import Path

import pytest

from apisec_orgscan import cli, repos, settings, store

ORG_REPOS = [
    {"id": 1, "full_name": "acme/api", "name": "api", "pushed_at": "2026-10-02T00:00:00Z", "size": 5},
    {"id": 2, "full_name": "acme/web", "name": "web", "pushed_at": "2026-10-01T00:00:00Z", "size": 5},
    {"id": 3, "full_name": "acme/apisec-scan", "name": "apisec-scan", "pushed_at": "x", "size": 5},
]


def _outputs(path: Path) -> dict:
    return dict(line.split("=", 1) for line in path.read_text().splitlines())


@pytest.fixture
def plan_env(tmp_path, monkeypatch):
    out = tmp_path / "out.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    monkeypatch.setattr(store, "restore", lambda *_: False)
    monkeypatch.setattr(repos, "list_org_repos", lambda org, token: ORG_REPOS)
    monkeypatch.setattr(repos, "find_empty", lambda *_: frozenset())
    monkeypatch.setattr(settings, "newest_cli_version", lambda: "1.2.0")
    env = {
        "TARGET_ORG": "acme",
        "ORG_READ_TOKEN": "pat",
        "GITHUB_REPOSITORY": "acme/apisec-scan",
        "APISEC_REGISTRATION_CODE": "123-456",
    }
    return env, out


def test_plan_writes_matrix_and_settings_skipping_host_repo(plan_env):
    env, out = plan_env
    assert cli.cmd_plan(None, env) == 0
    outputs = _outputs(out)
    matrix = json.loads(outputs["matrix"])
    assert outputs["count"] == "2"
    assert [r["repo_full_name"] for r in matrix["include"]] == ["acme/api", "acme/web"]
    assert outputs["throughput"] == "2"
    assert outputs["run_profile"] == "surface"


def test_plan_skips_repos_unchanged_since_store(plan_env):
    env, out = plan_env
    store.save({"1": {"pushed_at": "2026-10-02T00:00:00Z"}})
    cli.cmd_plan(None, {**env, "EXCLUDE_REPOS": "acme/web"})
    assert _outputs(out)["count"] == "0"


def test_plan_respects_max_repos_and_force(plan_env):
    env, out = plan_env
    store.save({"1": {"pushed_at": "2026-10-02T00:00:00Z"}})
    cli.cmd_plan(None, {**env, "FORCE_FULL_SCAN": "true", "MAX_REPOS": "1"})
    assert json.loads(_outputs(out)["matrix"])["include"][0]["repo_full_name"] == "acme/api"


def test_plan_without_org_token_warns_and_uses_github_token(plan_env, monkeypatch, capsys):
    env, _ = plan_env
    seen = {}
    monkeypatch.setattr(repos, "list_org_repos", lambda org, token: seen.setdefault("token", token) and [])
    env = {k: v for k, v in env.items() if k != "ORG_READ_TOKEN"} | {"GITHUB_TOKEN": "gh"}
    assert cli.cmd_plan(None, env) == 0
    assert seen["token"] == "gh"
    assert "ORG_READ_TOKEN is set" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({"APP_TOKEN": "ghs", "ORG_READ_TOKEN": "pat", "GITHUB_TOKEN": "gh"}, ("app", "ghs")),
        ({"APP_TOKEN": "", "ORG_READ_TOKEN": "pat", "GITHUB_TOKEN": "gh"}, ("pat", "pat")),
        ({"APP_TOKEN": "", "ORG_READ_TOKEN": "", "GITHUB_TOKEN": "gh"}, ("job", "gh")),
    ],
)
def test_credential_order_app_then_pat_then_job_token(env, expected):
    assert cli.github_credential(env) == expected


def test_plan_with_app_token_lists_installation_repos(plan_env, monkeypatch, capsys):
    env, out = plan_env
    seen = {}

    def _installation(token):
        seen["token"] = token
        return ORG_REPOS[:1]

    monkeypatch.setattr(repos, "list_installation_repos", _installation)
    monkeypatch.setattr(repos, "list_org_repos", lambda *_: pytest.fail("listed the whole org"))
    assert cli.cmd_plan(None, {**env, "APP_TOKEN": "ghs"}) == 0
    assert seen["token"] == "ghs"
    assert [r["repo_full_name"] for r in json.loads(_outputs(out)["matrix"])["include"]] == ["acme/api"]
    assert "::warning" not in capsys.readouterr().err


def test_plan_fails_when_installation_has_no_repos(plan_env, monkeypatch, capsys):
    env, _ = plan_env
    monkeypatch.setattr(repos, "list_installation_repos", lambda _t: [])
    assert cli.cmd_plan(None, {**env, "APP_TOKEN": "ghs"}) == 1
    assert "no repositories selected" in capsys.readouterr().err


def test_plan_warns_when_the_app_key_does_not_reach_the_workflow(plan_env, capsys):
    env, _ = plan_env
    assert cli.cmd_plan(None, {**env, "ORCHESTRATOR_APP_ID": "123"}) == 0
    assert "ORCHESTRATOR_APP_PRIVATE_KEY didn't reach this workflow" in capsys.readouterr().err


def test_plan_with_the_app_does_not_warn_about_its_key(plan_env, monkeypatch, capsys):
    env, _ = plan_env
    monkeypatch.setattr(repos, "list_installation_repos", lambda _t: ORG_REPOS[:1])
    assert cli.cmd_plan(None, {**env, "ORCHESTRATOR_APP_ID": "123", "APP_TOKEN": "ghs"}) == 0
    assert "::warning" not in capsys.readouterr().err


def test_plan_requires_target_org(plan_env):
    env, _ = plan_env
    assert cli.cmd_plan(None, {**env, "TARGET_ORG": " "}) == 1


@pytest.fixture
def ran(monkeypatch):
    calls = []

    def _call(cmd, env):
        calls.append((cmd, env))
        return 0

    monkeypatch.setattr(cli.subprocess, "call", _call)
    return calls


def _scan(env, full_name="acme/api"):
    return cli.cmd_scan(argparse.Namespace(path="repos/api", repo_id="42", repo_full_name=full_name), env)


def test_scan_runs_surface_with_settings(ran):
    env = {"APISEC_ENDPOINT": "https://api.example", "APISEC_PAT": "t", "RUN_PROFILE": "legacy"}
    assert _scan(env, "acme/api") == 0
    cmd, child = ran[0]
    assert cmd == [
        "apisec-surface",
        "analyze",
        "repos/api",
        "--no-detect-monorepo",
        "--skip-if-no-routes",
        "--api-url",
        "https://api.example",
    ]
    assert child["APISEC_RUN_PROFILE"] == "legacy"
    assert child["APISEC_REGISTRATION_CODE"] == "ci-orchestrator"
    assert "APISEC_SURFACE_LLM_EXTRACTION" not in child


def test_scan_gives_surface_the_scanned_repo_not_the_host_repo(ran):
    # Surface identifies the repo as github:<owner>/<repo> from GITHUB_REPOSITORY;
    # an explicit repo id would override it.
    env = {
        "APISEC_ENDPOINT": "https://a",
        "APISEC_PAT": "t",
        "GITHUB_REPOSITORY": "acme/apisec-scan",
        "APISEC_CANONICAL_REPO_ID": "github:7",
    }
    assert _scan(env, "acme/Payments-API") == 0
    child = ran[0][1]
    assert child["GITHUB_REPOSITORY"] == "acme/Payments-API"
    # Replaces any id in the job env; CLI 1.1 would otherwise force a new app.
    assert child["APISEC_CANONICAL_REPO_ID"] == "github:acme/payments-api"


@pytest.mark.parametrize(
    ("server", "expected"),
    [
        ("", "github:acme/payments-api"),
        ("https://github.com/", "github:acme/payments-api"),
        ("https://GHE.example.com", "github:ghe.example.com/acme/payments-api"),
    ],
)
def test_repo_id_matches_surface_cli(server, expected):
    assert cli.repo_id("Acme/Payments-API", server) == expected


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/acme/payments",
        "https://ghe.example.com/acme/payments.git",
        "git@github.com:acme/payments",
    ],
)
def test_scan_without_repo_name_reads_it_from_the_checkout(ran, tmp_path, url):
    # Workflows from before 1.1 do not pass --repo-full-name.
    cli.subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    cli.subprocess.run(["git", "-C", str(tmp_path), "remote", "add", "origin", url], check=True)
    args = argparse.Namespace(path=str(tmp_path), repo_id="42", repo_full_name="")
    assert cli.cmd_scan(args, {"APISEC_ENDPOINT": "https://a", "APISEC_PAT": "t"}) == 0
    assert ran[0][1]["GITHUB_REPOSITORY"] == "acme/payments"
    assert ran[0][1]["APISEC_CANONICAL_REPO_ID"].endswith("acme/payments")


def test_scan_refuses_a_repo_it_cannot_name(ran, tmp_path, capsys):
    args = argparse.Namespace(path=str(tmp_path), repo_id="42", repo_full_name="")
    assert cli.cmd_scan(args, {"APISEC_ENDPOINT": "https://a", "APISEC_PAT": "t"}) == 1
    assert ran == []
    assert "could not tell which repository" in capsys.readouterr().err


def test_scan_ignores_a_committed_surface_state_file(ran, tmp_path):
    state = tmp_path / "apisec-code-bolt" / "state.yaml"
    state.parent.mkdir()
    state.write_text("applicationId: someone-elses-app\n")
    args = argparse.Namespace(path=str(tmp_path), repo_id="42", repo_full_name="acme/api")
    assert cli.cmd_scan(args, {"APISEC_ENDPOINT": "https://a", "APISEC_PAT": "t"}) == 0
    assert ran and not state.exists()


def test_scan_makes_no_apisec_calls_of_its_own(ran, monkeypatch):
    # Only the Surface CLI talks to APIsec, so only an upload can create an application.
    monkeypatch.setattr(urllib.request, "urlopen", lambda *_, **__: pytest.fail("called APIsec"))
    assert _scan({"APISEC_ENDPOINT": "https://a", "APISEC_PAT": "t"}, "acme/api") == 0


def test_scan_passes_registration_code_when_set(ran):
    _scan({"APISEC_ENDPOINT": "https://a", "APISEC_PAT": "t", "APISEC_REGISTRATION_CODE": " acme-reg "})
    assert ran[0][1]["APISEC_REGISTRATION_CODE"] == "acme-reg"


def test_scan_dry_run_needs_no_token_and_passes_flag(ran):
    assert _scan({"APISEC_ENDPOINT": "https://api.example", "DRY_RUN": "true"}) == 0
    assert ran[0][0][-1] == "--dry-run"


def test_scan_passes_enrichment_only_when_set(ran):
    _scan({"APISEC_ENDPOINT": "https://a", "APISEC_PAT": "t", "APISEC_LLM_ENRICHMENT": "0"})
    assert ran[0][1]["APISEC_SURFACE_LLM_EXTRACTION"] == "0"


def test_scan_refuses_without_endpoint_or_token(ran, capsys):
    assert _scan({"APISEC_PAT": "t"}) == 1
    assert _scan({"APISEC_ENDPOINT": "https://a"}) == 1
    assert ran == []
    assert "APISEC_ENDPOINT" in capsys.readouterr().err


def test_scan_failure_is_reported_and_returned(monkeypatch, capsys):
    monkeypatch.setattr(cli.subprocess, "call", lambda cmd, env: 3)
    assert _scan({"APISEC_ENDPOINT": "https://a", "APISEC_PAT": "t"}) == 3
    assert "::error" in capsys.readouterr().err


def test_record_and_merge_commands(monkeypatch):
    monkeypatch.setattr(store, "restore", lambda *_: False)
    assert cli.main(["record", "--repo-id", "5", "--pushed-at", "2026-10-03T00:00:00Z"]) == 0
    assert cli.main(["merge"]) == 0
    assert store.load()["5"]["pushed_at"] == "2026-10-03T00:00:00Z"
