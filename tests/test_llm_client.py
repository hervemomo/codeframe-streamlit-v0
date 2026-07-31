"""Retry, parameter compatibility, extraction, and usage tests."""

from types import SimpleNamespace
from typing import Any

import pytest

from codeframe.config import ModelConfig
from codeframe.exceptions import ExternalServiceError
from codeframe.llm_client import (
    assistant_content,
    chat_with_retry,
    completion_kwargs,
    make_text_completion,
)
from codeframe.usage import UsageTracker


class FakeCompletions:
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = outcomes
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class ApiError(Exception):
    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


def response(content: str = "ok") -> object:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=2, completion_tokens=3, total_tokens=5),
    )


@pytest.mark.unit
def test_completion_kwargs_selects_token_parameter_by_model() -> None:
    modern = completion_kwargs(
        model="gpt-5.4-mini",
        messages=[],
        max_tokens=99,
        temperature=0,
    )
    legacy = completion_kwargs(model="gpt-4.1-mini", messages=[], max_tokens=99)

    assert modern["max_completion_tokens"] == 99
    assert "max_tokens" not in modern
    assert legacy["max_tokens"] == 99


@pytest.mark.unit
def test_retry_handles_transient_error_and_records_usage() -> None:
    completions = FakeCompletions([ApiError("rate limit", 429), response()])
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    tracker = UsageTracker()
    delays: list[float] = []

    result = chat_with_retry(
        client,
        model="gpt-4.1-mini",
        messages=[],
        max_tokens=10,
        config=ModelConfig(maximum_retries=2),
        usage_tracker=tracker,
        sleep=delays.append,
        jitter=lambda _low, _high: 0.0,
    )

    assert assistant_content(result) == "ok"
    assert delays == [2.0]
    assert tracker.totals.total_tokens == 5


@pytest.mark.unit
def test_bad_request_retries_without_unsupported_temperature() -> None:
    completions = FakeCompletions([ApiError("temperature is unsupported", 400), response("fixed")])
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))

    result = chat_with_retry(
        client,
        model="gpt-4.1-mini",
        messages=[],
        max_tokens=10,
        temperature=0.2,
    )

    assert assistant_content(result) == "fixed"
    assert "temperature" in completions.calls[0]
    assert "temperature" not in completions.calls[1]


@pytest.mark.unit
def test_auth_and_quota_errors_fail_without_retry() -> None:
    for error, expected in [
        (ApiError("bad key", 401), "credentials"),
        (ApiError("insufficient_quota", 429), "quota"),
    ]:
        completions = FakeCompletions([error])
        client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
        with pytest.raises(ExternalServiceError, match=expected):
            chat_with_retry(client, model="gpt-4.1-mini", messages=[], max_tokens=10)
        assert len(completions.calls) == 1


@pytest.mark.unit
def test_content_adapter_returns_text_and_rejects_bad_shape() -> None:
    completions = FakeCompletions([response("hello")])
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    complete = make_text_completion(client)

    assert complete(model="gpt-4.1-mini", messages=[], max_tokens=5) == "hello"
    with pytest.raises(ExternalServiceError, match="assistant text"):
        assistant_content(SimpleNamespace())
