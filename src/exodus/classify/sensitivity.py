"""L2 — Sensitivity classification per span.

Combines deterministic detections, contextual signals (local model), and user
policy hints into a single sensitivity label per span. Does NOT mutate content.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class Sensitivity(IntEnum):
    PUBLIC = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    SECRET = 4


@dataclass
class Span:
    text: str
    start: int
    end: int
    kind: str = "text"
    sensitivity: Sensitivity = Sensitivity.PUBLIC
    source: str = "unclassified"  # "regex" | "presidio" | "model" | "policy"


_CLASSIFY_SYSTEM = (
    "You are a privacy sensitivity classifier. Read the user's text and output "
    "EXACTLY ONE word — its sensitivity tier:\n"
    "PUBLIC = no personal/sensitive info (generic code, general questions).\n"
    "LOW = a mild identifier alone (a name or an email).\n"
    "MEDIUM = personal or proprietary details that should be minimized before sharing.\n"
    "HIGH = highly sensitive (medical, financial, credentials, identity documents, "
    "trade secrets).\n"
    "Reply with ONLY one of: PUBLIC, LOW, MEDIUM, HIGH. No explanation."
)


def _parse_tier(out: str) -> Sensitivity:
    """Find the tier word in the model output. Fail-closed to HIGH if none found."""
    upper = out.upper()
    for name in ("HIGH", "MEDIUM", "LOW", "PUBLIC"):
        if name in upper:
            return Sensitivity[name]
    return Sensitivity.HIGH  # unparseable -> treat as most sensitive (fail-closed)


def classify_text(text: str, runtime) -> Sensitivity:
    """Classify ``text`` into a sensitivity tier using the local model.

    ``runtime`` is anything with ``generate(system, prompt) -> str`` (see
    ``exodus.local_model.runtime.OllamaRuntime``). Raises if the runtime errors —
    the caller decides the fail-closed behavior (see ``transform.local_pass``).
    """
    return _parse_tier(runtime.generate(_CLASSIFY_SYSTEM, text))
