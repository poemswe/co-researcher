# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pytest",
# ]
# ///

import importlib.util
import json
import pathlib
import sys

import pytest

_SCRIPTS = (pathlib.Path(__file__).resolve().parent.parent
            / "skills/literature-review/scripts")
sys.path.insert(0, str(_SCRIPTS))
_SCRIPT = _SCRIPTS / "verify_citations.py"
_spec = importlib.util.spec_from_file_location("verify_citations", _SCRIPT)
vc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vc)


def _openalex_work(title, doi="10.1/x"):
  return {"id": "https://openalex.org/W1", "title": title,
          "doi": f"https://doi.org/{doi}"}


def test_parse_input_json_dicts(tmp_path):
  f = tmp_path / "refs.json"
  f.write_text(json.dumps([
      {"doi": "10.1038/s41586-021-03819-2"},
      {"title": "Attention Is All You Need"},
      {"doi": "10.1/x", "title": "Some Paper"},
  ]))
  entries = vc.parse_input(str(f))
  assert entries[0]["doi"] == "10.1038/s41586-021-03819-2"
  assert entries[1]["title"] == "Attention Is All You Need"
  assert entries[2]["doi"] == "10.1/x" and entries[2]["title"] == "Some Paper"


def test_parse_input_json_strings(tmp_path):
  f = tmp_path / "refs.json"
  f.write_text(json.dumps(["10.1038/nature14539", "Deep learning"]))
  entries = vc.parse_input(str(f))
  assert entries[0]["doi"] == "10.1038/nature14539"
  assert entries[1]["doi"] is None
  assert entries[1]["title"] == "Deep learning"


def test_parse_input_text_lines(tmp_path):
  f = tmp_path / "refs.md"
  f.write_text(
      "- Vaswani et al. Attention Is All You Need. "
      "https://doi.org/10.48550/arXiv.1706.03762\n"
      "\n"
      "- Jumper, J. Highly accurate protein structure prediction. "
      "doi:10.1038/s41586-021-03819-2.\n"
      "- Smith 2020, A paper with no DOI at all\n")
  entries = vc.parse_input(str(f))
  assert len(entries) == 3
  assert entries[0]["doi"] == "10.48550/arXiv.1706.03762"
  assert entries[1]["doi"] == "10.1038/s41586-021-03819-2"
  assert entries[2]["doi"] is None
  assert "no DOI at all" in entries[2]["title"]


def test_titles_match_tolerates_case_and_punctuation():
  assert vc.titles_match("Attention Is All You Need!",
                         "attention is all you need")
  assert not vc.titles_match("Attention Is All You Need",
                             "A Completely Different Subject Entirely")


def test_doi_verified_via_openalex(monkeypatch):
  monkeypatch.setattr(vc._OPENALEX, "fetch_json",
                      lambda url: _openalex_work("Real Title"))
  result = vc.verify_one({"doi": "10.1/x", "title": None, "raw": "10.1/x"})
  assert result["status"] == "verified"
  assert result["source"] == "openalex"
  assert result["matched_title"] == "Real Title"


def test_doi_mismatched_title(monkeypatch):
  monkeypatch.setattr(vc._OPENALEX, "fetch_json",
                      lambda url: _openalex_work("The Actual Published Title"))
  result = vc.verify_one({"doi": "10.1/x",
                          "title": "A Fabricated Title The Model Invented",
                          "raw": "x"})
  assert result["status"] == "mismatched"
  assert result["matched_title"] == "The Actual Published Title"


def test_doi_falls_back_to_epmc(monkeypatch):
  def raise_404(url):
    raise vc.http_client.HttpError("nope", status_code=404)
  monkeypatch.setattr(vc._OPENALEX, "fetch_json", raise_404)
  monkeypatch.setattr(vc._EPMC, "fetch_json", lambda url: {
      "resultList": {"result": [{"title": "EPMC Title",
                                 "doi": "10.1/x", "id": "12345"}]}})
  result = vc.verify_one({"doi": "10.1/x", "title": None, "raw": "10.1/x"})
  assert result["status"] == "verified"
  assert result["source"] == "epmc"


def test_doi_not_found_anywhere(monkeypatch):
  def raise_404(url):
    raise vc.http_client.HttpError("nope", status_code=404)
  monkeypatch.setattr(vc._OPENALEX, "fetch_json", raise_404)
  monkeypatch.setattr(vc._EPMC, "fetch_json",
                      lambda url: {"resultList": {"result": []}})
  result = vc.verify_one({"doi": "10.9999/ghost", "title": None, "raw": "g"})
  assert result["status"] == "not_found"


def test_title_verified_via_openalex_search(monkeypatch):
  monkeypatch.setattr(vc._OPENALEX, "fetch_json", lambda url: {
      "results": [_openalex_work("Attention Is All You Need",
                                 doi="10.48550/arxiv.1706.03762")]})
  result = vc.verify_one({"doi": None, "title": "Attention is all you need",
                          "raw": "t"})
  assert result["status"] == "verified"
  assert result["doi"] == "10.48550/arxiv.1706.03762"


def test_title_top_hit_dissimilar_is_not_found(monkeypatch):
  monkeypatch.setattr(vc._OPENALEX, "fetch_json", lambda url: {
      "results": [_openalex_work("Unrelated Paper About Fish")]})
  result = vc.verify_one({"doi": None,
                          "title": "Quantum Gravity In Two Dimensions",
                          "raw": "t"})
  assert result["status"] == "not_found"


def test_main_output_and_exit_code(monkeypatch, tmp_path, capsys):
  f = tmp_path / "refs.json"
  f.write_text(json.dumps([{"doi": "10.1/x"}]))
  monkeypatch.setattr(vc._OPENALEX, "fetch_json",
                      lambda url: _openalex_work("Real Title"))
  code = vc.main(["--input", str(f)])
  out = json.loads(capsys.readouterr().out)
  assert code == 0
  assert out["verified"] == 1 and out["total"] == 1
  assert out["results"][0]["status"] == "verified"


def test_main_nonzero_exit_on_failures(monkeypatch, tmp_path, capsys):
  f = tmp_path / "refs.json"
  f.write_text(json.dumps([{"doi": "10.9999/ghost"}]))
  def raise_404(url):
    raise vc.http_client.HttpError("nope", status_code=404)
  monkeypatch.setattr(vc._OPENALEX, "fetch_json", raise_404)
  monkeypatch.setattr(vc._EPMC, "fetch_json",
                      lambda url: {"resultList": {"result": []}})
  code = vc.main(["--input", str(f)])
  out = json.loads(capsys.readouterr().out)
  assert code == 1
  assert out["not_found"] == 1


if __name__ == "__main__":
  sys.exit(pytest.main([__file__, "-v"]))
