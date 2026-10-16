# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pytest",
#   "pymupdf4llm",
# ]
# ///

import hashlib
import importlib.util
import json
import os
import pathlib
import sys
import urllib.parse

import pymupdf
import pytest

_SCRIPTS = (pathlib.Path(__file__).resolve().parent.parent
            / "skills/literature-review/scripts")
sys.path.insert(0, str(_SCRIPTS))
_SCRIPT = _SCRIPTS / "read_paper.py"
_spec = importlib.util.spec_from_file_location("read_paper", _SCRIPT)
read_paper = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(read_paper)


def test_sanitize_id_replaces_unsafe_chars():
  assert read_paper.sanitize_id("10.1038/s41586-021-03819-2") == (
      "10.1038_s41586-021-03819-2"
  )
  assert read_paper.sanitize_id("PMC8371605") == "PMC8371605"


def test_sanitize_id_blocks_path_traversal():
  assert read_paper.sanitize_id("..") == "_"
  assert read_paper.sanitize_id(".") == "_"
  assert read_paper.sanitize_id("../../etc") == "__.._etc"
  assert read_paper.sanitize_id(".hidden") == "_hidden"
  assert read_paper.sanitize_id("") == "_"
  for bad in ("..", ".", "../../etc", ".hidden", ""):
    assert read_paper.sanitize_id(bad) not in (".", "..", "")


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


def test_extract_pdf_runs_real_pymupdf_pipeline(tmp_path):
  pdf = tmp_path / "fixture.pdf"
  document = pymupdf.open()
  page = document.new_page()
  page.insert_text((72, 72), "A Genuine PDF Fixture", fontsize=16)
  page.insert_text(
      (72, 104),
      "The intervention did not reduce readmissions by 18 percent.",
      fontsize=11)
  document.save(pdf)
  document.close()

  markdown = read_paper.extract_pdf(pdf)

  assert "A Genuine PDF Fixture" in markdown
  assert "did not reduce readmissions by 18 percent" in markdown


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


def test_lookup_openalex_work_returns_none_on_404(monkeypatch):
  def boom(url):
    raise read_paper.http_client.HttpError("missing", status_code=404)

  monkeypatch.setattr(read_paper._OPENALEX, "fetch_json", boom)
  monkeypatch.delenv("OPENALEX_API_KEY", raising=False)
  assert read_paper.lookup_openalex_work("10.1/missing") is None


def test_lookup_openalex_work_degrades_on_server_error(monkeypatch, capsys):
  def boom(url):
    raise read_paper.http_client.HttpError("down", status_code=500)

  monkeypatch.setattr(read_paper._OPENALEX, "fetch_json", boom)
  monkeypatch.delenv("OPENALEX_API_KEY", raising=False)
  assert read_paper.lookup_openalex_work("10.1/down") is None
  assert "OpenAlex" in capsys.readouterr().err


def test_lookup_warns_on_retracted(monkeypatch, capsys):
  monkeypatch.setattr(read_paper._OPENALEX, "fetch_json",
                      lambda url: {"id": "W1", "is_retracted": True})
  work = read_paper.lookup_openalex_work("10.1/retracted")
  assert work["is_retracted"] is True
  assert "retracted" in capsys.readouterr().err


def test_chain_falls_through_to_arxiv_when_openalex_errors(
    tmp_path, capsys, monkeypatch):
  def boom(url):
    raise read_paper.http_client.HttpError("down", status_code=503)

  def fake_arxiv(aid, dest):
    dest.write_bytes(b"%PDF-fake")
    return True

  monkeypatch.setattr(read_paper._OPENALEX, "fetch_json", boom)
  _no_network(monkeypatch, lookup_openalex_work=read_paper.lookup_openalex_work,
              fetch_arxiv_pdf=fake_arxiv)
  monkeypatch.setattr(read_paper, "extract_pdf", lambda p: "# md")
  read_paper.read_paper(doi="10.48550/arxiv.1706.03762", arxiv=None,
                        pmcid=None, workspace=tmp_path)
  out = json.loads(capsys.readouterr().out)
  assert out["source"] == "arxiv_pdf"


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


def test_pymupdf_layout_recommendation_suppressed():
  assert os.environ.get("PYMUPDF_SUGGEST_LAYOUT_ANALYZER") == "0"


def test_fetch_oa_pdf_rejects_non_http_scheme(tmp_path):
  assert not read_paper.fetch_oa_pdf("file:///etc/passwd", tmp_path / "x.pdf")
  assert not read_paper.fetch_oa_pdf("ftp://h/x.pdf", tmp_path / "x.pdf")
  assert not read_paper.fetch_oa_pdf("FILE:///etc/passwd", tmp_path / "x.pdf")
  assert not (tmp_path / "x.pdf").exists()


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


