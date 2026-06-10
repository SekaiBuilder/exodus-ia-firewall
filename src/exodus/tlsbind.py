"""TLS channel binding for attestation (RA-TLS style).

A self-signed certificate is enough here because trust does not come from a CA:
the certificate's sha256 fingerprint is folded into the attestation
``report_data`` (see ``exodus.attest``), so a verified quote proves the TLS
session terminates inside the attested enclave — a CA could not prove that.
"""
from __future__ import annotations

import hashlib
import os
import ssl
import subprocess

_CERT_DIR = os.path.join(os.path.expanduser("~"), ".exodus", "tls")


def ensure_cert(certfile: str | None, keyfile: str | None, host: str) -> tuple[str, str]:
    """Return (certfile, keyfile), generating a self-signed pair if none given."""
    if certfile and keyfile:
        return certfile, keyfile
    if certfile or keyfile:
        raise SystemExit("provide both --certfile and --keyfile, or neither")

    os.makedirs(_CERT_DIR, exist_ok=True)
    cert = os.path.join(_CERT_DIR, "exodus.crt")
    key = os.path.join(_CERT_DIR, "exodus.key")
    if not (os.path.exists(cert) and os.path.exists(key)):
        subprocess.run(
            [
                "openssl", "req", "-x509", "-newkey", "ec",
                "-pkeyopt", "ec_paramgen_curve:prime256v1",
                "-keyout", key, "-out", cert,
                "-days", "30", "-nodes",
                "-subj", "/CN=exodus",
                "-addext", f"subjectAltName=DNS:localhost,IP:{host}",
            ],
            check=True,
            capture_output=True,
        )
        os.chmod(key, 0o600)
    return cert, key


def fingerprint(certfile: str) -> str:
    """sha256 fingerprint (hex) of the certificate in DER form."""
    with open(certfile) as fh:
        der = ssl.PEM_cert_to_DER_cert(fh.read())
    return hashlib.sha256(der).hexdigest()


def remote_fingerprint(host: str, port: int) -> str:
    """Fetch a server's certificate and return its sha256 fingerprint (hex)."""
    pem = ssl.get_server_certificate((host, port))
    return hashlib.sha256(ssl.PEM_cert_to_DER_cert(pem)).hexdigest()
