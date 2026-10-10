import json
import pathlib

import pytest

from claim_verifier_benchmark.split import (
    Paper,
    SplitError,
    assign_split,
    derive_split_key,
    paper_order_key,
)

FIXTURE = pathlib.Path(__file__).parents[1] / "fixtures" / "split-vector.json"


def test_normative_split_vector():
  vector = json.loads(FIXTURE.read_text(encoding="utf-8"))
  split_key = derive_split_key(
      vector["output_value"], vector["construction_archive_sha256"])
  assert split_key.hex() == vector["expected_split_key"]
  papers = [Paper(stable_id=value, domain=vector["domain"])
            for value in vector["paper_ids"]]
  ordered = sorted(
      papers,
      key=lambda paper: (
          paper_order_key(split_key, paper),
          paper.stable_id.encode("utf-8"),
      ),
  )
  assert [paper.stable_id for paper in ordered] == vector["expected_order"]


@pytest.mark.parametrize("output_value", ["00", "GG" * 64, "0" * 127])
def test_split_rejects_malformed_beacon(output_value):
  with pytest.raises(SplitError):
    derive_split_key(output_value, "00" * 32)


def test_split_requires_lowercase_archive_digest():
  with pytest.raises(SplitError):
    derive_split_key("00" * 64, "AA" * 32)


def test_assign_split_requires_five_unique_papers_per_domain():
  split_key = bytes.fromhex("11" * 32)
  with pytest.raises(SplitError):
    assign_split(split_key, [Paper("p1", "medicine")])
