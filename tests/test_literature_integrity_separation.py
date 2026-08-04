import json
import pathlib
import sys

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
  elif isinstance(value, pathlib.Path):
    yield str(value)
  elif isinstance(value, str):
    yield value


def test_public_cases_and_fixtures_do_not_serialize_scorer_material():
  for case_path in ATTACKS.glob("*/case.json"):
    public = json.loads(case_path.read_text())
    assert set(public) == PUBLIC_FIELDS
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
