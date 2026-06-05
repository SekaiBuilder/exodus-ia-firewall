"""The self-test matrix is also a regression test: every kind, end to end."""
from exodus.classify import detectors
from exodus.selftest import SAMPLES, check


def test_matrix_covers_every_detector():
    """If a detector is added without a sample, this fails (keeps proof complete)."""
    sampled = {kind for kind, _ in SAMPLES}
    defined = set(detectors.SECRET_PATTERNS) | set(detectors.PII_PATTERNS)
    assert sampled == defined, f"matrix out of sync: {sampled ^ defined}"


def test_every_kind_is_detected():
    for r in check():
        assert r.detected, f"{r.kind} sample was not detected"


def test_no_protected_value_leaks_to_egress():
    for r in check():
        if r.action != "forward":
            assert not r.leaked, f"{r.kind} value leaked into the egress body"
            assert r.masked, f"{r.kind} was not masked"


def test_masked_kinds_restore_exactly():
    for r in check():
        if r.masked:
            assert r.roundtrip_ok, f"{r.kind} did not round-trip to the original bytes"


def test_selftest_exit_code_is_pass():
    from exodus.selftest import main

    assert main() == 0
