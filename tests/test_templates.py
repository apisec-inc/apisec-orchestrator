"""The workflow files customers run must stay consistent with the package."""

import subprocess
import sys
from pathlib import Path

import yaml

from apisec_orgscan import __version__

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github/workflows/scan.yml"
CALLER = ROOT / "templates/apisec-scan.yml"
STANDALONE = ROOT / "templates/apisec-scan-standalone.yml"


def _load(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_reusable_workflow_pins_this_package_version():
    assert _load(WORKFLOW)["env"]["ORGSCAN_SPEC"] == f"apisec-orgscan=={__version__}"


def test_standalone_is_generated_from_reusable_workflow():
    result = subprocess.run([sys.executable, str(ROOT / "scripts/sync_templates.py"), "--check"])
    assert result.returncode == 0


def test_standalone_runs_the_same_jobs():
    assert _load(STANDALONE)["jobs"] == _load(WORKFLOW)["jobs"]
    assert _load(STANDALONE)["env"]["ORGSCAN_SPEC"].startswith("apisec-orgscan~=")


def test_caller_passes_secrets_by_name():
    # `secrets: inherit` only works within one org; customers call across orgs.
    job = _load(CALLER)["jobs"]["scan"]
    assert job["uses"] == "apisec-inc/apisec-orchestrator/.github/workflows/scan.yml@v1"
    assert job["secrets"] == {
        "APISEC_TOKEN": "${{ secrets.APISEC_TOKEN }}",
        "ORG_READ_TOKEN": "${{ secrets.ORG_READ_TOKEN }}",
    }


def test_caller_inputs_exist_on_reusable_workflow():
    called = _load(WORKFLOW)[True]["workflow_call"]["inputs"]
    assert set(_load(CALLER)["jobs"]["scan"]["with"]) <= set(called)


def test_caller_converts_number_inputs():
    # Dispatch inputs arrive as strings; workflow_call number inputs reject them.
    called = _load(WORKFLOW)[True]["workflow_call"]["inputs"]
    for name, value in _load(CALLER)["jobs"]["scan"]["with"].items():
        if called[name]["type"] == "number":
            assert value.startswith("${{ fromJSON("), name


def test_callers_grant_permissions_the_store_needs():
    for path in (CALLER, STANDALONE):
        assert _load(path)["permissions"] == {"contents": "read", "actions": "read"}
