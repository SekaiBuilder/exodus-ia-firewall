"""M4 — local-model layer tests (classifier + abstractor + INV-4 + proxy wiring).

A FakeRuntime stands in for Ollama: it returns the tier word for classify calls and
a canned rewrite for abstract calls (routed by a keyword in the system prompt).
No network.
"""
import json

import httpx
import respx
from fastapi.testclient import TestClient

from exodus.classify.sensitivity import Sensitivity, classify_text
from exodus.transform.abstract import abstract
from exodus.transform.local_pass import BLOCK_MARK, minimize_text
from exodus.transform.pipeline import contextual_pass


class FakeRuntime:
    def __init__(self, tier="PUBLIC", abstraction="[minimized]", available=True, raises=False):
        self.tier = tier
        self.abstraction = abstraction
        self._available = available
        self._raises = raises

    def available(self) -> bool:
        return self._available

    def generate(self, system: str, prompt: str) -> str:
        if self._raises:
            raise RuntimeError("ollama down")
        return self.tier if "classif" in system.lower() else self.abstraction


# ---- classifier ----
def test_classify_parses_label_anywhere():
    assert classify_text("x", FakeRuntime(tier="The tier is HIGH.")) == Sensitivity.HIGH
    assert classify_text("x", FakeRuntime(tier="public")) == Sensitivity.PUBLIC


def test_classify_fails_closed_on_garbage():
    assert classify_text("x", FakeRuntime(tier="banana split")) == Sensitivity.HIGH


# ---- abstractor ----
def test_abstract_returns_model_rewrite():
    out = abstract("Juan, 54, diabetes", FakeRuntime(abstraction="adult with a chronic condition"))
    assert out == "adult with a chronic condition"


# ---- minimize_text (classify + abstract + INV-4) ----
def test_minimize_forwards_low_sensitivity():
    out, status = minimize_text("just some generic code", FakeRuntime(tier="PUBLIC"))
    assert out == "just some generic code"
    assert status.startswith("forwarded")


def test_minimize_abstracts_high_sensitivity():
    out, status = minimize_text(
        "Patient Juan, 54, diabetes, Calle Falsa 123",
        FakeRuntime(tier="HIGH", abstraction="adult patient with a chronic condition"),
    )
    assert out == "adult patient with a chronic condition"
    assert status == "abstracted:high"


def test_inv4_blocks_when_model_fails():
    out, status = minimize_text("sensitive thing", FakeRuntime(available=True, raises=True))
    assert out == BLOCK_MARK
    assert status == "blocked:inv4"


def test_layer_skipped_when_model_unavailable():
    out, status = minimize_text("anything", FakeRuntime(available=False))
    assert out == "anything"
    assert status == "skipped:model-unavailable"


# ---- contextual_pass over a request body ----
def test_contextual_pass_abstracts_user_text():
    body = json.dumps(
        {"model": "m", "messages": [{"role": "user", "content": "Patient Juan, 54, diabetes"}]}
    ).encode()
    new, statuses = contextual_pass(body, FakeRuntime(tier="HIGH", abstraction="a patient with a condition"))
    s = new.decode()
    assert "Juan" not in s
    assert "a patient with a condition" in s
    assert any(st.startswith("abstracted") for st in statuses)


def test_contextual_pass_leaves_public_text_unchanged():
    body = json.dumps({"model": "m", "messages": [{"role": "user", "content": "refactor this loop"}]}).encode()
    new, statuses = contextual_pass(body, FakeRuntime(tier="PUBLIC"))
    assert new == body
    assert statuses == ["forwarded:public"]


# ---- proxy wiring (M4 part 2) ----
@respx.mock
def test_proxy_applies_contextual_pass(monkeypatch):
    from exodus.proxy import server

    monkeypatch.setattr(
        server, "_load_runtime", lambda: FakeRuntime(tier="HIGH", abstraction="adult with a condition")
    )
    route = respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    with TestClient(server.create_app()) as client:
        client.post(
            "/v1/messages",
            json={"model": "m", "messages": [{"role": "user", "content": "Patient Juan, 54, diabetes"}]},
        )
    sent = route.calls.last.request.content.decode("utf-8")
    assert "adult with a condition" in sent
    assert "Juan" not in sent


# ---- runtime availability checks the MODEL, not just the server (graceful degrade) ----
@respx.mock
def test_runtime_unavailable_when_model_missing():
    from exodus.local_model.runtime import OllamaRuntime

    respx.get("http://127.0.0.1:11434/api/tags").mock(
        return_value=httpx.Response(200, json={"models": [{"name": "other-model:1b"}]})
    )
    assert OllamaRuntime(model="qwen2.5-coder:7b").available() is False


@respx.mock
def test_runtime_available_when_model_present():
    from exodus.local_model.runtime import OllamaRuntime

    respx.get("http://127.0.0.1:11434/api/tags").mock(
        return_value=httpx.Response(200, json={"models": [{"name": "qwen2.5-coder:7b"}, {"name": "x:1b"}]})
    )
    assert OllamaRuntime(model="qwen2.5-coder:7b").available() is True
