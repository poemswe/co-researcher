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
_SCRIPT = _SCRIPTS / "build_corpus.py"
_spec = importlib.util.spec_from_file_location("build_corpus", _SCRIPT)
bc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bc)


def _write(tmp_path, name, payload):
  f = tmp_path / name
  f.write_text(json.dumps(payload))
  return str(f)


def test_normalize_key_prefers_doi():
  assert bc.normalize_key("10.1/ABC", "Some Title") == "10.1/abc"


def test_normalize_key_falls_back_to_title():
  assert bc.normalize_key(None, "Attention Is All You Need!") == (
      "attentionisallyouneed")


def test_load_openalex_shapes_records(tmp_path):
  path = _write(tmp_path, "oa.json", {"results": [
      {"id": "https://openalex.org/W1",
       "doi": "https://doi.org/10.1/x",
       "title": "A Paper", "publication_year": 2024, "cited_by_count": 7,
       "authorships": [{"author": {"display_name": "Alice Smith"}}]}]})
  recs = bc.load_openalex(path)
  assert len(recs) == 1
  r = recs[0]
  assert r["key"] == "10.1/x"
  assert r["title"] == "A Paper"
  assert r["authors"] == ["Alice Smith"]
  assert r["year"] == 2024
  assert r["cited_by"] == 7
  assert r["found_via"] == "openalex"
  assert r["ids"]["doi"] == "10.1/x"
  assert r["screening"] == {"status": None, "stage": None, "reason": None}
  assert r["fulltext"] is None


def test_load_arxiv_shapes_records(tmp_path):
  path = _write(tmp_path, "ax.json", {"papers": [
      {"id": "1706.03762v1", "title": "Attention Is All You Need",
       "published": "2017-06-12T00:00:00Z",
       "authors": ["Ashish Vaswani", "Noam Shazeer"]}]})
  recs = bc.load_arxiv(path)
  r = recs[0]
  assert r["key"] == "attentionisallyouneed"
  assert r["year"] == 2017
  assert r["authors"] == ["Ashish Vaswani", "Noam Shazeer"]
  assert r["found_via"] == "arxiv"
  assert r["ids"]["arxiv"] == "1706.03762v1"


def test_load_epmc_shapes_records(tmp_path):
  path = _write(tmp_path, "ep.json", {"results": [
      {"doi": "10.2/y", "title": "Bio Paper", "pubYear": "2021",
       "pmid": "123", "pmcid": "PMC9", "citedByCount": 4,
       "authorList": {"author": [{"fullName": "Jane Doe"}]}}]})
  r = bc.load_epmc(path)[0]
  assert r["key"] == "10.2/y"
  assert r["year"] == 2021
  assert r["cited_by"] == 4
  assert r["authors"] == ["Jane Doe"]
  assert r["ids"]["pmcid"] == "PMC9"
  assert r["found_via"] == "epmc"


def test_load_epmc_falls_back_to_author_string(tmp_path):
  path = _write(tmp_path, "ep.json", {"results": [
      {"doi": "10.2/y", "title": "Bio Paper", "pubYear": "2021",
       "authorString": "Jane Doe; John Roe"}]})
  assert bc.load_epmc(path)[0]["authors"] == ["Jane Doe", "John Roe"]


def test_merge_dedupes_and_joins_found_via():
  a = [{"key": "10.1/x", "ids": {"doi": "10.1/x"}, "title": "T", "year": 2024,
        "cited_by": 5, "found_via": "openalex",
        "screening": {"status": None, "stage": None, "reason": None},
        "fulltext": None, "role": None}]
  b = [{"key": "10.1/x", "ids": {"pmcid": "PMC1"}, "title": "T", "year": 2024,
        "cited_by": 0, "found_via": "epmc",
        "screening": {"status": None, "stage": None, "reason": None},
        "fulltext": None, "role": None}]
  merged = bc.merge(a + b)
  assert len(merged) == 1
  assert merged[0]["found_via"] == "openalex+epmc"
  assert merged[0]["ids"] == {"doi": "10.1/x", "pmcid": "PMC1"}
  assert merged[0]["cited_by"] == 5


def test_merge_preserves_existing_screening_and_fulltext():
  existing = [{"key": "10.1/x", "ids": {"doi": "10.1/x"}, "title": "T",
               "year": 2024, "cited_by": 5, "found_via": "openalex",
               "screening": {"status": "included", "stage": "title_abstract",
                             "reason": None},
               "fulltext": "fulltext", "role": "evidence"}]
  fresh = [{"key": "10.1/x", "ids": {"doi": "10.1/x"}, "title": "T",
            "year": 2024, "cited_by": 9, "found_via": "arxiv",
            "screening": {"status": None, "stage": None, "reason": None},
            "fulltext": None, "role": None}]
  merged = bc.merge(existing + fresh)
  r = merged[0]
  assert r["screening"]["status"] == "included"
  assert r["fulltext"] == "fulltext"
  assert r["role"] == "evidence"
  assert r["cited_by"] == 9


def test_merge_backfills_authors_into_legacy_record():
  existing = [{"key": "10.1/x", "ids": {"doi": "10.1/x"}, "title": "T",
               "year": 2024, "cited_by": 5, "found_via": "openalex",
               "screening": {"status": "included", "stage": "title_abstract",
                             "reason": None},
               "fulltext": "fulltext", "role": "evidence"}]
  fresh = [{**existing[0], "authors": ["Alice Smith"],
            "screening": {"status": None, "stage": None, "reason": None}}]
  assert bc.merge(existing + fresh)[0]["authors"] == ["Alice Smith"]


