# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pytest",
#   "scienceskillscommon",
# ]
# [tool.uv.sources]
# scienceskillscommon = { path = "../skills/scienceskillscommon" }
# ///

import argparse
import importlib.util
import json
import pathlib
import sys

import pytest

_SCRIPT = (
    pathlib.Path(__file__).resolve().parent.parent
    / "skills/literature-review/scripts/search_arxiv.py"
)
_spec = importlib.util.spec_from_file_location("search_arxiv", _SCRIPT)
search_arxiv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(search_arxiv)

_FEED = b"""<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2301.00001v1</id>
    <title>Paper One</title>
    <summary>Summary one.</summary>
    <published>2023-01-01T00:00:00Z</published>
    <author><name>Alice</name></author>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2301.00002v1</id>
    <title>Paper Two</title>
    <summary>Summary two.</summary>
    <published>2023-01-02T00:00:00Z</published>
    <author><name>Bob</name></author>
  </entry>
</feed>"""


def _args():
  return argparse.Namespace(query="x", id_list=None, start=0, max_results=2,
                            sort_by=None, sort_order=None)


def test_search_arxiv_emits_single_json_object(capsys, monkeypatch):
  monkeypatch.setattr(search_arxiv._CLIENT, "fetch_bytes", lambda url: _FEED)
  search_arxiv.search_arxiv(_args())
  out = capsys.readouterr().out
  data = json.loads(out)
  assert data["status"] == "success"
  assert data["results_count"] == 2
  assert [p["id"] for p in data["papers"]] == ["2301.00001v1", "2301.00002v1"]


if __name__ == "__main__":
  sys.exit(pytest.main([__file__, "-v"]))