def _receipt_matches(out):
  source = pathlib.Path(out["path"])
  receipt = json.loads(
      source.with_suffix(".receipt.json").read_text(encoding="utf-8"))
  digest = hashlib.sha256(source.read_bytes()).hexdigest()
  return receipt, receipt["file"] == source.name and receipt["sha256"] == digest


def test_epmc_fetch_writes_a_receipt(tmp_path, capsys, monkeypatch):
  _no_network(monkeypatch, fetch_epmc_fulltext=lambda pmcid: "# epmc md")
  read_paper.read_paper(doi=None, arxiv=None, pmcid="PMC7",
                        workspace=tmp_path)
  receipt, matches = _receipt_matches(json.loads(capsys.readouterr().out))

  assert matches
  assert receipt["source"] == "epmc"
  assert receipt["fetched_at"].endswith("Z")


def test_user_pdf_and_abstract_routes_write_receipts(
    tmp_path, capsys, monkeypatch):
  d = tmp_path / "papers" / "PMC8"
  d.mkdir(parents=True)
  (d / "paper.pdf").write_bytes(b"%PDF-fake")
  monkeypatch.setattr(read_paper, "extract_pdf", lambda p: "# extracted")
  read_paper.read_paper(doi=None, arxiv=None, pmcid="PMC8",
                        workspace=tmp_path)
  pdf_receipt, pdf_matches = _receipt_matches(
      json.loads(capsys.readouterr().out))
  work = {"ids": {}, "title": "T", "abstract_inverted_index": {"hi": [0]}}
  _no_network(monkeypatch, lookup_openalex_work=lambda doi: work)
  read_paper.read_paper(doi="10.1/abs", arxiv=None, pmcid=None,
                        workspace=tmp_path)
  abstract_receipt, abstract_matches = _receipt_matches(
      json.loads(capsys.readouterr().out))

  assert pdf_matches and pdf_receipt["source"] == "user_pdf"
  assert abstract_matches and abstract_receipt["file"] == "abstract.md"


def test_cached_fulltext_does_not_mint_a_receipt(tmp_path, capsys):
  d = tmp_path / "papers" / "PMC9"
  d.mkdir(parents=True)
  (d / "fulltext.md").write_text("# written by hand", encoding="utf-8")
  read_paper.read_paper(doi=None, arxiv=None, pmcid="PMC9",
                        workspace=tmp_path)

  assert not (d / "fulltext.receipt.json").exists()


def _recheck(workspace, capsys):
  capsys.readouterr()
  code = read_paper.recheck(workspace)
  lines = capsys.readouterr().out.splitlines()
  return code, [json.loads(line) for line in lines]


def _epmc_workspace(tmp_path, monkeypatch):
  _no_network(monkeypatch, fetch_epmc_fulltext=lambda pmcid: "# epmc md")
  read_paper.read_paper(doi=None, arxiv=None, pmcid="PMC7",
                        workspace=tmp_path)
  return tmp_path / "papers" / "PMC7" / "fulltext.md"


def _rewrite_receipt(text_path, **fields):
  receipt_path = text_path.with_suffix(".receipt.json")
  receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
  receipt.update(fields)
  receipt["sha256"] = hashlib.sha256(text_path.read_bytes()).hexdigest()
  receipt_path.write_text(json.dumps(receipt), encoding="utf-8")


def test_recheck_matches_an_unchanged_source(tmp_path, capsys, monkeypatch):
  _epmc_workspace(tmp_path, monkeypatch)
  code, results = _recheck(tmp_path, capsys)

  assert code == 0
  assert results == [{"file": "papers/PMC7/fulltext.md", "source": "epmc",
                      "result": "match"}]


def test_recheck_flags_text_forged_with_its_receipt(
    tmp_path, capsys, monkeypatch):
  source = _epmc_workspace(tmp_path, monkeypatch)
  source.write_text("# forged", encoding="utf-8")
  _rewrite_receipt(source)
  code, results = _recheck(tmp_path, capsys)

  assert code == 1
  assert results[0]["result"] == "mismatch"


def test_recheck_flags_a_missing_source_file(tmp_path, capsys, monkeypatch):
  _epmc_workspace(tmp_path, monkeypatch).unlink()
  code, results = _recheck(tmp_path, capsys)

  assert (code, results[0]["result"]) == (1, "mismatch")


def test_recheck_fails_when_the_route_no_longer_answers(
    tmp_path, capsys, monkeypatch):
  _epmc_workspace(tmp_path, monkeypatch)
  _no_network(monkeypatch)
  code, results = _recheck(tmp_path, capsys)

  assert (code, results[0]["result"]) == (1, "unavailable")


