"""Transport and privacy-pipeline integration for the proxy.

The reverse proxy forwards each client request upstream. Before egress it
pseudonymizes secrets (and restores them on the response), applies the configurable
policy engine (``EXODUS_POLICY_FILE``), and writes an audit trail. An optional
local-model pass (``EXODUS_LOCAL_MODEL=on``) abstracts sensitive free text first.

An optional inspection log (``EXODUS_INSPECT=on``) records full plaintext of both
sides of your own exchange for debugging; see ``exodus.inspectlog`` (off by default,
git-ignored, holds secrets in clear).
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from collections import Counter
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse

from exodus import attest, inspectlog
from exodus.audit import log as audit
from exodus.policy.policy import Policy
from exodus.transform.pipeline import contextual_pass, sanitize_request_body
from exodus.transform.pseudonymize import StreamRestorer

from .anthropic_client import RESPONSE_DROP_HEADERS, Upstream

_PROXY_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
_TRUE = {"1", "true", "on", "yes"}
_log = logging.getLogger("exodus.firewall")


def _load_policy() -> Policy:
    path = os.getenv("EXODUS_POLICY_FILE")
    if path and os.path.exists(path):
        _log.info("Exodus policy loaded from %s", path)
        return Policy.from_yaml(path)
    return Policy.default()


def _load_runtime():
    if os.getenv("EXODUS_LOCAL_MODEL", "").lower() not in _TRUE:
        return None
    backend = os.getenv("EXODUS_LOCAL_BACKEND", "embedded").lower()
    if backend == "ollama":
        from exodus.local_model.runtime import OllamaRuntime

        rt = OllamaRuntime()
        hint = f"run `ollama list` and set OLLAMA_MODEL (looking for '{rt.model}' @ {rt.host})"
    else:  # "embedded" (default): in-process llama.cpp, NO Ollama required
        from exodus.local_model.embedded import LlamaCppRuntime

        rt = LlamaCppRuntime()
        hint = 'install the embedded model with: pip install -e ".[local]"'
    if not rt.available():
        _log.warning(
            "EXODUS_LOCAL_MODEL is on but the '%s' backend is unavailable; the local "
            "pass will be skipped (the deterministic firewall still protects). %s",
            backend,
            hint,
        )
    return rt


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.upstream = Upstream()
        app.state.policy = _load_policy()
        app.state.local_runtime = _load_runtime()
        app.state.inspect = os.getenv("EXODUS_INSPECT", "").lower() in _TRUE
        if app.state.inspect:
            _log.warning(
                "EXODUS_INSPECT is on: full plaintext (incl. secrets) is being written "
                "to %s. Debugging/verification only, on your own traffic. Delete it when done.",
                inspectlog.inspect_path(),
            )
        app.state.no_restore = os.getenv("EXODUS_NO_RESTORE", "").lower() in _TRUE
        # Set by `exodus serve --tls`: sha256 fingerprint of the serving certificate,
        # folded into attestation report_data so the TLS channel is bound to the enclave.
        app.state.tls_fingerprint = os.getenv("EXODUS_TLS_FINGERPRINT") or None
        if app.state.no_restore:
            _log.warning(
                "EXODUS_NO_RESTORE is on: responses are not un-masked; the client will see "
                "the placeholders the cloud actually received. Turn off for normal use."
            )
        try:
            yield
        finally:
            await app.state.upstream.aclose()

    app = FastAPI(title="Exodus", version="0.0.1", lifespan=lifespan)

    @app.get("/_exodus/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/_exodus/attest")
    async def attest_report(request: Request, nonce: str = "") -> dict:
        if not (8 <= len(nonce) <= 128):
            raise HTTPException(
                status_code=400, detail="nonce must be 8-128 characters (use a fresh random value)"
            )
        return attest.build_report(nonce, request.app.state.tls_fingerprint)

    @app.api_route("/{path:path}", methods=_PROXY_METHODS)
    async def proxy(path: str, request: Request) -> StreamingResponse:
        upstream: Upstream = request.app.state.upstream
        policy: Policy = request.app.state.policy
        runtime = request.app.state.local_runtime
        do_inspect: bool = request.app.state.inspect
        no_restore: bool = request.app.state.no_restore
        rid = uuid.uuid4().hex[:12]

        original_body = await request.body()
        body = original_body

        # Optional local-model pass: abstract sensitive free-text prose.
        if runtime is not None:
            body, statuses = await asyncio.to_thread(contextual_pass, body, runtime)
            if any(not s.startswith("forwarded") for s in statuses):
                _log.warning("local pass: %s", dict(Counter(statuses)))

        # Deterministic policy firewall (reversible), applied before egress.
        sanitized, vault, applied = sanitize_request_body(body, policy)
        if applied:
            summary = dict(Counter(f"{kind}:{action}" for kind, action in applied))
            _log.warning("masked %d item(s) before upstream: %s", len(applied), summary)
            audit.write(audit.AuditRecord.now(rid, kind, action) for kind, action in applied)

        up_req = upstream.build_request(
            request.method, "/" + path, dict(request.headers), sanitized, dict(request.query_params)
        )
        up_resp = await upstream.send(up_req)

        resp_headers = {
            k: v
            for k, v in up_resp.headers.items()
            if k.lower() not in RESPONSE_DROP_HEADERS and k.lower() != "content-type"
        }

        restorer = None if no_restore else StreamRestorer(vault)
        captured = bytearray() if do_inspect else None

        async def body_iter():
            try:
                async for chunk in up_resp.aiter_bytes():  # decoded (decompressed)
                    # Proof mode: forward the upstream bytes untouched so the client
                    # sees the placeholders the cloud actually received.
                    out = chunk if restorer is None else restorer.feed(chunk)
                    if out:
                        if captured is not None:
                            captured.extend(out)
                        yield out
                if restorer is not None:
                    tail = restorer.flush()
                    if tail:
                        if captured is not None:
                            captured.extend(tail)
                        yield tail
                if do_inspect:
                    try:
                        inspectlog.record(rid, original_body, sanitized, bytes(captured or b""))
                    except Exception:
                        _log.warning("inspect log write failed")
            finally:
                await up_resp.aclose()

        return StreamingResponse(
            body_iter(),
            status_code=up_resp.status_code,
            headers=resp_headers,
            media_type=up_resp.headers.get("content-type"),
        )

    return app


# Convenience target for `uvicorn exodus.proxy.server:app`. No network at import time.
app = create_app()
