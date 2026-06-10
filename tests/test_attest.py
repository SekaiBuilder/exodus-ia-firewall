"""Attestation endpoint tests.

Outside real SGX hardware the endpoint must return the simulated document
(no quote) with the same schema as the DCAP flow, and the report_data must
commit to the caller's nonce so verifiers can check freshness.
"""
import hashlib

from fastapi.testclient import TestClient

from exodus import attest
from exodus.proxy.server import create_app


def test_attest_requires_nonce():
    with TestClient(create_app()) as client:
        assert client.get("/_exodus/attest").status_code == 400
        assert client.get("/_exodus/attest", params={"nonce": "short"}).status_code == 400


def test_attest_binds_nonce_into_report_data():
    nonce = "a3f9c2e188d04b7e"
    with TestClient(create_app()) as client:
        r = client.get("/_exodus/attest", params={"nonce": nonce})
    assert r.status_code == 200
    doc = r.json()
    assert doc["nonce"] == nonce
    expected = hashlib.sha256(nonce.encode()).digest().ljust(64, b"\0").hex()
    assert doc["report_data"] == expected


def test_attest_simulated_outside_sgx():
    with TestClient(create_app()) as client:
        doc = client.get("/_exodus/attest", params={"nonce": "0123456789abcdef"}).json()
    # CI and dev machines have no /dev/attestation with DCAP.
    assert doc["simulated"] is True
    assert doc["tee"] in {"gramine-direct", "host"}
    assert "quote_b64" not in doc


def test_report_data_is_64_bytes():
    doc = attest.build_report("0123456789abcdef")
    assert len(bytes.fromhex(doc["report_data"])) == 64
