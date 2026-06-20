# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pytest",
#   "scienceskillscommon",
# ]
# [tool.uv.sources]
# scienceskillscommon = { path = "../skills/scienceskillscommon" }
# ///

import importlib.util
import pathlib
import sys

import pytest

_SCRIPT = (
    pathlib.Path(__file__).resolve().parent.parent
    / "skills/literature-review/scripts/europepmc_api.py"
)
_spec = importlib.util.spec_from_file_location("europepmc_api", _SCRIPT)
epmc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(epmc)


def test_search_enforces_open_access_and_shapes_result(monkeypatch):
  seen = {}

  def fake_json(url):
    seen["url"] = url
    return {"hitCount": 7,
            "resultList": {"result": [{"id": "A"}, {"id": "B"}, {"id": "C"}]},
            "nextCursorMark": "NEXT"}

  monkeypatch.setattr(epmc._API_CLIENT, "fetch_json", fake_json)
  out = epmc.search("CRISPR", max_results=2)
  assert "OPEN_ACCESS%3Ay" in seen["url"] or "OPEN_ACCESS:y" in seen["url"]
  assert out["hitCount"] == 7
  assert len(out["results"]) == 2
  assert out["nextCursorMark"] == "NEXT"


def test_search_keeps_explicit_open_access_clause(monkeypatch):
  seen = {}
  monkeypatch.setattr(epmc._API_CLIENT, "fetch_json",
                      lambda url: seen.update(url=url) or {"resultList": {}})
  epmc.search("cancer AND OPEN_ACCESS:n")
  assert seen["url"].count("OPEN_ACCESS") == 1


def test_get_fulltext_routes_format(monkeypatch):
  monkeypatch.setattr(epmc._API_CLIENT, "fetch_text",
                      lambda url, timeout=None: "<article><body>"
                      "<sec><title>M</title><p>hi</p></sec></body></article>")
  assert "<article>" in epmc.get_fulltext("PMC1", "xml")
  assert "## M" in epmc.get_fulltext("PMC1", "text")


def test_citations_and_references_unwrap(monkeypatch):
  monkeypatch.setattr(epmc._API_CLIENT, "fetch_json", lambda url: {
      "hitCount": 2,
      "citationList": {"citation": [{"id": 1}, {"id": 2}]},
      "referenceList": {"reference": [{"id": 9}]}})
  cites = epmc.get_citations("MED", "123")
  assert cites["hitCount"] == 2 and cites["citations"] == [{"id": 1}, {"id": 2}]
  refs = epmc.get_references("MED", "123")
  assert refs["references"] == [{"id": 9}]


if __name__ == "__main__":
  sys.exit(pytest.main([__file__, "-v"]))
