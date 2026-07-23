import dataclasses
import json
import pathlib

import pytest

from claim_verifier_benchmark.coverage_units import (
    CoverageEnumerationError,
    enumerate_coverage_units,
)


FIXTURES = pathlib.Path(__file__).parents[1] / "fixtures" / "coverage"
COMPOUND_SURNAMES = (
    ("García Márquez", "author:garcía márquez:2022"),
    ("Lloyd Webber", "author:lloyd webber:2022"),
    ("Sánchez Vicario", "author:sánchez vicario:2022"),
    ("王 小明", "author:王 小明:2022"),
)


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


def test_parenthetical_international_author_labels_have_exact_identities():
  synthesis = (
      "Results held (van den Berg, 2021; al-Hassan, 2022; 王, 2023)."
  )
  units = enumerate_coverage_units(synthesis)
  assert [unit.citation_identity for unit in units] == [
      "author:al hassan:2022",
      "author:van den berg:2021",
      "author:王:2023",
  ]
  assert all(synthesis[unit.start:unit.end] == synthesis for unit in units)


def test_narrative_international_author_labels_do_not_truncate_particles():
  synthesis = (
      "van den Berg (2021) reported change. "
      "al-Hassan (2022) replicated it. "
      "王 (2023) confirmed it."
  )
  units = enumerate_coverage_units(synthesis)
  assert [unit.citation_identity for unit in units] == [
      "author:van den berg:2021",
      "author:al hassan:2022",
      "author:王:2023",
  ]
  assert [unit.sentence for unit in units] == [
      "van den Berg (2021) reported change.",
      "al-Hassan (2022) replicated it.",
      "王 (2023) confirmed it.",
  ]
  assert all(
      synthesis[unit.start:unit.end] == unit.sentence
      for unit in units
  )


@pytest.mark.parametrize(("author", "identity"), COMPOUND_SURNAMES)
def test_compound_narrative_and_parenthetical_authors_have_the_same_identity(
    author, identity,
):
  narrative = enumerate_coverage_units(
      f"{author} (2022) reported change."
  )
  parenthetical = enumerate_coverage_units(
      f"Results changed ({author}, 2022)."
  )
  assert [unit.citation_identity for unit in narrative] == [identity]
  assert [unit.citation_identity for unit in parenthetical] == [identity]


@pytest.mark.parametrize(("author", "identity"), COMPOUND_SURNAMES)
def test_compound_narrative_and_parenthetical_renderings_deduplicate(
    author, identity,
):
  synthesis = (
      f"{author} (2022) agreed with prior results ({author}, 2022)."
  )
  units = enumerate_coverage_units(synthesis)
  assert [unit.citation_identity for unit in units] == [identity]
  assert synthesis[units[0].start:units[0].end] == units[0].sentence


@pytest.mark.parametrize(
    ("author", "identity"),
    [
        (
            "García Márquez et al.",
            "author:garcía márquez et al:2022",
        ),
        (
            "García Márquez and Lloyd Webber",
            "author:garcía márquez and lloyd webber:2022",
        ),
    ],
)
def test_compound_narrative_authors_retain_registered_group_forms(
    author, identity,
):
  units = enumerate_coverage_units(f"{author} (2022) reported change.")
  assert [unit.citation_identity for unit in units] == [identity]


@pytest.mark.parametrize(
    ("synthesis", "identity"),
    [
        (
            "Results from García (2022) were stable.",
            "author:garcía:2022",
        ),
        (
            "Results from García Márquez (2022) were stable.",
            "author:garcía márquez:2022",
        ),
    ],
)
def test_narrative_author_excludes_preceding_prose(synthesis, identity):
  units = enumerate_coverage_units(synthesis)
  assert [unit.citation_identity for unit in units] == [identity]
  assert synthesis[units[0].start:units[0].end] == units[0].sentence


@pytest.mark.parametrize(
    "synthesis",
    [
        "Results held (Garci\u0301a, 2022).",
        "Garci\u0301a (2022) reported change.",
    ],
)
def test_decomposed_unicode_authors_normalize_identity_and_preserve_offsets(
    synthesis,
):
  units = enumerate_coverage_units(synthesis)
  assert [unit.citation_identity for unit in units] == [
      "author:garcía:2022"
  ]
  assert synthesis[units[0].start:units[0].end] == units[0].sentence


@pytest.mark.parametrize(
    "author",
    ["Smith ৴", "Ⅳ", "Smith_", "smith"],
)
def test_malformed_nonletter_author_tokens_are_rejected_without_exception(
    author,
):
  units = enumerate_coverage_units(f"Results held ({author}, 2022).")
  assert units == ()


def test_narrative_nonletter_numeric_symbol_is_rejected_before_normalization():
  units = enumerate_coverage_units("Ⅳ (2022) reported change.")
  assert units == ()


def test_numeric_range_allows_the_registered_maximum_span():
  units = enumerate_coverage_units("Results cite [1-101].")
  assert len(units) == 101
  assert {unit.citation_identity for unit in units} == {
      f"number:{number}" for number in range(1, 102)
  }


@pytest.mark.parametrize("citation", ["[4-3]", "[1-102]"])
def test_invalid_matched_numeric_ranges_fail_closed(citation):
  with pytest.raises(CoverageEnumerationError, match="numeric citation range"):
    enumerate_coverage_units(f"Results cite {citation}.")


@pytest.mark.parametrize(
    "name", ["mixed-citations.json", "repeated-sentence.json"])
def test_inventory_fixtures_are_exact(name):
  fixture = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
  observed = [
      dataclasses.asdict(unit)
      for unit in enumerate_coverage_units(fixture["synthesis"])
  ]
  assert observed == fixture["units"]
