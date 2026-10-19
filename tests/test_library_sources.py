import json
import pathlib
import sys

import pymupdf
import pytest

_SCRIPTS = (pathlib.Path(__file__).resolve().parent.parent
            / "skills/literature-review/scripts")
sys.path.insert(0, str(_SCRIPTS))

import http_client  # noqa: E402
import library_sources  # noqa: E402
import verify_citations  # noqa: E402
import zotero_local  # noqa: E402

_BIB = r"""
@article{lumen2024,
  title = {Sleep and {Memory} in Adolescents},
  author = {Lumen, Ana and van der Berg, Jo{\"e}l and {World Health Organization}},
  year = {2024},
  doi = {10.1234/ABC.5},
  pmid = {123},
  file = {Full Text PDF:/abs/lumen.pdf:application/pdf;Snapshot:/abs/lumen.html:text/html}
}
@misc{vale2023,
  title = {Attention Is Measured},
  author = {Vale, Bo},
  year = {2023},
  eprint = {2301.01234},
  archiveprefix = {arXiv},
  file = {files/vale.pdf}
}
@report{grey2022,
  title = {A Ministry Report},
  author = {Reed, Cy},
  year = {2022}
}
"""


def _bib(tmp_path, text=_BIB):
  path = tmp_path / "lib.bib"
  path.write_text(text, encoding="utf-8")
  return path


def test_bibtex_maps_identifiers_authors_and_year(tmp_path):
  lumen, vale, grey = library_sources.read_bibtex(_bib(tmp_path))
  assert lumen["title"] == "Sleep and Memory in Adolescents"
  assert lumen["DOI"] == "10.1234/ABC.5"
  assert lumen["PMID"] == "123"
  assert lumen["author"] == [
      {"family": "Lumen", "given": "Ana"},
      {"family": "van der Berg", "given": "Joël"},
      {"literal": "World Health Organization"}]
  assert lumen["issued"] == {"date-parts": [[2024]]}
  assert vale["arxiv"] == "2301.01234"
  assert grey["DOI"] is None and grey["arxiv"] is None


def test_bibtex_file_field_gives_the_pdf_and_origin(tmp_path):
  lumen, vale, grey = library_sources.read_bibtex(_bib(tmp_path))
  assert lumen["pdf"] == "/abs/lumen.pdf"
  assert lumen["origin"] == {"kind": "file", "path": "/abs/lumen.pdf"}
  assert vale["pdf"] == str((tmp_path / "files/vale.pdf").resolve())
  assert grey["pdf"] is None and grey["origin"] is None


@pytest.mark.parametrize("field, expected", [
    (r"Full Text:C\:\\Users\\me\\w.pdf:application/pdf", r"C:\Users\me\w.pdf"),
    (r"C:\Users\me\w.pdf", r"C:\Users\me\w.pdf"),
    (r"Full Text PDF:/abs/a\;b.pdf:application/pdf", "/abs/a;b.pdf"),
])
def test_bibtex_unescapes_zotero_file_paths(tmp_path, field, expected):
  text = "@article{w, title={T}, author={A, B}, year={2020}, file={" + field + "}}"
  (item,) = library_sources.read_bibtex(_bib(tmp_path, text))
  assert item["pdf"] == expected
  assert item["origin"] == {"kind": "file", "path": expected}


def test_unparsable_bibtex_is_an_error(tmp_path):
  with pytest.raises(ValueError, match="no BibTeX entries"):
    library_sources.read_bibtex(_bib(tmp_path, "@article{broken, title = {x"))


def test_csl_maps_identifiers_and_arxiv(tmp_path):
  path = tmp_path / "lib.json"
  path.write_text(json.dumps([
      {"id": "a", "type": "article-journal", "title": "T",
       "DOI": "10.1/x", "PMCID": "PMC9", "author": [{"family": "Lumen"}],
       "issued": {"date-parts": [[2021, 3]]}},
      {"id": "b", "type": "article", "title": "P",
       "number": "arXiv:2101.00001v2"}]), encoding="utf-8")
  first, second = library_sources.read_csl(path)
  assert (first["DOI"], first["PMCID"], first["pdf"]) == ("10.1/x", "PMC9", None)
  assert first["issued"] == {"date-parts": [[2021, 3]]}
  assert second["arxiv"] == "2101.00001"


def test_csl_must_be_an_array(tmp_path):
  path = tmp_path / "lib.json"
  path.write_text("{}", encoding="utf-8")
  with pytest.raises(ValueError, match="CSL JSON array"):
    library_sources.read_csl(path)


def _pdf(path, text):
  doc = pymupdf.open()
  page = doc.new_page()
  if text:
    page.insert_text((72, 72), text)
  path.parent.mkdir(parents=True, exist_ok=True)
  doc.save(path)
  return path


