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


@pytest.fixture(autouse=True)
def _no_live_crossref(monkeypatch):
  """No test may reach Crossref unless it stubs the response itself."""
  monkeypatch.setattr(vc._CROSSREF, "fetch_json",
                      lambda url: {"message": {"total-results": 0}})


def _openalex_work(title, doi="10.1/x", retracted=False):
  return {"id": "https://openalex.org/W1", "title": title,
          "doi": f"https://doi.org/{doi}", "is_retracted": retracted}


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


def test_parse_input_bibtex(tmp_path):
  f = tmp_path / "refs.bib"
  f.write_text("""
@article{vaswani2017,
  title = {Attention Is All You Need},
  author = {Vaswani, Ashish},
  doi = {10.48550/arXiv.1706.03762},
  year = {2017}
}

@inproceedings{smith2020,
  title = "A Paper With {Nested} Braces",
  year = {2020}
}

@comment{ignore me}
""")
  entries = vc.parse_input(str(f))
  assert len(entries) == 2
  assert entries[0]["doi"] == "10.48550/arXiv.1706.03762"
  assert entries[0]["title"] == "Attention Is All You Need"
  assert entries[0]["raw"] == "vaswani2017"
  assert entries[1]["doi"] is None
  assert entries[1]["title"] == "A Paper With Nested Braces"


def test_parse_input_bibtex_one_line_entry(tmp_path):
  f = tmp_path / "refs.bib"
  f.write_text(
      "@article{k1, title={One Line Entry}, year={2020}}\n")
  entries = vc.parse_input(str(f))
  assert len(entries) == 1
  assert entries[0]["raw"] == "k1"
  assert entries[0]["title"] == "One Line Entry"


def test_parse_input_bibtex_commentary_not_skipped(tmp_path):
  f = tmp_path / "refs.bib"
  f.write_text("""
@commentary{k1,
  title = {A Commentary Entry}
}

@comment{ignore me}
""")
  entries = vc.parse_input(str(f))
  assert len(entries) == 1
  assert entries[0]["raw"] == "k1"
  assert entries[0]["title"] == "A Commentary Entry"


def test_parse_input_bibtex_stray_line_between_entries(tmp_path):
  f = tmp_path / "refs.bib"
  f.write_text("""
@article{first,
  title = {First Title},
  doi = {10.1/first}
}
stray line that is not an entry
@article{second,
  title = {Second Title},
  doi = {10.1/second}
}
""")
  entries = vc.parse_input(str(f))
  assert len(entries) == 2
  assert entries[0]["raw"] == "first" and entries[0]["doi"] == "10.1/first"
  assert entries[1]["raw"] == "second" and entries[1]["doi"] == "10.1/second"


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


def _crossref(total):
  return lambda url: {"message": {"total-results": total}}


def test_retracted_via_crossref_true_when_retraction_notice_exists(monkeypatch):
  monkeypatch.setattr(vc._CROSSREF, "fetch_json", _crossref(1))
  assert vc.retracted_via_crossref("10.1/x") is True


def test_retracted_via_crossref_false_when_no_notice(monkeypatch):
  monkeypatch.setattr(vc._CROSSREF, "fetch_json", _crossref(0))
  assert vc.retracted_via_crossref("10.1/x") is False


def test_retracted_via_crossref_none_on_http_error(monkeypatch, capsys):
  def boom(url):
    raise vc.http_client.HttpError("down", status_code=503)
  monkeypatch.setattr(vc._CROSSREF, "fetch_json", boom)
  assert vc.retracted_via_crossref("10.1/x") is None
  assert "Crossref" in capsys.readouterr().err


def test_retracted_via_crossref_none_when_doi_has_comma(monkeypatch, capsys):
  def fail(url):
    raise AssertionError("must not build a filter from a comma DOI")
  monkeypatch.setattr(vc._CROSSREF, "fetch_json", fail)
  assert vc.retracted_via_crossref("10.1234/foo,bar") is None
  assert "comma" in capsys.readouterr().err


def test_unchecked_crossref_is_visible_in_result(monkeypatch):
  monkeypatch.setattr(vc._OPENALEX, "fetch_json",
                      lambda url: _openalex_work("T", doi="10.1/a,b"))
  result = vc.verify_one({"doi": "10.1/a,b", "title": None, "raw": "x"})
  assert result["status"] == "verified"
  assert result["crossref_checked"] is False


def test_checked_crossref_is_visible_in_result(monkeypatch):
  monkeypatch.setattr(vc._OPENALEX, "fetch_json",
                      lambda url: _openalex_work("T"))
  monkeypatch.setattr(vc._CROSSREF, "fetch_json", _crossref(0))
  result = vc.verify_one({"doi": "10.1/x", "title": None, "raw": "x"})
  assert result["crossref_checked"] is True


