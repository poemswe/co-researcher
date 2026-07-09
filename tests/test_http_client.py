# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pytest",
# ]
# ///

import email.utils
import gzip
import io
import json
import pathlib
import sys
import time
import urllib.error

import pytest

sys.path.insert(0, str(
    pathlib.Path(__file__).resolve().parent.parent
    / "skills/literature-review/scripts"))
import http_client


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


def test_resolve_url_rejects_host_prefix_attack():
  c = http_client.HttpClient("https://api.test", qps=1000.0)
  with pytest.raises(ValueError):
    c._resolve_url("https://api.test.evil.com/x")


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


def test_retry_after_none_when_absent():
  assert http_client._retry_after_secs({}) is None


def test_retry_after_parses_numeric():
  assert http_client._retry_after_secs({"Retry-After": "12"}) == 12.0


def test_retry_after_parses_http_date():
  future = email.utils.formatdate(time.time() + 30, usegmt=True)
  secs = http_client._retry_after_secs({"Retry-After": future})
  assert 20 <= secs <= 30


def test_retry_after_past_date_clamps_to_zero():
  past = email.utils.formatdate(time.time() - 100, usegmt=True)
  assert http_client._retry_after_secs({"Retry-After": past}) == 0.0


def test_backoff_caps_at_max_plus_jitter(monkeypatch):
  monkeypatch.setattr(http_client.random, "uniform", lambda a, b: b)
  delay = _client()._backoff_secs(attempt=20, retry_after=None)
  assert delay == (http_client.DEFAULT_BACKOFF_MAX_SECS
                   + http_client.DEFAULT_JITTER_SECS)


def test_backoff_honors_retry_after_floor(monkeypatch):
  monkeypatch.setattr(http_client.random, "uniform", lambda a, b: 0.0)
  delay = _client()._backoff_secs(attempt=0, retry_after=50.0)
  assert delay == 50.0


if __name__ == "__main__":
  sys.exit(pytest.main([__file__, "-v"]))