def test_zotero_reader_walks_subcollections_once(monkeypatch, tmp_path):
  pdf = _pdf(tmp_path / "z.pdf", "x")
  monkeypatch.setattr(zotero_local, "collection_key",
                      lambda c, names=None: "ROOT")
  monkeypatch.setattr(zotero_local, "collection_names",
                      lambda: {"ROOT": "Review", "SUB": "Methods"})
  monkeypatch.setattr(zotero_local, "subcollection_keys",
                      lambda k: ["ROOT", "SUB"])
  shared = ("ITEM1", {"id": "0/ITEM1", "title": "Shared", "DOI": "10.1/s"})
  monkeypatch.setattr(zotero_local, "collection_items", lambda k: {
      "ROOT": [shared], "SUB": [shared, ("ITEM2", {"title": "Only sub"})]}[k])
  monkeypatch.setattr(zotero_local, "pdf_attachment",
                      lambda k: "ATT1" if k == "ITEM1" else None)
  monkeypatch.setattr(zotero_local, "attachment_path", lambda k: pdf)

  items, counts = library_sources.read_zotero("Review")

  assert counts == {"Review": 1, "Methods": 2}
  assert [i["title"] for i in items] == ["Shared", "Only sub"]
  assert items[0]["zotero"] == "ITEM1"
  assert items[0]["pdf"] == str(pdf)
  assert items[0]["origin"] == {"kind": "zotero", "item": "ITEM1",
                                "attachment": "ATT1"}
  assert items[1]["pdf"] is None and items[1]["origin"] is None


def test_zotero_attachment_missing_from_disk_keeps_its_origin(
    monkeypatch):
  monkeypatch.setattr(zotero_local, "collection_key",
                      lambda c, names=None: "ROOT")
  monkeypatch.setattr(zotero_local, "collection_names", lambda: {"ROOT": "R"})
  monkeypatch.setattr(zotero_local, "subcollection_keys", lambda k: ["ROOT"])
  monkeypatch.setattr(zotero_local, "collection_items",
                      lambda k: [("ITEM1", {"title": "T"})])
  monkeypatch.setattr(zotero_local, "pdf_attachment", lambda k: "ATT1")
  monkeypatch.setattr(zotero_local, "attachment_path", lambda k: None)

  (item,), _ = library_sources.read_zotero("R")

  assert item["pdf"] is None
  assert item["origin"]["kind"] == "zotero"


def test_first_page_doi_and_text(tmp_path):
  with_doi = _pdf(tmp_path / "a.pdf", "Journal. doi:10.1234/Abc.5.")
  blank = _pdf(tmp_path / "b.pdf", "")
  assert library_sources.first_page_doi(with_doi) == "10.1234/Abc.5"
  assert library_sources.first_page_doi(blank) is None
  assert library_sources.first_page_text(blank).strip() == ""
  assert library_sources.first_page_text(tmp_path / "missing.pdf") == ""


def test_pdf_files_is_recursive_and_case_insensitive(tmp_path):
  a = _pdf(tmp_path / "x" / "A.PDF", "a")
  b = _pdf(tmp_path / "b.pdf", "b")
  (tmp_path / "notes.txt").write_text("n", encoding="utf-8")
  assert library_sources.pdf_files(tmp_path) == sorted([a, b])


def test_pdf_folder_resolves_dois_through_crossref(monkeypatch, tmp_path):
  good = _pdf(tmp_path / "good.pdf", "doi:10.1000/good")
  dead = _pdf(tmp_path / "dead.pdf", "doi:10.1000/dead")
  bare = _pdf(tmp_path / "bare.pdf", "no identifier here")

  def fetch_json(path, **kwargs):
    if "10.1000/good" in path:
      return {"title": "Good paper", "DOI": "10.1000/good",
              "author": [{"family": "Lumen", "given": "Ana"}]}
    raise http_client.HttpError("missing", status_code=404)

  monkeypatch.setattr(verify_citations._CROSSREF, "fetch_json", fetch_json)
  items, unmatched = library_sources.read_pdf_folder(tmp_path)

  assert [(i["title"], i["pdf"]) for i in items] == [("Good paper", str(good))]
  assert items[0]["origin"] == {"kind": "file", "path": str(good)}
  assert sorted(unmatched) == sorted([str(dead), str(bare)])


def test_crossref_csl_uses_the_transform_route(monkeypatch):
  seen = []
  monkeypatch.setattr(verify_citations._CROSSREF, "fetch_json",
                      lambda path, **kw: seen.append(path) or {"DOI": "10.1/x"})
  assert library_sources.crossref_csl("10.1/x") == {"DOI": "10.1/x"}
  assert seen == [
      "works/10.1/x/transform/application/vnd.citationstyles.csl+json"]
