from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel, SecretStr

from glean import llm
from glean.llm import Feature, LLMRouter


class _Reply(BaseModel):
    answer: str


class _RecordingChatModel:
    """Stands in for the OpenRouter chat model: records how it was asked to respond."""

    def __init__(self) -> None:
        self.structured_calls: list[tuple[type[BaseModel], dict[str, Any]]] = []
        self.free_text_calls = 0

    def with_structured_output(self, schema: type[BaseModel], **kwargs: Any) -> _RecordingChatModel._Structured:
        self.structured_calls.append((schema, kwargs))
        return self._Structured(schema)

    def invoke(self, *_: Any, **__: Any) -> str:
        self.free_text_calls += 1
        return "free text"

    class _Structured:
        def __init__(self, schema: type[BaseModel]) -> None:
            self.schema = schema

        def invoke(self, *_: Any, **__: Any) -> BaseModel:
            return self.schema.model_validate({"answer": "ok"})


@pytest.fixture
def chat_model(monkeypatch: pytest.MonkeyPatch) -> _RecordingChatModel:
    model = _RecordingChatModel()
    monkeypatch.setattr(llm, "create_chat_model", lambda *_, **__: model)
    return model


@pytest.mark.parametrize("feature", list(Feature), ids=lambda feature: feature.value)
def test_every_feature_is_invoked_through_json_schema_structured_output(
    feature: Feature, chat_model: _RecordingChatModel
) -> None:
    router = LLMRouter(api_key=SecretStr("test-key"))

    reply = router.invoke(feature, _Reply, ["message"])

    assert reply == _Reply(answer="ok")
    assert chat_model.structured_calls == [(_Reply, {"method": "json_schema"})]
    assert chat_model.free_text_calls == 0

