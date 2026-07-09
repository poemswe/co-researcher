# MIT License
#
# Copyright (c) 2026 Poe Poe / co-researcher contributors
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED. See the MIT License for details.
#
# Original to this repository. Design (a rate-limited HTTP client with retry and
# backoff) was inspired by google-deepmind/science-skills; no code was copied.

"""Rate-limited HTTP client with retries and exponential backoff.

Wraps `urllib.request` with a cross-process per-host rate limiter, automatic
retries on transient errors (HTTP 429 / 5xx), exponential backoff with jitter,
`Retry-After` support, and transparent gzip decoding. GET-only.
"""

from __future__ import annotations

import contextlib
import datetime
import email.utils
import fcntl
import gzip
import json
import os
import random
import time
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
DEFAULT_TIMEOUT_SECS = 60.0
DEFAULT_MAX_RETRIES = 7
DEFAULT_BACKOFF_BASE_SECS = 3.0
DEFAULT_BACKOFF_MAX_SECS = 180.0
DEFAULT_JITTER_SECS = 0.5
_LOCK_PREFIX = "/tmp/co-researcher-httpclient"
_REFERER_TEMPLATE = (
    "https://github.com/poemswe/co-researcher/tree/main/skills/{skill}"
)
_MAX_BODY_SNIPPET = 500


class HttpError(Exception):
  """A non-retryable HTTP failure or an exhausted retry sequence.

  Attributes:
    status_code: HTTP status, or None for transport-level failures.
    body: Raw error response body, if any.
    url: The requested URL.
  """

  def __init__(self, message, *, status_code=None, body=None, url=None):
    if body:
      snippet = self._decode_snippet(body)
      if snippet:
        message = f"{message}\nServer body: {snippet}"
    super().__init__(message)
    self.status_code = status_code
    self.body = body
    self.url = url

  @staticmethod
  def _decode_snippet(body):
    if body.startswith(b"\x1f\x8b"):
      with contextlib.suppress(OSError, EOFError):
        body = gzip.decompress(body)
    text = body.decode("utf-8", errors="replace").strip()
    return text[:_MAX_BODY_SNIPPET]


class HttpResponse:
  """Decoded HTTP response: `.data`, `.text`, `.json()`, `.headers`, `.status_code`."""

  def __init__(self, data, status_code, headers, url, encoding="utf-8"):
    self.data = data
    self.status_code = status_code
    self.headers = headers
    self.url = url
    self.encoding = encoding or "utf-8"

  def json(self) -> Any:
    return json.loads(self.data.decode(self.encoding))

  @property
  def text(self) -> str:
    return self.data.decode(self.encoding)


class _RateLimiter:
  """Enforces a minimum gap between requests, shared across processes."""

  def __init__(self, hostname, qps):
    self._min_gap = 1.0 / qps
    self._lock_path = f"{_LOCK_PREFIX}-{hostname}.lock"

  def wait(self):
    with open(self._lock_path, "a+") as handle:
      fcntl.flock(handle, fcntl.LOCK_EX)
      try:
        handle.seek(0)
        raw = handle.read().strip()
        previous = float(raw) if raw else 0.0
        gap = self._min_gap - (time.monotonic() - previous)
        if gap > 0:
          time.sleep(gap)
        handle.seek(0)
        handle.truncate()
        handle.write(str(time.monotonic()))
        handle.flush()
      finally:
        fcntl.flock(handle, fcntl.LOCK_UN)


