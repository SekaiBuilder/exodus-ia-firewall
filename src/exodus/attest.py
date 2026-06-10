"""Remote attestation report for the proxy.

When Exodus runs inside a Gramine SGX enclave, this module produces a hardware
quote over the caller's nonce: proof that the exact Exodus build is executing
inside a genuine enclave, so the vault is unreadable even to the host operator.

Gramine exposes attestation through pseudo-files under ``/dev/attestation``:
writing 64 bytes to ``user_report_data`` binds them into the quote read back
from ``quote``. Outside real SGX (gramine-direct, plain host) the same JSON
schema is returned with ``simulated: true`` so verifier clients can be built
and tested before SGX hardware is available.
"""
from __future__ import annotations

import base64
import hashlib
import os

_ATTESTATION_DIR = "/dev/attestation"
_TYPE_PATH = os.path.join(_ATTESTATION_DIR, "attestation_type")
_REPORT_DATA_PATH = os.path.join(_ATTESTATION_DIR, "user_report_data")
_QUOTE_PATH = os.path.join(_ATTESTATION_DIR, "quote")

# user_report_data is a fixed 64-byte field inside the SGX report.
_REPORT_DATA_SIZE = 64


def attestation_type() -> str:
    """Return the Gramine attestation backend: ``dcap``, ``none``, or ``unavailable``."""
    try:
        with open(_TYPE_PATH, "rb") as fh:
            return fh.read().decode("ascii").strip() or "none"
    except OSError:
        return "unavailable"


def _report_data_for(nonce: str) -> bytes:
    """Derive the 64-byte report payload binding the caller's nonce."""
    digest = hashlib.sha256(nonce.encode("utf-8")).digest()
    return digest.ljust(_REPORT_DATA_SIZE, b"\0")


def build_report(nonce: str) -> dict:
    """Produce the attestation document for ``nonce``.

    Inside SGX (Gramine with DCAP) the returned ``quote_b64`` is a hardware
    quote whose report_data commits to sha256(nonce); anywhere else the
    document is explicitly marked ``simulated`` and carries no quote.
    """
    kind = attestation_type()
    report_data = _report_data_for(nonce)
    doc = {
        "nonce": nonce,
        "report_data": report_data.hex(),
        "attestation_type": kind,
    }

    if kind == "dcap":
        with open(_REPORT_DATA_PATH, "wb") as fh:
            fh.write(report_data)
        with open(_QUOTE_PATH, "rb") as fh:
            quote = fh.read()
        doc["tee"] = "sgx-dcap"
        doc["simulated"] = False
        doc["quote_b64"] = base64.b64encode(quote).decode("ascii")
    else:
        doc["tee"] = "gramine-direct" if kind == "none" else "host"
        doc["simulated"] = True
        doc["note"] = (
            "No SGX hardware quote available in this environment; schema matches "
            "the real flow so verifiers can be developed against it."
        )
    return doc
