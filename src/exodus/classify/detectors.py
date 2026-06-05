"""L1 — Deterministic detection (regex + hard validators).

High-precision, CPU-only detectors for secrets and structured PII. Detection ONLY:
no routing decisions, no content mutation.

Free-text / contextual sensitivity (names, locations, sensitive prose) is NOT regex
work — that belongs to the local-model layer (L2 / M4). Anything here is a string
with a recognizable *signature* or one that passes a *structural check*.

Kinds listed in ``VALIDATORS`` (credit card → Luhn, IBAN → mod-97, DNI/NIE → check
letter, SSN → range rules) only fire when the candidate validates, so the numeric
patterns don't trip on ordinary digit strings.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Detection:
    start: int
    end: int
    kind: str       # e.g. "anthropic_key", "credit_card", "iban", "es_dni"
    detector: str   # "regex" | "presidio"


# --- Secrets: provider/token signatures. Low false-positive by construction. ---
SECRET_PATTERNS: dict[str, re.Pattern] = {
    # LLM / AI providers
    "anthropic_key": re.compile(r"sk-ant-[A-Za-z0-9\-_]{20,}"),
    "openai_key": re.compile(r"sk-[A-Za-z0-9]{20,}"),
    "openai_project_key": re.compile(r"sk-proj-[A-Za-z0-9\-_]{20,}"),
    # Cloud providers
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "google_api_key": re.compile(r"AIza[0-9A-Za-z\-_]{35}"),
    "google_oauth_token": re.compile(r"ya29\.[0-9A-Za-z\-_]{20,}"),
    # Source control
    "github_token": re.compile(r"ghp_[A-Za-z0-9]{36}"),
    "github_oauth": re.compile(r"gh[ousr]_[A-Za-z0-9]{36,}"),
    "github_pat": re.compile(r"github_pat_[0-9A-Za-z_]{82}"),
    # SaaS
    "slack_token": re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}"),
    "slack_webhook": re.compile(r"https://hooks\.slack\.com/services/[A-Za-z0-9/_+\-]+"),
    "stripe_key": re.compile(r"(?:sk|rk)_(?:live|test)_[0-9A-Za-z]{24,}"),
    "sendgrid_key": re.compile(r"SG\.[A-Za-z0-9_\-]{22}\.[A-Za-z0-9_\-]{43}"),
    "npm_token": re.compile(r"npm_[0-9A-Za-z]{36}"),
    # Generic / structural
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),
    "private_key_block": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"),
    "generic_bearer": re.compile(r"(?i)bearer\s+[A-Za-z0-9\-_.=]{16,}"),
    "db_uri_credentials": re.compile(
        r"(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp)://[^:@\s/]+:[^@\s/]+@[^\s/]+"
    ),
}

# --- Structured PII. Validated kinds (see VALIDATORS) only fire on a real match. ---
PII_PATTERNS: dict[str, re.Pattern] = {
    "email": re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"),
    "ipv4": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]?){12,18}\d\b"),
    "iban": re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]){11,30}\b"),
    "es_dni": re.compile(r"\b\d{8}-?[A-Za-z]\b"),
    "es_nie": re.compile(r"\b[XYZxyz]-?\d{7}-?[A-Za-z]\b"),
    "us_ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "phone_intl": re.compile(r"(?<!\w)\+\d[\d .\-]{6,16}\d\b"),
}

# Kind groupings: secrets (never safe to leak) vs. PII (handled by policy tiers).
SECRET_KINDS: frozenset[str] = frozenset(SECRET_PATTERNS)
PII_KINDS: frozenset[str] = frozenset(PII_PATTERNS)


# --- Hard validators: keep the noisy numeric patterns honest (near-zero FP). ---
_DNI_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"


def _luhn_ok(s: str) -> bool:
    digits = [int(c) for c in s if c.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    total, parity = 0, len(digits) % 2
    for i, d in enumerate(digits):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _iban_ok(s: str) -> bool:
    s = re.sub(r"\s", "", s).upper()
    if not 15 <= len(s) <= 34:
        return False
    rearranged = s[4:] + s[:4]
    try:
        return int("".join(str(int(c, 36)) for c in rearranged)) % 97 == 1
    except ValueError:
        return False


def _dni_ok(s: str) -> bool:
    s = s.upper().replace("-", "")
    return len(s) == 9 and s[:8].isdigit() and _DNI_LETTERS[int(s[:8]) % 23] == s[8]


def _nie_ok(s: str) -> bool:
    s = s.upper().replace("-", "")
    if len(s) != 9 or s[0] not in "XYZ":
        return False
    num = {"X": "0", "Y": "1", "Z": "2"}[s[0]] + s[1:8]
    return num.isdigit() and _DNI_LETTERS[int(num) % 23] == s[8]


def _ssn_ok(s: str) -> bool:
    area, group, serial = s.split("-")
    return area not in ("000", "666") and area[0] != "9" and group != "00" and serial != "0000"


def _phone_ok(s: str) -> bool:
    return 8 <= sum(ch.isdigit() for ch in s) <= 15


VALIDATORS: dict[str, Callable[[str], bool]] = {
    "credit_card": _luhn_ok,
    "iban": _iban_ok,
    "es_dni": _dni_ok,
    "es_nie": _nie_ok,
    "us_ssn": _ssn_ok,
    "phone_intl": _phone_ok,
}


def scan(text: str) -> list[Detection]:
    """Return deterministic detections found in ``text``.

    A kind in ``VALIDATORS`` only yields a Detection when its candidate passes the
    structural check, so numeric patterns don't fire on ordinary digit strings.
    Overlap resolution happens downstream (transform layer), not here.
    """
    found: list[Detection] = []
    for kind, pattern in {**SECRET_PATTERNS, **PII_PATTERNS}.items():
        validator = VALIDATORS.get(kind)
        for m in pattern.finditer(text):
            if validator is not None and not validator(m.group()):
                continue
            found.append(Detection(m.start(), m.end(), kind, "regex"))
    return found
