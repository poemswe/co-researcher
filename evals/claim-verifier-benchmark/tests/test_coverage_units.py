import dataclasses
import json
import pathlib

import pytest

from claim_verifier_benchmark.coverage_units import enumerate_coverage_units


FIXTURES = pathlib.Path(__file__).parents[1] / "fixtures" / "coverage"


def test_inventory_is_complete_ordered_and_unicode_aware():
  synthesis = (
      "Admissions fell (García, 2022; Müller, 2020). "
      "Costs fell [2-3]."
  )
  units = enumerate_coverage_units(synthesis)
  assert [unit.citation_identity for unit in units] == [
      "author:garcía:2022",
      "author:müller:2020",
      "number:2",
      "number:3",
  ]
  for unit in units:
    assert synthesis[unit.start:unit.end] == unit.sentence


def test_duplicate_identity_in_one_sentence_forms_one_unit():
  units = enumerate_coverage_units(
      "Admissions fell (García, 2022) and remained low (García, 2022).")
  assert len(units) == 1


def test_repeated_sentence_gets_full_inventory_occurrence_ordinals():
  sentence = "Admissions fell (García, 2022)."
  units = enumerate_coverage_units(f"{sentence} {sentence}")
  assert [unit.occurrence_ordinal for unit in units] == [1, 2]
  assert [unit.sentence_ordinal for unit in units] == [0, 1]


def test_abbreviations_do_not_create_false_sentence_boundaries():
  units = enumerate_coverage_units(
      "García et al. (2022) found a reduction. Costs were unchanged.")
  assert len(units) == 1
  assert units[0].sentence == "García et al. (2022) found a reduction."


@pytest.mark.parametrize(
    "name", ["mixed-citations.json", "repeated-sentence.json"])
def test_inventory_fixtures_are_exact(name):
  fixture = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
  observed = [
      dataclasses.asdict(unit)
      for unit in enumerate_coverage_units(fixture["synthesis"])
  ]
  assert observed == fixture["units"]
