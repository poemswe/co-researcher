# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pytest",
#   "scienceskillscommon",
#   "pymupdf4llm",
# ]
# [tool.uv.sources]
# scienceskillscommon = { path = "../skills/scienceskillscommon" }
# ///

import importlib.util
import json
import pathlib
import sys
import urllib.parse

import pytest

_SCRIPT = (
    pathlib.Path(__file__).resolve().parent.parent
    / "skills/literature-review/scripts/read_paper.py"
)
_spec = importlib.util.spec_from_file_location("read_paper", _SCRIPT)
read_paper = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(read_paper)


def test_sanitize_id_replaces_unsafe_chars():
  assert read_paper.sanitize_id("10.1038/s41586-021-03819-2") == (
      "10.1038_s41586-021-03819-2"
  )
  assert read_paper.sanitize_id("PMC8371605") == "PMC8371605"


def test_doi_to_arxiv():
  assert read_paper.doi_to_arxiv("10.48550/arXiv.1706.03762") == "1706.03762"
  assert read_paper.doi_to_arxiv("10.1038/s41586-021-03819-2") is None


def test_abstract_from_inverted_index():
  inv = {"world": [1], "hello": [0], "again": [2]}
  assert read_paper.abstract_from_inverted_index(inv) == "hello world again"


def test_pmcid_from_ids():
  ids = {"pmcid": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8371605"}
  assert read_paper.pmcid_from_ids(ids) == "PMC8371605"
  assert read_paper.pmcid_from_ids({}) is None


def test_emit_prints_json_line(capsys):
  read_paper.emit("fulltext", pathlib.Path("/tmp/x.md"), "epmc", "PMC1")
  out = json.loads(capsys.readouterr().out)
  assert out == {
      "status": "fulltext", "path": "/tmp/x.md",
      "source": "epmc", "id": "PMC1",
  }


def test_cached_fulltext_is_noop(tmp_path, capsys):
  d = tmp_path / "papers" / "PMC1"
  d.mkdir(parents=True)
  (d / "fulltext.md").write_text("# cached", encoding="utf-8")
  read_paper.read_paper(doi=None, arxiv=None, pmcid="PMC1",
                        workspace=tmp_path)
  out = json.loads(capsys.readouterr().out)
  assert out["status"] == "fulltext"
  assert out["source"] == "cached"
  assert out["path"].endswith("papers/PMC1/fulltext.md")


def test_user_pdf_is_extracted(tmp_path, capsys, monkeypatch):
  d = tmp_path / "papers" / "PMC2"
  d.mkdir(parents=True)
  (d / "paper.pdf").write_bytes(b"%PDF-fake")
  monkeypatch.setattr(read_paper, "extract_pdf", lambda p: "# extracted")
  read_paper.read_paper(doi=None, arxiv=None, pmcid="PMC2",
                        workspace=tmp_path)
  out = json.loads(capsys.readouterr().out)
  assert out["status"] == "fulltext"
  assert out["source"] == "user_pdf"
  assert (d / "fulltext.md").read_text(encoding="utf-8") == "# extracted"


def test_corrupt_user_pdf_falls_through(tmp_path, capsys, monkeypatch):
  d = tmp_path / "papers" / "PMC3"
  d.mkdir(parents=True)
  (d / "paper.pdf").write_bytes(b"%PDF-corrupt")

  def boom(path):
    raise ValueError("cannot parse")

  monkeypatch.setattr(read_paper, "extract_pdf", boom)
  monkeypatch.setattr(read_paper, "fetch_epmc_fulltext", lambda p: "# epmc md")
  read_paper.read_paper(doi=None, arxiv=None, pmcid="PMC3",
                        workspace=tmp_path)
  out = json.loads(capsys.readouterr().out)
  assert out["source"] == "epmc"


def _no_network(monkeypatch, **overrides):
  defaults = {
      "lookup_openalex_work": lambda doi: None,
      "resolve_pmcid_via_epmc": lambda doi: None,
      "fetch_epmc_fulltext": lambda pmcid: None,
      "fetch_arxiv_pdf": lambda aid, dest: False,
      "fetch_oa_pdf": lambda url, dest: False,
  }
  defaults.update(overrides)
  for name, fn in defaults.items():
    monkeypatch.setattr(read_paper, name, fn)


def test_chain_doi_resolves_pmcid_via_openalex(tmp_path, capsys, monkeypatch):
  work = {"ids": {"pmcid": "https://.../PMC9"}, "title": "T"}
  _no_network(monkeypatch,
              lookup_openalex_work=lambda doi: work,
              fetch_epmc_fulltext=lambda pmcid: "# md" if pmcid == "PMC9" else None)
  read_paper.read_paper(doi="10.1/x", arxiv=None, pmcid=None,
                        workspace=tmp_path)
  out = json.loads(capsys.readouterr().out)
  assert out["source"] == "epmc"
  assert out["status"] == "fulltext"


def test_chain_arxiv_pdf_after_epmc_miss(tmp_path, capsys, monkeypatch):
  def fake_arxiv(aid, dest):
    dest.write_bytes(b"%PDF-fake")
    return True

  _no_network(monkeypatch, fetch_arxiv_pdf=fake_arxiv)
  monkeypatch.setattr(read_paper, "extract_pdf", lambda p: "# arxiv md")
  read_paper.read_paper(doi=None, arxiv="1706.03762", pmcid=None,
                        workspace=tmp_path)
  out = json.loads(capsys.readouterr().out)
  assert out["source"] == "arxiv_pdf"


def test_chain_oa_pdf_route(tmp_path, capsys, monkeypatch):
  work = {"ids": {}, "best_oa_location": {"pdf_url": "https://x.org/p.pdf"}}

  def fake_oa(url, dest):
    dest.write_bytes(b"%PDF-fake")
    return True

  _no_network(monkeypatch,
              lookup_openalex_work=lambda doi: work,
              fetch_oa_pdf=fake_oa)
  monkeypatch.setattr(read_paper, "extract_pdf", lambda p: "# oa md")
  read_paper.read_paper(doi="10.1/y", arxiv=None, pmcid=None,
                        workspace=tmp_path)
  out = json.loads(capsys.readouterr().out)
  assert out["source"] == "oa_pdf"


def test_chain_abstract_fallback(tmp_path, capsys, monkeypatch):
  work = {
      "ids": {},
      "title": "Paywalled Paper",
      "abstract_inverted_index": {"hello": [0], "world": [1]},
  }
  _no_network(monkeypatch, lookup_openalex_work=lambda doi: work)
  read_paper.read_paper(doi="10.1/z", arxiv=None, pmcid=None,
                        workspace=tmp_path)
  out = json.loads(capsys.readouterr().out)
  assert out["status"] == "abstract-only"
  assert out["source"] == "openalex_abstract"
  body = pathlib.Path(out["path"]).read_text(encoding="utf-8")
  assert "# Paywalled Paper" in body
  assert "hello world" in body


def test_chain_nothing_found(tmp_path, capsys, monkeypatch):
  _no_network(monkeypatch)
  read_paper.read_paper(doi="10.1/none", arxiv=None, pmcid=None,
                        workspace=tmp_path)
  out = json.loads(capsys.readouterr().out)
  assert out == {"status": "abstract-only", "path": None,
                 "source": "none", "id": "10.1/none"}


def test_resolve_pmcid_via_epmc_returns_first_pmcid(monkeypatch):
  seen = {}

  def fake_fetch_json(url):
    read_paper._EPMC._resolve_url(url)
    seen["url"] = url
    return {"resultList": {"result": [
        {"pmid": "34265844"},
        {"pmcid": "PMC8371605", "source": "MED"},
    ]}}

  monkeypatch.setattr(read_paper._EPMC, "fetch_json", fake_fetch_json)
  assert read_paper.resolve_pmcid_via_epmc("10.1038/s41586-021-03819-2") == (
      "PMC8371605")
  assert 'DOI:"10.1038/s41586-021-03819-2"' in urllib.parse.unquote(
      seen["url"])


def test_resolve_pmcid_via_epmc_no_match_returns_none(monkeypatch):
  monkeypatch.setattr(read_paper._EPMC, "fetch_json",
                      lambda url: {"resultList": {"result": []}})
  assert read_paper.resolve_pmcid_via_epmc("10.1/nomatch") is None


def test_resolve_pmcid_via_epmc_swallows_http_error(monkeypatch):
  def boom(url):
    raise read_paper.http_client.HttpError("fail", status_code=500)

  monkeypatch.setattr(read_paper._EPMC, "fetch_json", boom)
  assert read_paper.resolve_pmcid_via_epmc("10.1/err") is None


def test_chain_resolves_pmcid_via_epmc_when_openalex_lacks_it(
    tmp_path, capsys, monkeypatch):
  work = {"ids": {}, "title": "AlphaFold"}
  _no_network(monkeypatch,
              lookup_openalex_work=lambda doi: work,
              resolve_pmcid_via_epmc=lambda doi: "PMC8371605",
              fetch_epmc_fulltext=lambda pmcid: "# md" if pmcid == "PMC8371605"
              else None)
  read_paper.read_paper(doi="10.1038/s41586-021-03819-2", arxiv=None,
                        pmcid=None, workspace=tmp_path)
  out = json.loads(capsys.readouterr().out)
  assert out["source"] == "epmc"
  assert out["status"] == "fulltext"


def test_lookup_openalex_work_url_accepted_by_client(monkeypatch):
  seen = {}

  def fake_fetch_json(url):
    read_paper._OPENALEX._resolve_url(url)
    seen["url"] = url
    return {"ok": True}

  monkeypatch.setattr(read_paper._OPENALEX, "fetch_json", fake_fetch_json)
  monkeypatch.delenv("OPENALEX_API_KEY", raising=False)
  result = read_paper.lookup_openalex_work("10.7717/peerj.4375")
  assert result == {"ok": True}
  assert seen["url"].startswith("https://api.openalex.org/works/")


if __name__ == "__main__":
  sys.exit(pytest.main([__file__, "-v"]))
