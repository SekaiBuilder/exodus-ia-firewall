"""Reversible pseudonymization + local vault + stream-safe restoration.

Sensitive values are replaced by stable, unique placeholder tokens wrapped in
U+27EA / U+27EB sentinels (⟪ … ⟫): rare in code, easy to detect, chosen to survive
SSE chunking. The vault (placeholder <-> real) never leaves the machine and is
restored on the response path. For the agentic edit loop, restoration is byte-exact.
"""
from __future__ import annotations

import codecs
from dataclasses import dataclass, field

_OPEN = "⟪"
_CLOSE = "⟫"


@dataclass
class Vault:
    """In-memory, per-request map. Never serialized to the wire or to logs."""

    _fwd: dict[str, str] = field(default_factory=dict)  # real -> placeholder
    _rev: dict[str, str] = field(default_factory=dict)  # placeholder -> real

    def placeholder_for(self, real: str, kind: str) -> str:
        if real in self._fwd:
            return self._fwd[real]
        token = f"{_OPEN}EXODUS:{kind}:{len(self._fwd) + 1}{_CLOSE}"
        self._fwd[real] = token
        self._rev[token] = real
        return token

    def restore(self, text: str) -> str:
        """Replace every known complete placeholder with its real value."""
        for token, real in self._rev.items():
            text = text.replace(token, real)
        return text

    def __len__(self) -> int:
        return len(self._fwd)


def resolve_overlaps(detections):
    """Keep a non-overlapping subset of detections (earliest start, longest wins)."""
    ordered = sorted(detections, key=lambda d: (d.start, -(d.end - d.start)))
    chosen = []
    last_end = -1
    for d in ordered:
        if d.start >= last_end:
            chosen.append(d)
            last_end = d.end
    return chosen


def apply_replacements(text: str, replacements: list[tuple[int, int, str]]) -> str:
    """Apply (start, end, new_text) edits. Assumes non-overlapping spans.

    Done right-to-left so that each edit does not shift the offsets of the ones
    still to be applied (which are all further left).
    """
    for start, end, new in sorted(replacements, key=lambda r: r[0], reverse=True):
        text = text[:start] + new + text[end:]
    return text


def pseudonymize(text: str, detections, vault: Vault) -> str:
    """Convenience: reversibly pseudonymize every detection (overlaps resolved)."""
    chosen = resolve_overlaps(detections)
    repls = [(d.start, d.end, vault.placeholder_for(text[d.start : d.end], d.kind)) for d in chosen]
    return apply_replacements(text, repls)


class StreamRestorer:
    """Restores placeholders over a byte stream, safe across chunk boundaries.

    Handles two boundary hazards at once:
      * split multibyte UTF-8 characters (via an incremental decoder), and
      * placeholder tokens split between two chunks (by holding back any trailing
        unclosed ``⟪…`` until its ``⟫`` arrives).
    """

    def __init__(self, vault: Vault) -> None:
        self.vault = vault
        self._decoder = codecs.getincrementaldecoder("utf-8")()
        self._buf = ""

    def feed(self, data: bytes) -> bytes:
        self._buf += self._decoder.decode(data)
        self._buf = self.vault.restore(self._buf)

        # If a (possibly partial) placeholder is dangling at the end, hold it back.
        idx = self._buf.rfind(_OPEN)
        if idx != -1 and _CLOSE not in self._buf[idx:]:
            out, self._buf = self._buf[:idx], self._buf[idx:]
        else:
            out, self._buf = self._buf, ""
        return out.encode("utf-8")

    def flush(self) -> bytes:
        self._buf += self._decoder.decode(b"", final=True)
        out = self.vault.restore(self._buf)
        self._buf = ""
        return out.encode("utf-8")
