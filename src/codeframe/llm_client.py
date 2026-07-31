"""Injected OpenAI-compatible completion boundary and notebook retry behavior."""

import random
import time
from collections.abc import Callable
from typing import Any, Protocol, cast

from codeframe.config import ModelConfig
from codeframe.exceptions import ExternalServiceError
from codeframe.usage import UsageTracker

type Messages = list[dict[str, str]]


class CompletionsResource(Protocol):
    """OpenAI-compatible ``chat.completions`` resource."""

    def create(self, **kwargs: Any) -> object:
        """Create one completion response."""


class ChatResource(Protocol):
    completions: CompletionsResource


class ChatClient(Protocol):
    chat: ChatResource


class TextCompletion(Protocol):
    """Content-only completion boundary consumed by domain services."""

    def __call__(self, **kwargs: Any) -> str:
        """Return assistant text."""


def uses_max_completion_tokens(model: str) -> bool:
    """Return whether the model uses the newer completion-token parameter."""

    return model.lower().startswith(("o1", "o3", "o4", "gpt-5"))


def completion_kwargs(
    *,
    model: str,
    messages: Messages,
    max_tokens: int,
    temperature: float | None = None,
    seed: int | None = None,
    timeout: float = 180.0,
) -> dict[str, Any]:
    """Build the notebook-equivalent Chat Completions request payload."""

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "timeout": timeout,
    }
    token_key = "max_completion_tokens" if uses_max_completion_tokens(model) else "max_tokens"
    kwargs[token_key] = max_tokens
    if temperature is not None:
        kwargs["temperature"] = temperature
    if seed is not None:
        kwargs["seed"] = seed
    return kwargs


def _status_code(error: BaseException) -> int | None:
    status = getattr(error, "status_code", None)
    if status is None:
        response = getattr(error, "response", None)
        status = getattr(response, "status_code", None)
    return status if isinstance(status, int) else None


def _is_transient(error: BaseException) -> bool:
    text = str(error).lower()
    return _status_code(error) in {429, 500, 502, 503, 504} or any(
        token in text for token in ("rate limit", "timeout", "temporar")
    )


def _is_quota_error(error: BaseException) -> bool:
    text = str(error).lower()
    return any(token in text for token in ("insufficient_quota", "billing", "quota"))


def chat_with_retry(
    client: ChatClient,
    *,
    model: str,
    messages: Messages,
    max_tokens: int,
    temperature: float | None = None,
    seed: int | None = None,
    config: ModelConfig | None = None,
    usage_tracker: UsageTracker | None = None,
    sleep: Callable[[float], None] = time.sleep,
    jitter: Callable[[float, float], float] = random.uniform,
) -> object:
    """Call Chat Completions with bounded retry and parameter compatibility fallback."""

    settings = config or ModelConfig()
    kwargs = completion_kwargs(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        seed=seed,
        timeout=settings.timeout_seconds,
    )
    compatibility_retried = False
    for attempt in range(settings.maximum_retries):
        try:
            response = client.chat.completions.create(**kwargs)
            if usage_tracker is not None:
                usage_tracker.record_response(model, response, messages=messages)
            return response
        except Exception as error:
            status = _status_code(error)
            text = str(error).lower()
            if status == 401:
                raise ExternalServiceError("Invalid API credentials.") from error
            if _is_quota_error(error):
                raise ExternalServiceError("API quota or billing limit reached.") from error
            if status == 400 and not compatibility_retried:
                changed = False
                if "temperature" in text and "temperature" in kwargs:
                    kwargs.pop("temperature")
                    changed = True
                if "max_tokens" in text and "max_completion_tokens" in text:
                    old_key = (
                        "max_completion_tokens"
                        if "max_completion_tokens" in kwargs
                        else "max_tokens"
                    )
                    new_key = (
                        "max_tokens"
                        if old_key == "max_completion_tokens"
                        else "max_completion_tokens"
                    )
                    kwargs[new_key] = kwargs.pop(old_key)
                    changed = True
                if changed:
                    compatibility_retried = True
                    continue
            if not _is_transient(error) or attempt == settings.maximum_retries - 1:
                raise ExternalServiceError(
                    f"Model request failed after {attempt + 1} attempt(s)."
                ) from error
            delay = min(90.0, 2.0 * (2**attempt))
            sleep(delay + jitter(0.0, 0.5 * delay))
    raise AssertionError("unreachable")


def assistant_content(response: object) -> str:
    """Extract assistant content from an OpenAI-shaped response."""

    try:
        dynamic_response = cast(Any, response)
        return str(dynamic_response.choices[0].message.content or "")
    except (AttributeError, IndexError, TypeError) as error:
        raise ExternalServiceError("Model response did not contain assistant text.") from error


def make_text_completion(
    client: ChatClient,
    *,
    config: ModelConfig | None = None,
    usage_tracker: UsageTracker | None = None,
) -> TextCompletion:
    """Adapt an injected client to the content-only domain boundary."""

    def complete(**kwargs: Any) -> str:
        response = chat_with_retry(
            client,
            config=config,
            usage_tracker=usage_tracker,
            **kwargs,
        )
        return assistant_content(response)

    return complete
