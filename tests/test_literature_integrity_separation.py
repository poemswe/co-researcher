import json
import pathlib
import sys
from dataclasses import fields, is_dataclass

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[1]
EVALS = ROOT / "evals"
ATTACKS = (
    EVALS / "test-cases/literature-review-integrity/synthetic-attacks")
sys.path.insert(0, str(EVALS))

from lib import literature_integrity  # noqa: E402
from lib.literature_integrity import load_cases  # noqa: E402


PUBLIC_FIELDS = {
    "schema_version", "capability", "case_id", "prompt", "domain",
    "fixture_paths", "quality_rubric_id",
}
PRIVATE_MARKERS = {
    "attack_family", "expected_status", "expected_reason_codes",
    "reason_expectations", "gold", "scorer_path", "scorecard_path",
}


def _walk(value):
  if isinstance(value, dict):
    for key, nested in value.items():
      yield str(key)
      yield from _walk(nested)
  elif isinstance(value, (list, tuple, set)):
    for nested in value:
      yield from _walk(nested)
  elif isinstance(value, pathlib.PurePath):
    yield str(value)
  elif isinstance(value, str):
    yield value
  elif is_dataclass(value):
    for definition in fields(value):
      yield from _walk(getattr(value, definition.name))


def _temp_tree(root: pathlib.Path) -> tuple[tuple[str, bytes], ...]:
  return tuple(
      (path.relative_to(root).as_posix(), path.read_bytes())
      for path in sorted(root.rglob("*")) if path.is_file())


def test_public_cases_and_fixtures_do_not_serialize_scorer_material():
  for case_path in ATTACKS.glob("*/case.json"):
    public = json.loads(case_path.read_text())
    assert set(public) - {"workspace_tamper"} == PUBLIC_FIELDS
    assert case_path.parent.name == public["case_id"]
    assert public["case_id"].startswith("integrity-case-")
    assert public["fixture_paths"] == ["input.json"]
    serialized = "\n".join(_walk(public)).casefold()
    assert not any(marker in serialized for marker in PRIVATE_MARKERS)
    for relative in public["fixture_paths"]:
      fixture = case_path.parent / relative
      serialized_fixture = fixture.read_text(encoding="utf-8").casefold()
      assert not any(marker in serialized_fixture for marker in PRIVATE_MARKERS)


def test_fixture_loader_rejects_symlinks_even_when_target_stays_inside_case(
    tmp_path,
):
  case_dir = tmp_path / "linked"
  case_dir.mkdir()
  target = case_dir / "target.json"
  target.write_text("{}")
  (case_dir / "scenario.json").symlink_to(target)
  (case_dir / "case.json").write_text(json.dumps({
      "schema_version": "1.0.0",
      "capability": "literature-review-integrity",
      "case_id": "linked",
      "prompt": "Create an invented review.",
      "domain": "invented",
      "fixture_paths": ["scenario.json"],
      "quality_rubric_id": "literature-review-v1",
  }))

  with pytest.raises(ValueError, match="symlink"):
    load_cases(case_dir)


def test_case_loading_keeps_public_fixtures_in_memory_without_temp_mirrors(
    monkeypatch, tmp_path,
):
  safe_temp = tmp_path / "safe-temp"
  safe_temp.mkdir()
  monkeypatch.setattr(literature_integrity, "_SAFE_TEMP_ROOT", safe_temp)
  case_dir = tmp_path / "collection" / "case-one"
  case_dir.mkdir(parents=True)
  (case_dir / "input.txt").write_bytes(b"neutral public fixture\n")
  (case_dir / "case.json").write_text(json.dumps({
      "schema_version": "1.0.0",
      "capability": "literature-review-integrity",
      "case_id": "case-one",
      "prompt": "Create an invented review.",
      "domain": "invented",
      "fixture_paths": ["input.txt"],
      "quality_rubric_id": "literature-review-v1",
  }))
  (case_dir / "expected.json").write_text(json.dumps({
      "schema_version": "1.0.0",
      "final_status": "invalid",
      "minimum_repair_rounds": 0,
      "maximum_repair_rounds": 3,
      "attack_family": "never-write-this-family",
      "reason_expectations": [],
  }))

  case, = load_cases(tmp_path / "collection")

  assert case.fixture_files[0].relative_path == pathlib.PurePosixPath(
      "input.txt")
  assert case.fixture_files[0].content == b"neutral public fixture\n"
  assert _temp_tree(safe_temp) == ()
  assert not any(str(tmp_path) in value for value in _walk(case))


