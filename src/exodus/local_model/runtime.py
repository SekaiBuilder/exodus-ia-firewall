"""L5 — Local model runtime. Ollama now; MLX later.

Pure local inference used for contextual sensitivity classification and
abstraction. Knows nothing about HTTP/proxy concerns. On the target machine
(MacBook Air M5, 32 GB) a 7B instruct model runs comfortably.
"""
from __future__ import annotations

import os

import httpx


class OllamaRuntime:
    def __init__(self, host: str | None = None, model: str | None = None, timeout: float = 120.0):
        self.host = (host or os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")).rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL", "qwen2.5:3b-instruct")
        self.timeout = timeout

    def available(self) -> bool:
        """True only if the Ollama server answers AND the configured model is pulled.

        Checking the MODEL (not just the server) matters: if the model is missing,
        we report unavailable so the M4 layer is SKIPPED (the deterministic firewall
        still protects), instead of every generate() failing and INV-4 blocking ALL
        content. INV-4 is reserved for genuine mid-flight failures, not misconfig.
        """
        try:
            r = httpx.get(f"{self.host}/api/tags", timeout=2.0)
            if r.status_code != 200:
                return False
            models = [m.get("name", "") for m in r.json().get("models", [])]
            return self.model in models
        except Exception:
            return False

    def generate(self, system: str, prompt: str) -> str:
        """Single-shot, deterministic (temperature 0) local generation."""
        r = httpx.post(
            f"{self.host}/api/generate",
            json={
                "model": self.model,
                "system": system,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0},
            },
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json().get("response", "").strip()


# TODO(V2): MLXRuntime — Apple-native acceleration for the M-series GPU.
