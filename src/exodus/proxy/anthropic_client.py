"""Upstream forwarder to api.anthropic.com.

The only component allowed to open a connection past the trust boundary. It holds a
shared ``httpx.AsyncClient`` and forwards requests upstream in streaming mode so that
Server-Sent Events (SSE) are relayed chunk-by-chunk without buffering.

This is a *transparent* forwarder: it does not inspect or mutate bodies. The privacy
pipeline is layered on top elsewhere; this module stays simple on purpose.
"""
from __future__ import annotations

import os

import httpx

# Headers that are connection-specific and must not be relayed verbatim.
REQUEST_DROP_HEADERS: frozenset[str] = frozenset({
    "host", "content-length", "connection", "keep-alive",
    "proxy-authenticate", "proxy-authorization", "te", "trailers",
    "transfer-encoding", "upgrade",
})
RESPONSE_DROP_HEADERS: frozenset[str] = frozenset({
    # content-encoding is dropped because we stream the decoded body (aiter_bytes)
    # to restore placeholders, then re-emit it decompressed.
    "content-length", "content-encoding", "transfer-encoding", "connection",
    "keep-alive", "te", "trailers", "upgrade", "proxy-authenticate", "proxy-authorization",
})


def upstream_base_url() -> str:
    """Provider-neutral upstream. Anthropic by default, but point Exodus at ANY API
    with ``EXODUS_UPSTREAM`` (e.g. ``https://api.openai.com`` for Codex). One Exodus
    instance = one upstream; run a second instance on another port for a second provider.
    """
    return (
        os.getenv("EXODUS_UPSTREAM")
        or os.getenv("ANTHROPIC_UPSTREAM_BASE_URL")  # backwards-compatible alias
        or "https://api.anthropic.com"
    ).rstrip("/")


def _filter(headers: dict[str, str], drop: frozenset[str]) -> dict[str, str]:
    return {k: v for k, v in headers.items() if k.lower() not in drop}


class Upstream:
    """A long-lived client that forwards (method, path, headers, body) upstream."""

    def __init__(self, base_url: str | None = None, timeout: float = 600.0) -> None:
        self.base_url = (base_url or upstream_base_url()).rstrip("/")
        self._client = httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    def build_request(
        self, method: str, path: str, headers: dict[str, str], content: bytes, params
    ) -> httpx.Request:
        url = f"{self.base_url}{path}"
        return self._client.build_request(
            method, url, headers=_filter(headers, REQUEST_DROP_HEADERS), content=content, params=params
        )

    async def send(self, request: httpx.Request) -> httpx.Response:
        """Send in streaming mode. Caller must ``aclose()`` the returned response."""
        return await self._client.send(request, stream=True)