def test_main_warns_when_some_citations_unchecked(monkeypatch, tmp_path, capsys):
  f = tmp_path / "refs.json"
  f.write_text(json.dumps([{"doi": "10.1/a,b"}]))
  monkeypatch.setattr(vc._OPENALEX, "fetch_json",
                      lambda url: _openalex_work("T", doi="10.1/a,b"))
  vc.main(["--input", str(f)])
  assert "1 not retraction-checked" in capsys.readouterr().err


def test_main_no_unchecked_warning_when_all_checked(monkeypatch, tmp_path,
                                                    capsys):
  f = tmp_path / "refs.json"
  f.write_text(json.dumps([{"doi": "10.1/x"}]))
  monkeypatch.setattr(vc._OPENALEX, "fetch_json",
                      lambda url: _openalex_work("T"))
  monkeypatch.setattr(vc._CROSSREF, "fetch_json", _crossref(0))
  vc.main(["--input", str(f)])
  assert "not retraction-checked" not in capsys.readouterr().err


def test_crossref_user_agent_prefers_env_override(monkeypatch):
  monkeypatch.setenv(vc._CROSSREF_UA_ENV, "lab-bot (mailto:pi@uni.edu)")
  assert vc.crossref_user_agent() == "lab-bot (mailto:pi@uni.edu)"


def test_crossref_user_agent_falls_back_to_default(monkeypatch):
  monkeypatch.delenv(vc._CROSSREF_UA_ENV, raising=False)
  assert vc.crossref_user_agent() == vc._DEFAULT_CROSSREF_UA


def test_crossref_user_agent_ignores_empty_env(monkeypatch):
  monkeypatch.setenv(vc._CROSSREF_UA_ENV, "")
  assert vc.crossref_user_agent() == vc._DEFAULT_CROSSREF_UA


def test_crossref_catches_retraction_openalex_missed(monkeypatch):
  monkeypatch.setattr(vc._OPENALEX, "fetch_json",
                      lambda url: _openalex_work("Clean Looking Paper"))
  monkeypatch.setattr(vc._CROSSREF, "fetch_json", _crossref(1))
  result = vc.verify_one({"doi": "10.1/x", "title": None, "raw": "x"})
  assert result["status"] == "retracted"


def test_crossref_not_queried_when_openalex_already_retracted(monkeypatch):
  monkeypatch.setattr(vc._OPENALEX, "fetch_json",
                      lambda url: _openalex_work("T", retracted=True))

  def fail(url):
    raise AssertionError("Crossref should not be queried")
  monkeypatch.setattr(vc._CROSSREF, "fetch_json", fail)
  assert vc.verify_one({"doi": "10.1/x", "title": None,
                        "raw": "x"})["status"] == "retracted"


def test_mismatch_still_wins_over_clean_crossref(monkeypatch):
  monkeypatch.setattr(vc._OPENALEX, "fetch_json",
                      lambda url: _openalex_work("The Actual Title"))
  monkeypatch.setattr(vc._CROSSREF, "fetch_json", _crossref(0))
  result = vc.verify_one({"doi": "10.1/x", "title": "A Fabricated Title Here",
                          "raw": "x"})
  assert result["status"] == "mismatched"


def test_doi_retracted_flagged(monkeypatch):
  monkeypatch.setattr(vc._OPENALEX, "fetch_json",
                      lambda url: _openalex_work("Real Title", retracted=True))
  result = vc.verify_one({"doi": "10.1/x", "title": "Real Title", "raw": "x"})
  assert result["status"] == "retracted"
  assert result["matched_title"] == "Real Title"


def test_title_retracted_flagged(monkeypatch):
  monkeypatch.setattr(vc._OPENALEX, "fetch_json", lambda url: {
      "results": [_openalex_work("Some Retracted Study", retracted=True)]})
  result = vc.verify_one({"doi": None, "title": "Some Retracted Study",
                          "raw": "t"})
  assert result["status"] == "retracted"


def test_main_nonzero_exit_on_retracted(monkeypatch, tmp_path, capsys):
  f = tmp_path / "refs.json"
  f.write_text(json.dumps([{"doi": "10.1/x"}]))
  monkeypatch.setattr(vc._OPENALEX, "fetch_json",
                      lambda url: _openalex_work("T", retracted=True))
  code = vc.main(["--input", str(f)])
  out = json.loads(capsys.readouterr().out)
  assert code == 1
  assert out["retracted"] == 1


if __name__ == "__main__":
  sys.exit(pytest.main([__file__, "-v"]))
