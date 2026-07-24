from claim_verifier_benchmark.constants import (
    DOMAINS,
    PROTOCOL_CORE_VERSION,
    REASON_CODES,
    RESULT_STATUSES,
    TARGET_COMMIT,
)


def test_frozen_protocol_constants():
    assert DOMAINS == (
        "medicine",
        "social-science",
        "climate-environment",
        "machine-learning",
    )
    assert TARGET_COMMIT == "e72a4d6"
    assert PROTOCOL_CORE_VERSION == "1.0.0"
    assert len(RESULT_STATUSES) == 9
    assert len(REASON_CODES) == 11
    assert len(set(RESULT_STATUSES)) == len(RESULT_STATUSES)
    assert len(set(REASON_CODES)) == len(REASON_CODES)
