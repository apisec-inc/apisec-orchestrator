"""External Integrations helpers."""

from apisec_orgscan.integrations import _integrations_base


def test_integrations_base_explicit() -> None:
    assert _integrations_base({"APISEC_INTEGRATIONS_URL": "http://localhost:8080"}) == "http://localhost:8080"


def test_integrations_base_from_applications_endpoint() -> None:
    env = {"APISEC_ENDPOINT": "https://api.example.com/v1/applications"}
    assert _integrations_base(env) == "https://api.example.com"
