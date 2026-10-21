"""Resolve run settings: workflow input, then org variable, then default."""

from __future__ import annotations

from collections.abc import Mapping

CLI_VERSION = "1.1.0"
DEFAULT_THROUGHPUT = 2
MAX_THROUGHPUT = 10
RUN_PROFILES = ("surface", "legacy")


def _int(raw: str | None) -> int:
    try:
        return int(float(raw or 0))
    except ValueError:
        return 0


def throughput(env: Mapping[str, str]) -> int:
    t = _int(env.get("IN_THROUGHPUT")) or _int(env.get("THROUGHPUT")) or DEFAULT_THROUGHPUT
    return max(1, min(t, MAX_THROUGHPUT))


def run_profile(env: Mapping[str, str]) -> tuple[str, str | None]:
    """Return (profile, warning)."""
    raw = (env.get("IN_RUN_PROFILE") or env.get("APISEC_RUN_PROFILE") or "surface").strip().lower()
    if raw in RUN_PROFILES:
        return raw, None
    return "surface", f"'{raw}' is not surface or legacy; using surface."


def max_repos(env: Mapping[str, str]) -> int:
    return max(0, _int(env.get("MAX_REPOS")))


def truthy(raw: str | None) -> bool:
    return (raw or "").strip().lower() == "true"


def resolve(env: Mapping[str, str]) -> tuple[dict[str, str], list[str]]:
    """Settings the scan jobs need, plus warnings for the run log."""
    profile, warning = run_profile(env)
    settings = {
        "run_profile": profile,
        "cli_version": (env.get("APISEC_CLI_VERSION") or CLI_VERSION).strip(),
        "throughput": str(throughput(env)),
    }
    return settings, [warning] if warning else []
