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


if __name__ == "__main__":
  sys.exit(pytest.main([__file__, "-v"]))
