"""L5 (embedded) — In-process local model via llama.cpp (GGUF). NO Ollama required.

This is the DEFAULT M4 backend so end users don't install or run a separate daemon:
it embeds a small instruct model *inside* the Exodus process using llama-cpp-python.
The weights (a single GGUF) download once from the Hugging Face Hub and cache locally;
after that it's fully offline and on-device.

Optional dependency — activate with:  pip install -e ".[local]"
If llama-cpp-python is absent (or the download fails), ``available()`` returns False
and the M4 layer is SKIPPED — the deterministic firewall (regex + validators) still
protects. Same duck-typed interface as ``OllamaRuntime``: available() + generate().
"""
from __future__ import annotations

import logging
import os

_log = logging.getLogger("exodus.embedded")

# Small + multilingual by default ("para todo el mundo"): Qwen2.5-1.5B-Instruct (~1 GB q4).
_DEFAULT_REPO = "Qwen/Qwen2.5-1.5B-Instruct-GGUF"
_DEFAULT_FILE = "*q4_k_m.gguf"


class LlamaCppRuntime:
    def __init__(
        self,
        repo_id: str | None = None,
        filename: str | None = None,
        model_path: str | None = None,
        n_ctx: int = 4096,
    ):
        self.repo_id = repo_id or os.getenv("EXODUS_EMBED_REPO", _DEFAULT_REPO)
        self.filename = filename or os.getenv("EXODUS_EMBED_FILE", _DEFAULT_FILE)
        self.model_path = model_path or os.getenv("EXODUS_EMBED_MODEL_PATH") or None
        self.n_ctx = n_ctx
        self._llm = None  # lazy: not loaded until first available()/generate()

    def _ensure_loaded(self):
        if self._llm is not None:
            return self._llm
        from llama_cpp import Llama  # optional dep; ImportError handled by available()

        if self.model_path:
            _log.warning("🧠 Cargando modelo embebido desde %s …", self.model_path)
            self._llm = Llama(model_path=self.model_path, n_ctx=self.n_ctx, verbose=False)
        else:
            _log.warning(
                "🧠 Preparando modelo local embebido (%s) — la primera vez se descarga UNA vez, "
                "luego es 100%% offline en tu máquina…",
                self.repo_id,
            )
            self._llm = Llama.from_pretrained(
                repo_id=self.repo_id, filename=self.filename, n_ctx=self.n_ctx, verbose=False
            )
        return self._llm

    def available(self) -> bool:
        """True only once the embedded model is actually loaded.

        Returning False (not raising) when the optional dep or the download is missing
        means the M4 layer is SKIPPED rather than INV-4-blocked.
        """
        try:
            import llama_cpp  # noqa: F401
        except Exception:
            return False
        try:
            self._ensure_loaded()
            return True
        except Exception:
            _log.warning("Modelo embebido no disponible (descarga/carga falló) — M4 se omite.")
            return False

    def generate(self, system: str, prompt: str) -> str:
        """Single-shot, deterministic (temperature 0) in-process generation."""
        llm = self._ensure_loaded()
        out = llm.create_chat_completion(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
        )
        return out["choices"][0]["message"]["content"].strip()
