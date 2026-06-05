"""Embedded local-model backend (llama.cpp) + backend selection.

These run WITHOUT llama-cpp-python installed (we force its absence): the runtime must
degrade to 'unavailable' so the M4 layer is SKIPPED, never crash the proxy. The
deterministic firewall does not depend on any of this.
"""
import sys

from exodus.local_model.embedded import LlamaCppRuntime
from exodus.local_model.runtime import OllamaRuntime
from exodus.proxy.server import _load_runtime


def test_embedded_unavailable_without_dep(monkeypatch):
    # Force `import llama_cpp` to fail -> available() must be False, never raise/download.
    monkeypatch.setitem(sys.modules, "llama_cpp", None)
    assert LlamaCppRuntime().available() is False


def test_generate_parses_chat_completion():
    # With a fake loaded model, generate() extracts and strips the message content.
    rt = LlamaCppRuntime()

    class _FakeLlama:
        def create_chat_completion(self, messages, temperature):
            assert temperature == 0.0 and messages[0]["role"] == "system"
            return {"choices": [{"message": {"content": "  abstracted text  "}}]}

    rt._llm = _FakeLlama()
    assert rt.generate("sys", "hello") == "abstracted text"


def test_load_runtime_defaults_to_embedded(monkeypatch):
    monkeypatch.setitem(sys.modules, "llama_cpp", None)  # no download during the test
    monkeypatch.setenv("EXODUS_LOCAL_MODEL", "on")
    monkeypatch.delenv("EXODUS_LOCAL_BACKEND", raising=False)
    assert isinstance(_load_runtime(), LlamaCppRuntime)


def test_load_runtime_ollama_when_selected(monkeypatch):
    monkeypatch.setenv("EXODUS_LOCAL_MODEL", "on")
    monkeypatch.setenv("EXODUS_LOCAL_BACKEND", "ollama")
    assert isinstance(_load_runtime(), OllamaRuntime)


def test_load_runtime_off_by_default(monkeypatch):
    monkeypatch.delenv("EXODUS_LOCAL_MODEL", raising=False)
    assert _load_runtime() is None