def test_public_fixture_record_rejects_scorer_owned_names():
  with pytest.raises(ValueError, match="harness|scorer|expected"):
    literature_integrity.PublicFixture(
        pathlib.PurePosixPath("expected.json"), b"private scorer bytes")


def test_malformed_case_cannot_leave_a_scorer_mirror_after_interruption(
    monkeypatch, tmp_path,
):
  safe_temp = tmp_path / "safe-temp"
  safe_temp.mkdir()
  monkeypatch.setattr(literature_integrity, "_SAFE_TEMP_ROOT", safe_temp)
  case_dir = tmp_path / "collection" / "case-one"
  case_dir.mkdir(parents=True)
  (case_dir / "case.json").write_text("{")
  (case_dir / "expected.json").write_text(
      '{"attack_family":"crash-visible-family"}')

  with pytest.raises(ValueError, match="case definition"):
    load_cases(tmp_path / "collection")

  assert _temp_tree(safe_temp) == ()


def test_collection_file_reads_are_bounded(tmp_path):
  case_dir = tmp_path / "collection" / "case-one"
  case_dir.mkdir(parents=True)
  (case_dir / "case.json").write_text(json.dumps({
      "schema_version": "1.0.0",
      "capability": "literature-review-integrity",
      "case_id": "case-one",
      "prompt": "x" * (8 * 1024 * 1024),
      "domain": "invented",
      "fixture_paths": [],
      "quality_rubric_id": "literature-review-v1",
  }))

  with pytest.raises(ValueError, match="size|large|limit"):
    load_cases(tmp_path / "collection")


def test_fixture_loader_rejects_symlinked_case_collection(tmp_path):
  target = tmp_path / "target"
  case_dir = target / "case-one"
  case_dir.mkdir(parents=True)
  (case_dir / "case.json").write_text(json.dumps({
      "schema_version": "1.0.0",
      "capability": "literature-review-integrity",
      "case_id": "case-one",
      "prompt": "Create an invented review.",
      "domain": "invented",
      "fixture_paths": [],
      "quality_rubric_id": "literature-review-v1",
  }))
  linked = tmp_path / "linked"
  linked.symlink_to(target, target_is_directory=True)

  with pytest.raises(ValueError, match="symlink"):
    load_cases(linked)


def test_case_discovery_rejects_symlinked_absolute_ancestor(tmp_path):
  real_parent = tmp_path / "real-parent"
  case_dir = real_parent / "collection" / "case-one"
  case_dir.mkdir(parents=True)
  (case_dir / "case.json").write_text(json.dumps({
      "schema_version": "1.0.0",
      "capability": "literature-review-integrity",
      "case_id": "case-one",
      "prompt": "Create an invented review.",
      "domain": "invented",
      "fixture_paths": [],
      "quality_rubric_id": "literature-review-v1",
  }))
  linked_parent = tmp_path / "linked-parent"
  linked_parent.symlink_to(real_parent, target_is_directory=True)

  with pytest.raises(ValueError, match="ancestor|symlink"):
    load_cases(linked_parent / "collection")


