import json
import pathlib
import sys

import pymupdf
import pytest

_SCRIPTS = (pathlib.Path(__file__).resolve().parent.parent
            / "skills/literature-review/scripts")
sys.path.insert(0, str(_SCRIPTS))

import import_library  # noqa: E402
import library_sources  # noqa: E402
import verify_citations  # noqa: E402
import zotero_local  # noqa: E402


def _pdf(path, text):
  doc = pymupdf.open()
  page = doc.new_page()
  if text:
    page.insert_text((72, 72), text)
  path.parent.mkdir(parents=True, exist_ok=True)
  doc.save(path)
  return path


def _item(**fields):
  item = {"title": None, "DOI": None, "arxiv": None, "PMID": None,
          "PMCID": None, "author": [], "issued": None, "zotero": None,
          "pdf": None, "origin": None}
  item.update(fields)
  return item


@pytest.fixture(autouse=True)
def _no_title_lookups(monkeypatch):
  monkeypatch.setattr(verify_citations, "resolve_title", lambda title: None)


def _run(capsys, *argv):
  capsys.readouterr()
  code = import_library.main(list(argv))
  out = capsys.readouterr().out.strip()
  return code, json.loads(out) if out else None


@pytest.mark.parametrize("fields, name", [
    ({"DOI": "https://doi.org/10.1234/ABC"}, "10.1234_abc"),
    ({"arxiv": "2301.01234"}, "2301.01234"),
    ({"PMCID": "PMC9"}, "PMC9"),
    ({"title": "A Ministry Report", "PMID": "7"}, "aministryreport"),
])
def test_paper_dir_name_matches_read_paper(fields, name):
  assert import_library.paper_dir_name(_item(**fields)) == name


def test_title_lookup_fills_a_missing_doi(monkeypatch):
  monkeypatch.setattr(verify_citations, "resolve_title",
                      lambda title: {"doi": "10.1/found"} if title == "Known" else None)
  items = [_item(title="Known"), _item(title="Unknown"),
           _item(title="Has arXiv", arxiv="2301.00001")]
  assert import_library.resolve_missing_dois(items) == ["Known"]
  assert [i["DOI"] for i in items] == ["10.1/found", None, None]


def test_pdf_dir_matches_by_first_page_doi(tmp_path):
  one = _pdf(tmp_path / "pdfs/one.pdf", "doi:10.1000/ONE")
  twin_a = _pdf(tmp_path / "pdfs/twin_a.pdf", "doi:10.1000/twin")
  twin_b = _pdf(tmp_path / "pdfs/twin_b.pdf", "10.1000/twin")
  stray = _pdf(tmp_path / "pdfs/stray.pdf", "doi:10.1000/other")
  bare = _pdf(tmp_path / "pdfs/bare.pdf", "nothing")
  items = [_item(DOI="10.1000/one"), _item(DOI="10.1000/twin"), _item(title="T")]

  unmatched, conflicts = import_library.match_pdf_dir(items, tmp_path / "pdfs")

  assert items[0]["pdf"] == str(one)
  assert items[0]["origin"] == {"kind": "file", "path": str(one)}
  assert items[1]["pdf"] is None
  assert sorted(conflicts) == sorted([str(twin_a), str(twin_b)])
  assert sorted(unmatched) == sorted([str(stray), str(bare)])


def test_attachment_wins_over_the_pdf_dir(tmp_path):
  attached = _pdf(tmp_path / "attached.pdf", "a")
  _pdf(tmp_path / "pdfs/other.pdf", "doi:10.1000/one")
  items = [_item(DOI="10.1000/one", pdf=str(attached),
                 origin={"kind": "zotero", "item": "I", "attachment": "A"})]
  import_library.match_pdf_dir(items, tmp_path / "pdfs")
  assert items[0]["pdf"] == str(attached)


def test_place_pdf_writes_origin_and_is_idempotent(tmp_path):
  pdf = _pdf(tmp_path / "src.pdf", "x")
  item = _item(DOI="10.1/x", pdf=str(pdf), origin={"kind": "file", "path": str(pdf)})
  ws = tmp_path / "ws"
  assert import_library.place_pdf(item, ws) is True
  target = ws / "papers/10.1_x"
  assert (target / "paper.pdf").read_bytes() == pdf.read_bytes()
  assert json.loads((target / "paper.origin.json").read_text()) == item["origin"]
  (target / "fulltext.md").write_text("read", encoding="utf-8")
  assert import_library.place_pdf(item, ws) is True


@pytest.mark.parametrize("existing", ["paper.pdf", "fulltext.md"])
def test_place_pdf_refuses_to_overwrite(tmp_path, existing):
  pdf = _pdf(tmp_path / "src.pdf", "x")
  target = tmp_path / "ws/papers/10.1_x"
  target.mkdir(parents=True)
  (target / existing).write_bytes(b"other")
  item = _item(DOI="10.1/x", pdf=str(pdf), origin={"kind": "file", "path": str(pdf)})
  assert import_library.place_pdf(item, tmp_path / "ws") is False
  assert (target / existing).read_bytes() == b"other"


