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
import pathlib
import sys

import pytest

_SCRIPTS = pathlib.Path(__file__).resolve().parent.parent / (
    "skills/literature-review/scripts"
)


def _load(name):
  spec = importlib.util.spec_from_file_location(name, _SCRIPTS / f"{name}.py")
  module = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(module)
  return module


download_paper = _load("download_paper")
download_paper_source = _load("download_paper_source")


def _raise(status):
  def fetch(url, **kwargs):
    raise download_paper.http_client.HttpError("boom", status_code=status)

  return fetch


def test_download_paper_404_prints_message(tmp_path, capsys, monkeypatch):
  monkeypatch.setattr(download_paper._CLIENT, "fetch_bytes", _raise(404))
  args = argparse.Namespace(id="0000.0", format="pdf", output=str(tmp_path / "p"))
  download_paper.download_paper(args)
  assert "404" in capsys.readouterr().err


def test_download_paper_html_404_suggests_pdf(tmp_path, capsys, monkeypatch):
  monkeypatch.setattr(download_paper._CLIENT, "fetch_bytes", _raise(404))
  args = argparse.Namespace(id="0000.0", format="html",
                            output=str(tmp_path / "p"))
  download_paper.download_paper(args)
  err = capsys.readouterr().err
  assert "HTML format is not available" in err
  assert "--format pdf" in err


def test_download_paper_non_404_reraises(tmp_path, monkeypatch):
  monkeypatch.setattr(download_paper._CLIENT, "fetch_bytes", _raise(500))
  args = argparse.Namespace(id="0000.0", format="pdf", output=str(tmp_path / "p"))
  with pytest.raises(download_paper.http_client.HttpError):
    download_paper.download_paper(args)


def test_download_source_404_prints_message(tmp_path, capsys, monkeypatch):
  monkeypatch.setattr(download_paper_source._CLIENT, "fetch_bytes", _raise(404))
  args = argparse.Namespace(id="0000.0", output=str(tmp_path / "s.tar.gz"))
  download_paper_source.download_source(args)
  assert "404" in capsys.readouterr().err


def test_download_source_non_404_reraises(tmp_path, monkeypatch):
  monkeypatch.setattr(download_paper_source._CLIENT, "fetch_bytes", _raise(503))
  args = argparse.Namespace(id="0000.0", output=str(tmp_path / "s.tar.gz"))
  with pytest.raises(download_paper_source.http_client.HttpError):
    download_paper_source.download_source(args)


if __name__ == "__main__":
  sys.exit(pytest.main([__file__, "-v"]))
