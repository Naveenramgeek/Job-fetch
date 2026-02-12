import json

import pytest

import app.services.titan_embedding as titan


class _Body:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload)


class _Client:
    def __init__(self, payload):
        self.payload = payload

    def invoke_model(self, **kwargs):
        return {"body": _Body(self.payload)}


def test_embed_text_titan_parses_embedding(monkeypatch):
    titan._bedrock_runtime_client.cache_clear()
    monkeypatch.setattr(titan, "_bedrock_runtime_client", lambda: _Client({"embedding": [1, 2, 3]}))
    out = titan.embed_text_titan("hello")
    assert out == [1.0, 2.0, 3.0]


def test_embed_text_titan_parses_embeddings_fallback(monkeypatch):
    titan._bedrock_runtime_client.cache_clear()
    monkeypatch.setattr(titan, "_bedrock_runtime_client", lambda: _Client({"embeddings": [[0.1, 0.2]]}))
    out = titan.embed_text_titan("hello")
    assert out == [0.1, 0.2]


def test_embed_text_titan_raises_when_shape_invalid(monkeypatch):
    titan._bedrock_runtime_client.cache_clear()
    monkeypatch.setattr(titan, "_bedrock_runtime_client", lambda: _Client({"x": 1}))
    with pytest.raises(RuntimeError):
        titan.embed_text_titan("hello")


def test_cosine_similarity_edge_cases():
    assert titan.cosine_similarity([], [1.0]) == 0.0
    assert titan.cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert titan.cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == -1.0
