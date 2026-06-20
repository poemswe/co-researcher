# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pytest",
#   "scienceskillscommon",
# ]
# [tool.uv.sources]
# scienceskillscommon = { path = "../skills/scienceskillscommon" }
# ///

import gzip
import io
import json
import sys
import urllib.error

import pytest

from science_skills.scienceskillscommon import http_client


class _Headers(dict):
  def get_content_charset(self):
    return None


class _Resp:
  def __init__(self, data, status=200, headers=None, url="https://api.test/x"):
    self._buf = io.BytesIO(data)
    self.status = status
    self.url = url
    self.headers = _Headers(headers or {})

  def read(self, size=-1):
    return self._buf.read(size)

  def close(self):
    pass


def _client(**kw):
  return http_client.HttpClient("https://api.test/", qps=1000.0, **kw)


def _patch_urlopen(monkeypatch, responses):
  calls = {"n": 0}

  def fake(req, timeout=None):
    r = responses[calls["n"]]
    calls["n"] += 1
    if isinstance(r, Exception):
      raise r
    return r

  monkeypatch.setattr(http_client.urllib.request, "urlopen", fake)
  monkeypatch.setattr(http_client.time, "sleep", lambda *a: None)
  return calls


def test_constructor_requires_absolute_base():
  with pytest.raises(ValueError):
    http_client.HttpClient("not-a-url", qps=1.0)


def test_resolve_url_relative_joins_base():
  c = _client()
  assert c._resolve_url("search?q=x") == "https://api.test/search?q=x"


def test_resolve_url_absolute_must_match_base():
  c = _client()
  assert c._resolve_url("https://api.test/works/https://doi.org/10.1/x") == (
      "https://api.test/works/https://doi.org/10.1/x")
  with pytest.raises(ValueError):
    c._resolve_url("https://evil.test/x")


def test_fetch_json_success(monkeypatch):
  _patch_urlopen(monkeypatch, [_Resp(json.dumps({"ok": 1}).encode())])
  assert _client().fetch_json("x") == {"ok": 1}


def test_fetch_bytes_and_text(monkeypatch):
  _patch_urlopen(monkeypatch, [_Resp(b"hello")])
  assert _client().fetch_bytes("x") == b"hello"
  _patch_urlopen(monkeypatch, [_Resp(b"hello")])
  assert _client().fetch_text("x") == "hello"


def test_gzip_response_decoded(monkeypatch):
  payload = gzip.compress(b'{"g": 2}')
  _patch_urlopen(monkeypatch,
                 [_Resp(payload, headers={"Content-Encoding": "gzip"})])
  assert _client().fetch_json("x") == {"g": 2}


def _http_error(code, body=b"err"):
  return urllib.error.HTTPError("https://api.test/x", code, "msg",
                                {}, io.BytesIO(body))


def test_retries_on_503_then_succeeds(monkeypatch):
  calls = _patch_urlopen(monkeypatch, [
      _http_error(503),
      _Resp(json.dumps({"ok": 1}).encode()),
  ])
  assert _client().fetch_json("x") == {"ok": 1}
  assert calls["n"] == 2


def test_404_raises_httperror_with_status(monkeypatch):
  _patch_urlopen(monkeypatch, [_http_error(404)])
  with pytest.raises(http_client.HttpError) as exc:
    _client().fetch("x")
  assert exc.value.status_code == 404


def test_non_retryable_not_retried(monkeypatch):
  calls = _patch_urlopen(monkeypatch, [_http_error(400)])
  with pytest.raises(http_client.HttpError):
    _client().fetch("x")
  assert calls["n"] == 1


if __name__ == "__main__":
  sys.exit(pytest.main([__file__, "-v"]))