def test_case_discovery_fails_closed_when_collection_path_is_swapped(
    monkeypatch, tmp_path,
):
  collection = tmp_path / "collection"
  collection.mkdir()
  outside = tmp_path / "outside"
  case_dir = outside / "case-one"
  case_dir.mkdir(parents=True)
  (case_dir / "case.json").write_text(json.dumps({
      "schema_version": "1.0.0",
      "capability": "literature-review-integrity",
      "case_id": "case-one",
      "prompt": "Create an invented review.",
      "domain": "invented",
      "fixture_paths": [],
      "quality_rubric_id": "literature-review-v1",
  }))
  original_open = literature_integrity.os.open
  swapped = False

  def swap_before_open(path, flags, *args, **kwargs):
    nonlocal swapped
    if (not swapped and path == collection.name
        and kwargs.get("dir_fd") is not None):
      swapped = True
      collection.rename(tmp_path / "displaced")
      collection.symlink_to(outside, target_is_directory=True)
    return original_open(path, flags, *args, **kwargs)

  monkeypatch.setattr(literature_integrity.os, "open", swap_before_open)

  with pytest.raises(ValueError, match="swap|identity|symlink"):
    load_cases(collection)


def test_case_discovery_rejects_nested_directory_symlink(tmp_path):
  outside = tmp_path / "outside"
  outside.mkdir()
  collection = tmp_path / "collection"
  collection.mkdir()
  (collection / "linked").symlink_to(outside, target_is_directory=True)

  with pytest.raises(ValueError, match="symlink"):
    load_cases(collection)


def test_case_discovery_rejects_case_file_symlink_to_outside(tmp_path):
  outside = tmp_path / "outside-case.json"
  outside.write_text("{}")
  collection = tmp_path / "collection"
  case_dir = collection / "integrity-case-001"
  case_dir.mkdir(parents=True)
  (case_dir / "case.json").symlink_to(outside)

  with pytest.raises(ValueError, match="symlink"):
    load_cases(collection)


def test_case_discovery_rejects_hardlink_aliases(tmp_path):
  collection = tmp_path / "collection"
  first = collection / "integrity-case-001"
  second = collection / "integrity-case-002"
  first.mkdir(parents=True)
  second.mkdir(parents=True)
  payload = first / "case.json"
  payload.write_text("{}")
  (second / "case.json").hardlink_to(payload)

  with pytest.raises(ValueError, match="alias|hard|duplicate"):
    load_cases(collection)


@pytest.mark.parametrize("relative", ["../outside.json", "/tmp/outside.json"])
def test_fixture_loader_rejects_traversal_before_reading(tmp_path, relative):
  case_dir = tmp_path / "traversal"
  case_dir.mkdir()
  (case_dir / "case.json").write_text(json.dumps({
      "schema_version": "1.0.0",
      "capability": "literature-review-integrity",
      "case_id": "traversal",
      "prompt": "Create an invented review.",
      "domain": "invented",
      "fixture_paths": [relative],
      "quality_rubric_id": "literature-review-v1",
  }))

  with pytest.raises(ValueError, match="inside|relative|traversal"):
    load_cases(case_dir)


def test_recursive_repair_feedback_cannot_reach_scorer_values():
  feedback = {
      "reason_codes": ["fabricated_quote"],
      "affected_artifacts": ["claims.json"],
      "findings": [{
          "reason_code": "fabricated_quote", "artifact": "claims.json",
          "context": {"nested": [{"safe": "public validator detail"}]},
      }],
  }
  serialized = "\n".join(_walk(feedback)).casefold()

  assert not any(marker in serialized for marker in PRIVATE_MARKERS)
  assert "unicode-substitution" not in serialized
  assert "expected.json" not in serialized


def test_production_adapter_has_no_builtin_case_collection_or_mapping_path():
  source = pathlib.Path(literature_integrity.__file__).read_text()
  forbidden = (
      "synthetic-attacks", "official-cases", "private-cases",
      "gold-mapping", "gold_mapping",
  )

  assert not any(value in source.casefold() for value in forbidden)
