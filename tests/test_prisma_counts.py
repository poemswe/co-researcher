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
_SCRIPT = _SCRIPTS / "prisma_counts.py"
_spec = importlib.util.spec_from_file_location("prisma_counts", _SCRIPT)
pc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pc)


def _record(found_via="openalex", status="included", reason=None,
            fulltext="fulltext"):
  return {"key": "k", "found_via": found_via, "fulltext": fulltext,
          "screening": {"status": status, "stage": "title", "reason": reason}}


def _write(tmp_path, records):
  f = tmp_path / "corpus.json"
  f.write_text(json.dumps(records))
  return str(f)


def test_counts_happy_path(tmp_path, capsys):
  records = [
      _record("openalex", "included", fulltext="fulltext"),
      _record("openalex", "included", fulltext="abstract-only"),
      _record("arxiv", "excluded", reason="wrong population"),
      _record("snowball:refs", "excluded", reason="wrong population"),
  ]
  code = pc.main(["--corpus", _write(tmp_path, records)])
  out = json.loads(capsys.readouterr().out)
  assert code == 0
  assert out["records_by_source"] == {"openalex": 2, "arxiv": 1,
                                      "snowball:refs": 1}
  assert out["after_dedup"] == 4
  assert out["excluded"] == {"wrong population": 2}
  assert out["included"] == 2
  assert out["not_retrieved"] == 1
  assert out["in_synthesis"] == 1


def test_wrapped_container_and_missing_fields(tmp_path, capsys):
  f = tmp_path / "corpus.json"
  f.write_text(json.dumps({"records": [{"key": "bare"}]}))
  code = pc.main(["--corpus", str(f)])
  out = json.loads(capsys.readouterr().out)
  assert out["after_dedup"] == 1
  assert out["screened"] == 0
  assert out["records_by_source"] == {"unknown": 1}
  assert code == 0


def test_missing_exclusion_reason_exits_nonzero(tmp_path, capsys):
  records = [_record(status="excluded", reason=None)]
  code = pc.main(["--corpus", _write(tmp_path, records)])
  out = json.loads(capsys.readouterr().out)
  assert code == 1
  assert out["excluded"] == {"unspecified": 1}


if __name__ == "__main__":
  sys.exit(pytest.main([__file__, "-v"]))
