import pytest

from apisec_orgscan import settings


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({}, 2),
        ({"THROUGHPUT": "5"}, 5),
        ({"IN_THROUGHPUT": "3", "THROUGHPUT": "5"}, 3),
        ({"IN_THROUGHPUT": "0", "THROUGHPUT": "5"}, 5),
        ({"IN_THROUGHPUT": "", "THROUGHPUT": ""}, 2),
        ({"THROUGHPUT": "50"}, 10),
        ({"THROUGHPUT": "-4"}, 1),
        ({"THROUGHPUT": "lots"}, 2),
        ({"IN_THROUGHPUT": "4.0"}, 4),
    ],
)
def test_throughput_precedence_and_bounds(env, expected):
    assert settings.throughput(env) == expected


def test_run_profile_input_beats_variable():
    assert settings.run_profile({"IN_RUN_PROFILE": "legacy", "APISEC_RUN_PROFILE": "surface"}) == (
        "legacy",
        None,
    )
    assert settings.run_profile({"APISEC_RUN_PROFILE": "Legacy"}) == ("legacy", None)
    assert settings.run_profile({}) == ("surface", None)


def test_invalid_run_profile_falls_back_with_warning():
    profile, warning = settings.run_profile({"APISEC_RUN_PROFILE": "fast"})
    assert profile == "surface"
    assert "fast" in warning


def test_cli_version_pinned_unless_overridden():
    assert settings.resolve({})[0]["cli_version"] == settings.CLI_VERSION
    assert settings.resolve({"APISEC_CLI_VERSION": "1.2.3"})[0]["cli_version"] == "1.2.3"


@pytest.mark.parametrize(("raw", "expected"), [("", 0), (None, 0), ("25", 25), ("-1", 0), ("x", 0)])
def test_max_repos(raw, expected):
    assert settings.max_repos({"MAX_REPOS": raw} if raw is not None else {}) == expected


@pytest.mark.parametrize(("raw", "expected"), [("true", True), ("True", True), ("false", False), ("", False)])
def test_truthy(raw, expected):
    assert settings.truthy(raw) is expected