def _retry_after_secs(headers):
  value = headers.get("Retry-After")
  if value is None:
    return None
  try:
    return float(value)
  except (TypeError, ValueError):
    pass
  parsed = email.utils.parsedate_to_datetime(value)
  if parsed is None:
    return None
  delta = (parsed - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
  return max(0.0, delta)


def _decode_body(response):
  data = response.read()
  encoding = (response.headers.get("Content-Encoding") or "").lower()
  if encoding in ("gzip", "x-gzip"):
    data = gzip.decompress(data)
  return data


class HttpClient:
  """Rate-limited, retrying HTTP client scoped to one base URL."""

  def __init__(self, base_url, qps, *, referer_skill=None,
               max_retries=DEFAULT_MAX_RETRIES, timeout=DEFAULT_TIMEOUT_SECS,
               user_agent=None):
    parsed = urllib.parse.urlparse(base_url)
    if not parsed.scheme or not parsed.netloc:
      raise ValueError(f"base_url must be an absolute URL: {base_url!r}")
    self.base_url = base_url
    self.hostname = parsed.hostname
    self.max_retries = max_retries
    self.timeout = timeout
    self.user_agent = user_agent or os.environ.get(
        "CO_RESEARCHER_USER_AGENT", "")
    self.referer_skill = referer_skill
    self._limiter = _RateLimiter(self.hostname, qps)

  def _resolve_url(self, url):
    if "://" not in url:
      return urllib.parse.urljoin(self.base_url, url)
    if urllib.parse.urlparse(url).hostname != self.hostname:
      raise ValueError(
          f"URL {url!r} does not match base_url {self.base_url!r}")
    return url

  def _request_headers(self, extra):
    headers = {"User-Agent": self.user_agent, "Accept-Encoding": "gzip"}
    if self.referer_skill:
      headers["Referer"] = _REFERER_TEMPLATE.format(skill=self.referer_skill)
    if extra:
      headers.update(extra)
    return headers

  def _backoff_secs(self, attempt, retry_after):
    delay = min(DEFAULT_BACKOFF_BASE_SECS * (2 ** attempt),
                DEFAULT_BACKOFF_MAX_SECS)
    if retry_after is not None:
      delay = max(delay, retry_after)
    return delay + random.uniform(0, DEFAULT_JITTER_SECS)

  def fetch(self, url, *, headers=None, timeout=None,
            max_retries=None) -> HttpResponse:
    resolved = self._resolve_url(url)
    timeout = self.timeout if timeout is None else timeout
    retries = self.max_retries if max_retries is None else max_retries
    last_error = None

    for attempt in range(retries + 1):
      self._limiter.wait()
      request = urllib.request.Request(
          resolved, headers=self._request_headers(headers), method="GET")
      try:
        response = urllib.request.urlopen(request, timeout=timeout)
      except urllib.error.HTTPError as exc:
        body = exc.read()
        status = exc.code
        retry_after = _retry_after_secs(exc.headers)
        exc.close()
        last_error = HttpError(
            f"HTTP {status} while fetching {resolved}",
            status_code=status, body=body, url=resolved)
        if status in RETRYABLE_STATUS_CODES and attempt < retries:
          time.sleep(self._backoff_secs(attempt, retry_after))
          continue
        raise last_error from exc
      except (urllib.error.URLError, OSError) as exc:
        last_error = HttpError(
            f"Network error while fetching {resolved}: {exc}", url=resolved)
        if attempt < retries:
          time.sleep(self._backoff_secs(attempt, None))
          continue
        raise last_error from exc

      data = _decode_body(response)
      result = HttpResponse(
          data=data,
          status_code=response.status,
          headers=dict(response.headers),
          url=response.url,
          encoding=response.headers.get_content_charset() or "utf-8",
      )
      response.close()
      return result

    raise HttpError(f"Max retries exceeded for {resolved}", url=resolved)

  def fetch_json(self, url, **kwargs) -> Any:
    headers = kwargs.pop("headers", None) or {}
    headers.setdefault("Accept", "application/json")
    return self.fetch(url, headers=headers, **kwargs).json()

  def fetch_bytes(self, url, **kwargs) -> bytes:
    return self.fetch(url, **kwargs).data

  def fetch_text(self, url, **kwargs) -> str:
    return self.fetch(url, **kwargs).text
