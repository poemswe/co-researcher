import pytest

from claim_verifier_benchmark.commitment import (
    CommitmentError,
    mapping_commitment,
    opaque_id,
    review_order,
    verify_mapping_commitment,
)


def test_opaque_ids_are_stable_unique_and_domain_separated():
    secret = bytes(range(32))
    claim = opaque_id(secret, "claim", "case-1:entry-1")
    coverage = opaque_id(secret, "coverage", "case-1:entry-1")
    assert claim == opaque_id(secret, "claim", "case-1:entry-1")
    assert claim != coverage
    assert claim.startswith("claim_")


def test_review_order_is_stable_and_seeded():
    values = ("u1", "u2", "u3", "u4")
    assert review_order(values, b"a" * 32) == review_order(values, b"a" * 32)
    assert review_order(values, b"a" * 32) != review_order(values, b"b" * 32)


def test_mapping_commitment_fails_closed_on_mapping_or_salt_change():
    mapping = {"review_1": "case-1"}
    salt = bytes(range(32))
    expected = mapping_commitment(mapping, salt)
    assert verify_mapping_commitment(mapping, salt, expected)
    assert not verify_mapping_commitment({"review_1": "case-2"}, salt, expected)
    assert not verify_mapping_commitment(mapping, b"x" * 32, expected)


@pytest.mark.parametrize("salt", [b"", b"x" * 31, b"x" * 33])
def test_mapping_commitment_requires_32_byte_salt(salt):
    with pytest.raises(CommitmentError):
        mapping_commitment({}, salt)


@pytest.mark.parametrize(
    "malformed",
    [
        lambda expected: expected.upper(),
        lambda expected: expected[:-1],
        lambda expected: expected + "0",
        lambda expected: "g" + expected[1:],
        lambda expected: "０" + expected[1:],
        lambda expected: expected.encode("ascii"),
        lambda expected: None,
        lambda expected: 0,
    ],
)
def test_mapping_verification_requires_exact_lowercase_ascii_digest(malformed):
    mapping = {"review_1": "case-1"}
    salt = bytes(range(32))
    expected = mapping_commitment(mapping, salt)
    assert not verify_mapping_commitment(mapping, salt, malformed(expected))


@pytest.mark.parametrize(
    ("mapping", "salt"),
    [
        ({"review_1": object()}, bytes(range(32))),
        (["not", "a", "mapping"], bytes(range(32))),
        ({"review_1": "case-1"}, None),
        ({"review_1": "case-1"}, "x" * 32),
        ({"review_1": "case-1"}, bytearray(32)),
    ],
)
def test_mapping_verification_returns_false_for_invalid_mapping_or_salt(
    mapping, salt,
):
    expected = mapping_commitment(
        {"review_1": "case-1"}, bytes(range(32))
    )
    assert not verify_mapping_commitment(mapping, salt, expected)
