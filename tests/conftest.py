import email.message
import io
import urllib.error

import pytest


def http_error(code, headers=None, body=b""):
    hdrs = email.message.Message()
    for k, v in (headers or {}).items():
        hdrs[k] = v
    return urllib.error.HTTPError("https://api.github.com/x", code, "err", hdrs, io.BytesIO(body))


class FakeResp:
    def __init__(self, body, link=""):
        self._body = body
        self.headers = {"Link": link}

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


@pytest.fixture(autouse=True)
def _in_tmp(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
