import json
import pathlib

import pytest

from claim_verifier_benchmark.cli import main


FIXTURE = pathlib.Path(__file__).parents[1] / "fixtures" / "split-vector.json"


def test_enumerate_coverage_prints_machine_readable_json(tmp_path, capsys):
  synthesis = tmp_path / "synthesis.md"
  synthesis.write_text("Admissions fell (García, 2022).", encoding="utf-8")
  assert main(["enumerate-coverage", str(synthesis)]) == 0
  output = json.loads(capsys.readouterr().out)
  assert output["unit_count"] == 1
  assert output["units"][0]["citation_identity"] == "author:garcía:2022"


def test_manifest_command_reports_digest(tmp_path, capsys):
  (tmp_path / "a.txt").write_text("alpha", encoding="utf-8")
  assert main(["manifest", str(tmp_path), "a.txt"]) == 0
  output = json.loads(capsys.readouterr().out)
  assert len(output["manifest_sha256"]) == 64


def test_split_vector_command_accepts_normative_fixture(capsys):
  assert main(["check-split-vector", str(FIXTURE)]) == 0
  assert json.loads(capsys.readouterr().out) == {"valid": True}


def test_commit_mapping_prints_deterministic_machine_readable_json(tmp_path, capsys):
  mapping = tmp_path / "mapping.json"
  mapping.write_text('{"review_1":"case-1"}', encoding="utf-8")
  assert main(["commit-mapping", str(mapping), "00" * 32]) == 0
  assert json.loads(capsys.readouterr().out) == {
      "mapping_commitment": (
          "e8f2a2a2bff43580592be1328997dd3d023ea66f392cea93ff0957931df41650"
      ),
  }


@pytest.mark.parametrize(
    ("arguments", "contents", "expected_error"),
    [
        (
            ["check-split-vector"],
            "[]",
            "must contain a JSON object",
        ),
        (
            ["commit-mapping", "00" * 32],
            "[]",
            "must contain a JSON object",
        ),
        (
            ["check-split-vector"],
            json.dumps({
                "output_value": "00" * 64,
                "construction_archive_sha256": "00" * 32,
                "expected_split_key": "00" * 32,
                "domain": "medicine",
                "paper_ids": ["p1", "p2", "p3", "p4", "p5"],
            }),
            "split vector has missing or unexpected fields",
        ),
        (
            ["check-split-vector"],
            json.dumps({
                "output_value": "00" * 64,
                "construction_archive_sha256": "00" * 32,
                "expected_split_key": "00" * 32,
                "domain": "medicine",
                "paper_ids": ["p1", "p1", "p3", "p4", "p5"],
                "expected_order": ["p1", "p1", "p3", "p4", "p5"],
            }),
            "split vector paper IDs and expected order must match",
        ),
    ],
)
def test_data_errors_return_two_write_stderr_and_no_json(
    tmp_path, capsys, arguments, contents, expected_error,
):
  data = tmp_path / "input.json"
  data.write_text(contents, encoding="utf-8")
  assert main([arguments[0], str(data), *arguments[1:]]) == 2
  captured = capsys.readouterr()
  assert captured.out == ""
  assert captured.err.startswith("error: ")
  assert expected_error in captured.err


@pytest.mark.parametrize(
    ("salt_hex", "expected_error"),
    [
        ("00" * 31, "mapping salt must contain exactly 64 hex characters"),
        ("zz" * 32, "mapping salt is not hexadecimal"),
    ],
)
def test_commit_mapping_rejects_invalid_salt_without_success_json(
    tmp_path, capsys, salt_hex, expected_error,
):
  mapping = tmp_path / "mapping.json"
  mapping.write_text("{}", encoding="utf-8")
  assert main(["commit-mapping", str(mapping), salt_hex]) == 2
  captured = capsys.readouterr()
  assert captured.out == ""
  assert captured.err == f"error: {expected_error}\n"


def test_missing_operational_input_returns_two_with_no_success_json(tmp_path, capsys):
  missing = tmp_path / "missing.md"
  assert main(["enumerate-coverage", str(missing)]) == 2
  captured = capsys.readouterr()
  assert captured.out == ""
  assert captured.err.startswith("error: ")


@pytest.mark.parametrize("arguments", [[], ["not-a-command"]])
def test_argument_parse_errors_return_two_with_no_success_json(arguments, capsys):
  assert main(arguments) == 2
  captured = capsys.readouterr()
  assert captured.out == ""
  assert captured.err
