import json
import pathlib
import sys

import pytest

_SCRIPTS = (pathlib.Path(__file__).resolve().parent.parent
            / "skills/literature-review/scripts")
sys.path.insert(0, str(_SCRIPTS))

import library_sources  # noqa: E402

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


def test_bibtex_windows_file_path_does_not_crash(tmp_path):
  text = ("@article{w, title={T}, author={A, B}, year={2020},"
          r" file={Full Text:C\:\\Users\\me\\w.pdf:application/pdf}}")
  (item,) = library_sources.read_bibtex(_bib(tmp_path, text))
  assert item["pdf"] is None or item["pdf"].lower().endswith("w.pdf")


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
