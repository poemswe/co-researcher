# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pytest",
#   "python-dotenv",
# ]
# ///

import argparse
import importlib.util
import json
import pathlib
import sys

import pytest

_SCRIPTS = (pathlib.Path(__file__).resolve().parent.parent
            / "skills/literature-review/scripts")
sys.path.insert(0, str(_SCRIPTS))
_SCRIPT = _SCRIPTS / "openalex_cli.py"
_spec = importlib.util.spec_from_file_location("openalex_cli", _SCRIPT)
openalex_cli = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(openalex_cli)


def _args():
  return argparse.Namespace(
      entity_type="works", search="x", filter=None, group_by=None,
      sample=None, seed=None, select=None, sort=None, per_page=1, page=1,
      api_key=None)


def test_handle_filter_prints_hit_count_to_stderr(capsys, monkeypatch):
  monkeypatch.setattr(openalex_cli, "fetch_with_retry",
                      lambda *a, **k: {"meta": {"count": 42},
                                       "results": [{"id": "W1"}]})
  openalex_cli.handle_filter(_args())
  captured = capsys.readouterr()
  assert "OpenAlex: 42 total hits (1 on this page)" in captured.err
  assert json.loads(captured.out)["meta"]["count"] == 42


def test_handle_filter_tolerates_missing_meta(capsys, monkeypatch):
  monkeypatch.setattr(openalex_cli, "fetch_with_retry",
                      lambda *a, **k: {"results": []})
  openalex_cli.handle_filter(_args())
  captured = capsys.readouterr()
  assert "total hits" not in captured.err
  assert json.loads(captured.out) == {"results": []}


if __name__ == "__main__":
  sys.exit(pytest.main([__file__, "-v"]))
