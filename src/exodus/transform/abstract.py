"""Local abstraction / minimization.

Uses the local model to rewrite a sensitive span into a less-identifying but still
useful form. LOSSY and honest: the abstracted facts STILL leave the machine — this
reduces exposure, it does not eliminate it (see docs/threat-model.md §5).
"""
from __future__ import annotations

ABSTRACT_SYSTEM_PROMPT = (
    "You rewrite text to strip ALL personally identifying or sensitive specifics "
    "while keeping only the general, non-identifying meaning needed to understand "
    "the situation.\n"
    "ALWAYS remove or generalize: personal names, ages, exact dates, postal "
    "addresses, phone numbers, emails, and ANY identification / record / account / "
    "medical-record numbers (even standalone digit strings).\n"
    "Do NOT keep a detail just because you are unsure — when in doubt, remove it.\n"
    "Output ONLY the rewritten text, nothing else.\n"
    "\n"
    "Example:\n"
    'Input:  "Patient John Smith, 47, record #55231, 12 Oak St, Madrid, has asthma."\n'
    'Output: "A patient has asthma."'
)


def abstract(text: str, runtime) -> str:
    """Return a privacy-minimized rewrite of ``text`` via the local model.

    ``runtime`` is anything with ``generate(system, prompt) -> str``. Raises if the
    runtime errors (the caller fails closed — see ``transform.local_pass``).
    """
    return runtime.generate(ABSTRACT_SYSTEM_PROMPT, text).strip()
