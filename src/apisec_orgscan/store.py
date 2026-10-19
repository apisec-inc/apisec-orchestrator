"""The push-timestamp store: which commit of each repo was last scanned.

It lives as the ``push-ts-store`` artifact in the repo that runs the scan, so
the next run only scans repos pushed to since.
"""

from __future__ import annotations

import io
import json
import sys
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from . import github

ARTIFACT = "push-ts-store"
STORE_PATH = Path(".cache/push-ts-store.json")
UPDATES_DIR = Path("ts-updates")


def load(path: Path = STORE_PATH) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print("  Warning: store is corrupt; treating as empty.", file=sys.stderr)
        return {}


def save(store: dict, path: Path = STORE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store, indent=2, sort_keys=True), encoding="utf-8")


def restore(repo: str, token: str, path: Path = STORE_PATH) -> bool:
    """Download the newest unexpired store artifact. False when there is none."""
    try:
        with urllib.request.urlopen(
            github.request(f"{github.API}/repos/{repo}/actions/artifacts?name={ARTIFACT}&per_page=10", token)
        ) as resp:
            artifacts = [a for a in json.loads(resp.read()).get("artifacts", []) if not a.get("expired")]
        if not artifacts:
            print("No previous store; every repo counts as changed.", file=sys.stderr)
            return False
        with urllib.request.urlopen(github.request(artifacts[0]["archive_download_url"], token)) as resp:
            archive = zipfile.ZipFile(io.BytesIO(resp.read()))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(archive.read(path.name))
        print(f"Restored store from run {artifacts[0].get('workflow_run', {}).get('id')}", file=sys.stderr)
        return True
    except (urllib.error.URLError, KeyError, zipfile.BadZipFile) as exc:
        print(
            f"::warning title=APIsec Surface::Could not restore the scan store ({exc}); "
            f"every repo counts as changed this run.",
            file=sys.stderr,
        )
        return False


def record(repo_id: str, pushed_at: str, updates_dir: Path = UPDATES_DIR) -> Path:
    updates_dir.mkdir(parents=True, exist_ok=True)
    out = updates_dir / f"{repo_id}.json"
    scanned_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out.write_text(json.dumps({"repo_id": str(repo_id), "pushed_at": pushed_at, "scanned_at": scanned_at}))
    return out


def merge(store: dict, updates_dir: Path = UPDATES_DIR) -> int:
    """Fold per-repo update files into ``store``. Returns how many applied."""
    applied = 0
    for update_path in sorted(updates_dir.glob("*.json")) if updates_dir.is_dir() else []:
        try:
            update = json.loads(update_path.read_text(encoding="utf-8"))
            store[str(update["repo_id"])] = {
                "pushed_at": update["pushed_at"],
                "scanned_at": update.get("scanned_at", ""),
            }
            applied += 1
        except (KeyError, json.JSONDecodeError, OSError) as exc:
            print(f"  Skipping malformed update {update_path}: {exc}", file=sys.stderr)
    return applied
