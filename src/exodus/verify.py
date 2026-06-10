"""Attestation verifier — the client side of ``/_exodus/attest``.

A relying party (another agent, an MCP client, a human) calls ``verify`` with a
fresh random nonce; the proxy answers with an attestation document and this
module checks it:

1. the document echoes our nonce (freshness — no replayed quotes);
2. ``report_data`` commits to sha256(nonce);
3. if a hardware quote is present, the same commitment appears inside the
   quote's report body, and MRENCLAVE/MRSIGNER are extracted so the caller can
   pin them to a known-good Exodus build.

Full DCAP signature-chain validation (Intel QVL / PCCS) is intentionally out of
scope here: this verifier establishes structure and nonce binding, and surfaces
the measurements needed for that final step.
"""
from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass, field

# SGX quote layout: 48-byte header followed by the 384-byte report body.
_QUOTE_HEADER_SIZE = 48
_REPORT_BODY_SIZE = 384
# Offsets inside the report body (sgx_report_body_t).
_MR_ENCLAVE_OFFSET = 64
_MR_SIGNER_OFFSET = 128
_REPORT_DATA_OFFSET = 320
_REPORT_DATA_SIZE = 64


@dataclass
class Verdict:
    trusted: bool
    tee: str
    checks: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    mr_enclave: str | None = None
    mr_signer: str | None = None


def fresh_nonce() -> str:
    return secrets.token_hex(16)


def expected_report_data(nonce: str, channel_binding: str | None = None) -> bytes:
    payload = nonce if channel_binding is None else f"{nonce}|{channel_binding}"
    return hashlib.sha256(payload.encode("utf-8")).digest().ljust(_REPORT_DATA_SIZE, b"\0")


def parse_quote(quote: bytes) -> dict:
    """Extract measurements and report_data from a raw SGX DCAP quote."""
    if len(quote) < _QUOTE_HEADER_SIZE + _REPORT_BODY_SIZE:
        raise ValueError(f"quote too short: {len(quote)} bytes")
    body = quote[_QUOTE_HEADER_SIZE : _QUOTE_HEADER_SIZE + _REPORT_BODY_SIZE]
    return {
        "mr_enclave": body[_MR_ENCLAVE_OFFSET : _MR_ENCLAVE_OFFSET + 32].hex(),
        "mr_signer": body[_MR_SIGNER_OFFSET : _MR_SIGNER_OFFSET + 32].hex(),
        "report_data": body[_REPORT_DATA_OFFSET : _REPORT_DATA_OFFSET + _REPORT_DATA_SIZE],
    }


def verify_document(
    doc: dict,
    nonce: str,
    expected_mrenclave: str | None = None,
    allow_simulated: bool = False,
    channel_binding: str | None = None,
) -> Verdict:
    """Check an attestation document against the nonce we sent.

    ``channel_binding`` is the sha256 fingerprint of the TLS certificate *we*
    observed on the connection; requiring it inside report_data rules out a
    man-in-the-middle terminating TLS outside the enclave.
    """
    v = Verdict(trusted=False, tee=str(doc.get("tee", "unknown")))

    if doc.get("nonce") != nonce:
        v.failures.append("nonce mismatch — possible replayed document")
    else:
        v.checks.append("nonce echoed correctly")

    if channel_binding is not None:
        if doc.get("channel_binding") != channel_binding:
            v.failures.append("attestation does not bind the TLS certificate we are talking to")
        else:
            v.checks.append("TLS certificate fingerprint bound into attestation")

    want = expected_report_data(nonce, channel_binding)
    if doc.get("report_data") != want.hex():
        v.failures.append("report_data does not commit to our nonce")
    else:
        label = "sha256(nonce|tls-cert)" if channel_binding else "sha256(nonce)"
        v.checks.append(f"report_data == {label}")

    if doc.get("simulated", True):
        v.checks.append("document is SIMULATED — no hardware guarantee")
        v.trusted = allow_simulated and not v.failures
        return v

    quote_b64 = doc.get("quote_b64")
    if not quote_b64:
        v.failures.append("non-simulated document without a quote")
        return v
    try:
        parsed = parse_quote(base64.b64decode(quote_b64))
    except (ValueError, TypeError) as exc:
        v.failures.append(f"quote unparseable: {exc}")
        return v

    v.mr_enclave = parsed["mr_enclave"]
    v.mr_signer = parsed["mr_signer"]
    if parsed["report_data"] != want:
        v.failures.append("quote report_data does not match our nonce commitment")
    else:
        v.checks.append("hardware quote binds our nonce")

    if expected_mrenclave is not None:
        if v.mr_enclave == expected_mrenclave.lower():
            v.checks.append("MRENCLAVE matches pinned build")
        else:
            v.failures.append(
                f"MRENCLAVE mismatch: got {v.mr_enclave}, expected {expected_mrenclave.lower()}"
            )

    v.trusted = not v.failures
    return v


def verify_url(
    base_url: str,
    expected_mrenclave: str | None = None,
    allow_simulated: bool = False,
) -> Verdict:
    """Fetch ``/_exodus/attest`` from a running proxy and verify the answer.

    Over HTTPS the server certificate's fingerprint is captured first and must
    appear inside the attestation (RA-TLS): certificate validation is replaced
    by attestation binding, which a CA cannot provide.
    """
    from urllib.parse import urlsplit

    import httpx

    binding = None
    parts = urlsplit(base_url)
    if parts.scheme == "https":
        from exodus.tlsbind import remote_fingerprint

        binding = remote_fingerprint(parts.hostname or "127.0.0.1", parts.port or 443)

    nonce = fresh_nonce()
    r = httpx.get(
        f"{base_url.rstrip('/')}/_exodus/attest",
        params={"nonce": nonce},
        timeout=10,
        verify=parts.scheme != "https",  # trust comes from the binding, not a CA
    )
    r.raise_for_status()
    return verify_document(r.json(), nonce, expected_mrenclave, allow_simulated, binding)