def test_main_writes_corpus_and_reports(tmp_path, capsys):
  oa = _write(tmp_path, "oa.json", {"results": [
      {"id": "W1", "doi": "https://doi.org/10.1/x", "title": "Shared",
       "publication_year": 2024, "cited_by_count": 3}]})
  ep = _write(tmp_path, "ep.json", {"results": [
      {"doi": "10.1/x", "title": "Shared", "pubYear": "2024"},
      {"doi": "10.3/z", "title": "Unique", "pubYear": "2023"}]})
  out = tmp_path / "corpus.json"
  code = bc.main(["--openalex", oa, "--epmc", ep, "--output", str(out)])
  assert code == 0
  corpus = json.loads(out.read_text())
  assert len(corpus) == 2
  shared = next(r for r in corpus if r["key"] == "10.1/x")
  assert shared["found_via"] == "openalex+epmc"
  assert "2 records" in capsys.readouterr().err


def test_normalize_key_falls_back_to_stable_identifier():
  assert bc.normalize_key(None, None, {"arxiv": "1706.03762v1"}) == (
      "arxiv:1706.03762v1")
  assert bc.normalize_key(None, "", {"pmcid": "PMC9"}) == "pmcid:PMC9"


def test_normalize_key_none_when_nothing_identifies_the_record():
  assert bc.normalize_key(None, "", {}) is None


def test_untitled_records_with_distinct_ids_do_not_collide(tmp_path):
  path = _write(tmp_path, "ep.json", {"results": [
      {"title": None, "pmid": "111"},
      {"title": "", "pmid": "222"}]})
  recs = bc.load_epmc(path)
  assert len(recs) == 2
  assert len(bc.merge(recs)) == 2


def test_unidentifiable_record_is_dropped_with_warning(tmp_path, capsys):
  path = _write(tmp_path, "ep.json", {"results": [
      {"title": None}, {"doi": "10.1/keep", "title": "Kept"}]})
  recs = bc.load_epmc(path)
  assert [r["key"] for r in recs] == ["10.1/keep"]
  assert "no DOI, title, or identifier" in capsys.readouterr().err


def test_main_summary_reports_skipped_records(tmp_path, capsys):
  path = _write(tmp_path, "ep.json", {"results": [
      {"title": None}, {"doi": "10.1/keep", "title": "Kept"}]})
  out = tmp_path / "corpus.json"
  bc.main(["--epmc", path, "--output", str(out)])
  err = capsys.readouterr().err
  assert "1 record skipped" in err
  assert len(json.loads(out.read_text())) == 1


def test_main_summary_omits_skipped_when_none(tmp_path, capsys):
  path = _write(tmp_path, "ep.json", {"results": [
      {"doi": "10.1/keep", "title": "Kept"}]})
  bc.main(["--epmc", path, "--output", str(tmp_path / "corpus.json")])
  assert "skipped" not in capsys.readouterr().err


def test_load_epmc_reads_citation_and_reference_lists(tmp_path):
  cites = _write(tmp_path, "cit.json", {"hitCount": 1, "citations": [
      {"doi": "10.1/a", "title": "Citing Paper", "pubYear": "2024"}]})
  refs = _write(tmp_path, "ref.json", {"hitCount": 1, "references": [
      {"doi": "10.1/b", "title": "Referenced Paper", "pubYear": "2019"}]})
  assert bc.load_epmc(cites)[0]["key"] == "10.1/a"
  assert bc.load_epmc(refs)[0]["key"] == "10.1/b"


def test_found_via_override_tags_snowball_provenance(tmp_path):
  cites = _write(tmp_path, "cit.json", {"citations": [
      {"doi": "10.1/a", "title": "Citing Paper"}]})
  out = tmp_path / "corpus.json"
  bc.main(["--epmc", cites, "--found-via", "snowball:citations",
           "--output", str(out)])
  corpus = json.loads(out.read_text())
  assert corpus[0]["found_via"] == "snowball:citations"


def test_found_via_override_joins_with_existing_source(tmp_path):
  out = tmp_path / "corpus.json"
  out.write_text(json.dumps([
      {"key": "10.1/a", "ids": {"doi": "10.1/a"}, "title": "P", "year": 2024,
       "cited_by": 0, "found_via": "openalex",
       "screening": {"status": None, "stage": None, "reason": None},
       "fulltext": None, "role": None}]))
  cites = _write(tmp_path, "cit.json", {"citations": [
      {"doi": "10.1/a", "title": "P"}]})
  bc.main(["--epmc", cites, "--found-via", "snowball:citations",
           "--output", str(out)])
  corpus = json.loads(out.read_text())
  assert corpus[0]["found_via"] == "openalex+snowball:citations"


def test_main_resumes_from_existing_corpus(tmp_path):
  out = tmp_path / "corpus.json"
  out.write_text(json.dumps([
      {"key": "10.1/x", "ids": {"doi": "10.1/x"}, "title": "Shared",
       "year": 2024, "cited_by": 3, "found_via": "openalex",
       "screening": {"status": "excluded", "stage": "title_abstract",
                     "reason": "wrong population"},
       "fulltext": None, "role": None}]))
  ep = _write(tmp_path, "ep.json", {"results": [
      {"doi": "10.1/x", "title": "Shared", "pubYear": "2024"}]})
  bc.main(["--epmc", ep, "--output", str(out)])
  corpus = json.loads(out.read_text())
  assert len(corpus) == 1
  assert corpus[0]["screening"]["reason"] == "wrong population"


if __name__ == "__main__":
  sys.exit(pytest.main([__file__, "-v"]))