def test_recheck_ignores_a_route_the_receipt_claims(
    tmp_path, capsys, monkeypatch):
  source = _epmc_workspace(tmp_path, monkeypatch)
  source.write_text("# forged", encoding="utf-8")
  _rewrite_receipt(source, source="oa_pdf",
                   locator="http://forger.example/paper.pdf")
  code, results = _recheck(tmp_path, capsys)

  assert (code, results[0]["result"]) == (1, "unavailable")


def test_recheck_reports_a_receipt_whose_route_found_nothing(
    tmp_path, capsys, monkeypatch):
  source = _epmc_workspace(tmp_path, monkeypatch)
  _rewrite_receipt(source, source="none")
  _no_network(monkeypatch)
  code, results = _recheck(tmp_path, capsys)

  assert (code, results[0]["result"]) == (1, "unavailable")


def test_recheck_reports_a_failed_fetch_and_checks_the_rest(
    tmp_path, capsys, monkeypatch):
  _epmc_workspace(tmp_path, monkeypatch)
  _no_network(monkeypatch, fetch_epmc_fulltext=lambda pmcid: "# epmc md")
  read_paper.read_paper(doi=None, arxiv=None, pmcid="PMC8",
                        workspace=tmp_path)

  def fetch(pmcid):
    if pmcid == "PMC7":
      raise read_paper.http_client.HttpError("down")
    return "# epmc md"

  monkeypatch.setattr(read_paper, "fetch_epmc_fulltext", fetch)
  code, results = _recheck(tmp_path, capsys)

  assert code == 1
  assert [r["result"] for r in results] == ["unavailable", "match"]


def test_recheck_rejects_a_receipt_for_another_paper(
    tmp_path, capsys, monkeypatch):
  source = _epmc_workspace(tmp_path, monkeypatch)
  _rewrite_receipt(source, id="PMC8")
  code, results = _recheck(tmp_path, capsys)

  assert (code, results[0]["result"]) == (1, "unreadable_receipt")


def test_recheck_cannot_verify_a_user_pdf(tmp_path, capsys, monkeypatch):
  d = tmp_path / "papers" / "10.1_x"
  d.mkdir(parents=True)
  (d / "paper.pdf").write_bytes(b"%PDF-fake")
  monkeypatch.setattr(read_paper, "extract_pdf", lambda p: "# extracted")
  read_paper.read_paper(doi="10.1/x", arxiv=None, pmcid=None,
                        workspace=tmp_path)
  code, results = _recheck(tmp_path, capsys)

  assert code == 1
  assert results == [{"file": "papers/10.1_x/fulltext.md",
                      "source": "user_pdf", "result": "unverifiable"}]


def test_recheck_fails_on_an_unreadable_receipt(tmp_path, capsys):
  d = tmp_path / "papers" / "PMC7"
  d.mkdir(parents=True)
  (d / "fulltext.receipt.json").write_text("{", encoding="utf-8")
  code, results = _recheck(tmp_path, capsys)

  assert code == 1
  assert results == [{"file": "papers/PMC7/fulltext.receipt.json",
                      "source": None, "result": "unreadable_receipt"}]


def test_recheck_refetches_an_abstract_by_its_doi(
    tmp_path, capsys, monkeypatch):
  work = {"ids": {}, "title": "T", "abstract_inverted_index": {"hi": [0]}}
  _no_network(monkeypatch, lookup_openalex_work=lambda doi: work)
  read_paper.read_paper(doi="10.1/abs", arxiv=None, pmcid=None,
                        workspace=tmp_path)
  code, results = _recheck(tmp_path, capsys)

  assert (code, results[0]["result"]) == (0, "match")


def test_recheck_resolves_an_arxiv_doi_again(tmp_path, capsys, monkeypatch):
  def fake_pdf(arxiv_id, dest):
    dest.write_bytes(b"%PDF-" + arxiv_id.encode())
    return True

  _no_network(monkeypatch, fetch_arxiv_pdf=fake_pdf)
  monkeypatch.setattr(read_paper, "extract_pdf",
                      lambda p: p.read_bytes().decode())
  read_paper.read_paper(doi="10.48550/arXiv.1706.03762", arxiv=None,
                        pmcid=None, workspace=tmp_path)
  code, results = _recheck(tmp_path, capsys)

  assert (code, results[0]["source"], results[0]["result"]) == (
      0, "arxiv_pdf", "match")


@pytest.mark.parametrize("identifier, expected", [
    ("PMC123", (None, None, "PMC123")),
    ("10.1/x", ("10.1/x", None, None)),
    ("1706.03762", (None, "1706.03762", None)),
])
def test_identifier_args_routes_by_shape(identifier, expected):
  assert read_paper.identifier_args(identifier) == expected
