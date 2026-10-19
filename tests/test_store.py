import io
import json
import urllib.error
import zipfile
from pathlib import Path

from conftest import FakeResp

from apisec_orgscan import store


def _zip(name, content):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(name, content)
    return buf.getvalue()


def test_load_missing_and_corrupt_store_is_empty(tmp_path):
    assert store.load(tmp_path / "none.json") == {}
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert store.load(bad) == {}


def test_record_then_merge_updates_store():
    store.record("42", "2026-10-01T00:00:00Z")
    current = {"7": {"pushed_at": "old", "scanned_at": ""}}
    assert store.merge(current) == 1
    assert current["42"]["pushed_at"] == "2026-10-01T00:00:00Z"
    assert current["42"]["scanned_at"]
    assert current["7"]["pushed_at"] == "old"


def test_merge_skips_malformed_updates_and_missing_dir():
    assert store.merge({}) == 0
    Path("ts-updates").mkdir()
    Path("ts-updates/bad.json").write_text('{"pushed_at": "x"}')
    assert store.merge({}) == 0


def test_save_round_trips():
    store.save({"1": {"pushed_at": "p", "scanned_at": "s"}})
    assert store.load() == {"1": {"pushed_at": "p", "scanned_at": "s"}}


def test_restore_uses_newest_unexpired_artifact(monkeypatch):
    listing = {
        "artifacts": [
            {"expired": True, "archive_download_url": "https://api.github.com/old"},
            {
                "expired": False,
                "archive_download_url": "https://api.github.com/new",
                "workflow_run": {"id": 9},
            },
        ]
    }
    requested = []

    def _urlopen(req):
        requested.append(req.full_url)
        if "artifacts?" in req.full_url:
            return FakeResp(json.dumps(listing).encode())
        return FakeResp(_zip("push-ts-store.json", '{"1": {"pushed_at": "p"}}'))

    monkeypatch.setattr(store.urllib.request, "urlopen", _urlopen)
    assert store.restore("org/scan", "tok") is True
    assert requested[1] == "https://api.github.com/new"
    assert store.load() == {"1": {"pushed_at": "p"}}


def test_restore_without_artifact_returns_false(monkeypatch):
    monkeypatch.setattr(store.urllib.request, "urlopen", lambda _req: FakeResp(b'{"artifacts": []}'))
    assert store.restore("org/scan", "tok") is False
    assert store.load() == {}


def test_restore_network_error_warns_and_continues(monkeypatch, capsys):
    def _fail(_req):
        raise urllib.error.URLError("down")

    monkeypatch.setattr(store.urllib.request, "urlopen", _fail)
    assert store.restore("org/scan", "tok") is False
    assert "::warning" in capsys.readouterr().err
