"""Contextual minimization pass (M4) — the OPTIONAL local-model layer.

Sits on top of the deterministic secret firewall. For a piece of prose it asks the
local model "how sensitive is this?" and, if it crosses a threshold, rewrites it to
a less-identifying form. The deterministic firewall (M2/M3) still handles secrets;
this layer handles *contextual* sensitivity that regex cannot see.

INV-4 (fail-closed): once we ENGAGE the local model and it fails mid-flight, we
BLOCK the content rather than forward it raw. If the model is simply unavailable
from the start, the layer is skipped (the deterministic firewall still applies).
"""
from __future__ import annotations

from exodus.classify.sensitivity import Sensitivity, classify_text
from exodus.transform.abstract import abstract

BLOCK_MARK = "[EXODUS-BLOCKED:local-model-failure]"


def minimize_text(text: str, runtime, min_tier: Sensitivity = Sensitivity.MEDIUM) -> tuple[str, str]:
    """Return ``(new_text, status)``.

    status is one of:
      skipped:model-unavailable | forwarded:<tier> | abstracted:<tier> |
      blocked:empty-abstraction | blocked:inv4
    """
    if not runtime.available():
        return text, "skipped:model-unavailable"
    try:
        tier = classify_text(text, runtime)
        if tier < min_tier:
            return text, f"forwarded:{tier.name.lower()}"
        rewritten = abstract(text, runtime)
        if not rewritten:
            return BLOCK_MARK, "blocked:empty-abstraction"
        return rewritten, f"abstracted:{tier.name.lower()}"
    except Exception:
        # INV-4: we committed to local handling and it failed -> never forward raw.
        return BLOCK_MARK, "blocked:inv4"