def test_bibtex_import_writes_library_and_summary(tmp_path, capsys):
  good = _pdf(tmp_path / "good.pdf", "text")
  scan = _pdf(tmp_path / "scan.pdf", "")
  bib = tmp_path / "lib.bib"
  bib.write_text(
      "@article{a, title={Good}, author={Lumen, Ana}, year={2024},"
      f" doi={{10.1/good}}, file={{{good}}}}}\n"
      "@article{b, title={Scanned}, author={Vale, Bo}, year={2023},"
      f" doi={{10.1/scan}}, file={{{scan}}}}}\n"
      "@report{c, title={A Ministry Report}, author={Reed, Cy}, year={2022}}\n"
      "@article{d, title={Gone}, author={Reed, Cy}, year={2021},"
      " doi={10.1/gone}, file={/nowhere/gone.pdf}}\n", encoding="utf-8")
  ws = tmp_path / "ws"

  code, summary = _run(capsys, "--file", str(bib), "--workspace", str(ws))

  assert code == 0
  assert summary == {
      "items": 4, "by_collection": {}, "pdfs_matched": 2, "no_pdf": 1,
      "no_identifier": ["A Ministry Report"], "no_text_layer": ["Scanned"],
      "missing_on_disk": ["Gone"], "unmatched_files": [], "conflicts": [],
      "doi_resolved": []}
  library = json.loads((ws / "library.json").read_text(encoding="utf-8"))
  assert library["source"] == "bibtex" and len(library["items"]) == 4
  assert (ws / "papers/10.1_good/paper.pdf").is_file()


def test_rerun_reports_no_new_conflicts(tmp_path, capsys):
  good = _pdf(tmp_path / "good.pdf", "text")
  bib = tmp_path / "lib.bib"
  bib.write_text("@article{a, title={Good}, author={Lumen, Ana}, year={2024},"
                 f" doi={{10.1/good}}, file={{{good}}}}}\n", encoding="utf-8")
  ws = tmp_path / "ws"
  _run(capsys, "--file", str(bib), "--workspace", str(ws))
  (ws / "papers/10.1_good/fulltext.md").write_text("read", encoding="utf-8")
  code, summary = _run(capsys, "--file", str(bib), "--workspace", str(ws))
  assert code == 0 and summary["conflicts"] == []


def test_zotero_import_reports_collection_counts(monkeypatch, tmp_path, capsys):
  monkeypatch.setattr(library_sources, "read_zotero", lambda c: (
      [_item(title="T", DOI="10.1/t", zotero="I1")], {"Review": 1}))
  code, summary = _run(capsys, "--zotero", "Review",
                       "--workspace", str(tmp_path / "ws"))
  assert code == 0
  assert summary["by_collection"] == {"Review": 1}
  assert summary["no_pdf"] == 1


def test_pdf_dir_alone_uses_the_folder_reader(monkeypatch, tmp_path, capsys):
  pdf = _pdf(tmp_path / "pdfs/p.pdf", "doi:10.1/p")
  monkeypatch.setattr(library_sources, "read_pdf_folder", lambda d: (
      [_item(title="P", DOI="10.1/p", pdf=str(pdf),
             origin={"kind": "file", "path": str(pdf)})], [str(tmp_path / "x.pdf")]))
  ws = tmp_path / "ws"
  code, summary = _run(capsys, "--pdf-dir", str(tmp_path / "pdfs"),
                       "--workspace", str(ws))
  assert code == 0
  assert summary["unmatched_files"] == [str(tmp_path / "x.pdf")]
  assert json.loads((ws / "library.json").read_text())["source"] == "pdf_folder"


@pytest.mark.parametrize("argv, message", [
    (["--file", "lib.bib", "--workspace", "relative"], "absolute"),
    (["--file", "lib.txt", "--workspace", "/tmp/ws"], ".bib or .json"),
])
def test_bad_arguments_exit_non_zero(capsys, argv, message):
  code = import_library.main(argv)
  assert code != 0
  assert message in capsys.readouterr().err


def test_unavailable_zotero_exits_with_the_fix(monkeypatch, tmp_path, capsys):
  def down(collection):
    raise zotero_local.ZoteroUnavailable("Zotero is not reachable at localhost:23119.")
  monkeypatch.setattr(library_sources, "read_zotero", down)
  code = import_library.main(["--zotero", "R", "--workspace", str(tmp_path)])
  assert code == 1
  assert "Zotero is not reachable" in capsys.readouterr().err


def test_a_windows_path_on_this_machine_is_missing_on_disk(tmp_path, capsys):
  bib = tmp_path / "lib.bib"
  bib.write_text("@article{w, title={Windows Paper}, author={A, B}, year={2020},"
                 r" doi={10.1000/w}, file={Full Text:C\:\\Users\\me\\w.pdf:application/pdf}}",
                 encoding="utf-8")
  code, summary = _run(capsys, "--file", str(bib), "--workspace", str(tmp_path / "ws"))
  assert code == 0
  assert summary["missing_on_disk"] == ["Windows Paper"]
  assert summary["no_pdf"] == 0
