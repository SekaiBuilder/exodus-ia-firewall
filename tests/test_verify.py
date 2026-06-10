"""Verifier tests.

These exercise the relying-party side: nonce binding, replay rejection,
quote parsing, MRENCLAVE pinning, and the simulated-mode policy.
"""
import base64

from exodus import attest
from exodus.verify import expected_report_data, parse_quote, verify_document

NONCE = "a3f9c2e188d04b7e"


def _synthetic_quote(nonce: str, mr_enclave: bytes = b"\x11" * 32) -> bytes:
    """Build a structurally valid DCAP quote committing to ``nonce``."""
    body = bytearray(384)
    body[64:96] = mr_enclave
    body[128:160] = b"\x22" * 32
    body[320:384] = expected_report_data(nonce)
    return bytes(48) + bytes(body)


def _hardware_doc(nonce: str, quote: bytes) -> dict:
    return {
        "nonce": nonce,
        "report_data": expected_report_data(nonce).hex(),
        "tee": "sgx-dcap",
        "simulated": False,
        "quote_b64": base64.b64encode(quote).decode(),
    }


def test_simulated_rejected_by_default():
    doc = attest.build_report(NONCE)
    v = verify_document(doc, NONCE)
    assert v.trusted is False


def test_simulated_accepted_with_flag():
    doc = attest.build_report(NONCE)
    v = verify_document(doc, NONCE, allow_simulated=True)
    assert v.trusted is True


def test_replayed_nonce_rejected():
    doc = attest.build_report(NONCE)
    v = verify_document(doc, "ffffffffffffffff", allow_simulated=True)
    assert v.trusted is False
    assert any("nonce" in f for f in v.failures)


def test_hardware_quote_binds_nonce():
    v = verify_document(_hardware_doc(NONCE, _synthetic_quote(NONCE)), NONCE)
    assert v.trusted is True
    assert v.mr_enclave == "11" * 32


def test_quote_with_wrong_nonce_rejected():
    v = verify_document(_hardware_doc(NONCE, _synthetic_quote("other-nonce-here")), NONCE)
    assert v.trusted is False
    assert any("quote report_data" in f for f in v.failures)


def test_mrenclave_pinning():
    doc = _hardware_doc(NONCE, _synthetic_quote(NONCE))
    assert verify_document(doc, NONCE, expected_mrenclave="11" * 32).trusted is True
    bad = verify_document(doc, NONCE, expected_mrenclave="aa" * 32)
    assert bad.trusted is False
    assert any("MRENCLAVE mismatch" in f for f in bad.failures)


def test_truncated_quote_rejected():
    doc = _hardware_doc(NONCE, b"\x00" * 100)
    v = verify_document(doc, NONCE)
    assert v.trusted is False
    assert any("unparseable" in f for f in v.failures)


def test_parse_quote_offsets():
    parsed = parse_quote(_synthetic_quote(NONCE))
    assert parsed["mr_signer"] == "22" * 32
    assert parsed["report_data"] == expected_report_data(NONCE)


def test_channel_binding_required_when_observed():
    # Verifier saw a TLS cert, but the document does not bind any.
    doc = attest.build_report(NONCE)
    v = verify_document(doc, NONCE, allow_simulated=True, channel_binding="ab" * 32)
    assert v.trusted is False
    assert any("TLS" in f for f in v.failures)


def test_channel_binding_accepted_when_matching():
    fp = "ab" * 32
    doc = attest.build_report(NONCE, channel_binding=fp)
    v = verify_document(doc, NONCE, allow_simulated=True, channel_binding=fp)
    assert v.trusted is True
    assert doc["channel_binding"] == fp


def test_channel_binding_mismatch_rejected():
    doc = attest.build_report(NONCE, channel_binding="ab" * 32)
    v = verify_document(doc, NONCE, allow_simulated=True, channel_binding="cd" * 32)
    assert v.trusted is False
