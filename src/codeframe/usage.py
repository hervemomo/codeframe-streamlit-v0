"""External-model usage accounting without retaining prompt or response text."""

from dataclasses import dataclass, field
from datetime import UTC, datetime

import pandas as pd


@dataclass(frozen=True, slots=True)
class UsageRecord:
    """One model request's non-sensitive token totals."""

    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cached_prompt_tokens: int | None = None
    prompt_chars_approx: int | None = None
    system_fingerprint: str | None = None
    timestamp: str = ""


@dataclass(slots=True)
class UsageTracker:
    """Collect token totals while deliberately excluding survey content."""

    records: list[UsageRecord] = field(default_factory=list)

    def record(self, model: str, usage: object | None) -> UsageRecord:
        """Append usage from an OpenAI-shaped response usage object."""

        input_tokens = _integer_attribute(usage, "prompt_tokens", "input_tokens")
        output_tokens = _integer_attribute(usage, "completion_tokens", "output_tokens")
        total_tokens = _integer_attribute(usage, "total_tokens")
        if not total_tokens:
            total_tokens = input_tokens + output_tokens
        record = UsageRecord(
            model,
            input_tokens,
            output_tokens,
            total_tokens,
            timestamp=datetime.now(UTC).isoformat(),
        )
        self.records.append(record)
        return record

    def record_response(
        self,
        model: str,
        response: object,
        *,
        messages: list[dict[str, str]] | None = None,
    ) -> UsageRecord | None:
        """Append notebook-equivalent metadata from a successful chat response."""

        dynamic_response = response
        usage = getattr(dynamic_response, "usage", None)
        if usage is None:
            return None
        details = getattr(usage, "prompt_tokens_details", None)
        cached = getattr(details, "cached_tokens", None) if details is not None else None
        prompt_chars = (
            sum(len(str(message.get("content", ""))) for message in messages) if messages else None
        )
        record = UsageRecord(
            model=model,
            input_tokens=_integer_attribute(usage, "prompt_tokens", "input_tokens"),
            output_tokens=_integer_attribute(
                usage,
                "completion_tokens",
                "output_tokens",
            ),
            total_tokens=_integer_attribute(usage, "total_tokens"),
            cached_prompt_tokens=int(cached) if cached is not None else None,
            prompt_chars_approx=prompt_chars,
            system_fingerprint=getattr(dynamic_response, "system_fingerprint", None),
            timestamp=datetime.now(UTC).isoformat(),
        )
        self.records.append(record)
        return record

    @property
    def totals(self) -> UsageRecord:
        """Return aggregate totals across recorded requests."""

        return UsageRecord(
            model="all",
            input_tokens=sum(record.input_tokens for record in self.records),
            output_tokens=sum(record.output_tokens for record in self.records),
            total_tokens=sum(record.total_tokens for record in self.records),
        )

    def to_dataframe(self) -> pd.DataFrame:
        """Return the notebook-style session usage table."""

        return pd.DataFrame(
            [
                {
                    "timestamp": record.timestamp,
                    "model": record.model,
                    "prompt_tokens": record.input_tokens,
                    "completion_tokens": record.output_tokens,
                    "total_tokens": record.total_tokens,
                    "cached_prompt_tokens": record.cached_prompt_tokens,
                    "prompt_chars_approx": record.prompt_chars_approx,
                    "system_fingerprint": record.system_fingerprint,
                }
                for record in self.records
            ]
        )


def _integer_attribute(value: object | None, *names: str) -> int:
    if value is None:
        return 0
    for name in names:
        raw = getattr(value, name, None)
        if raw is None and isinstance(value, dict):
            raw = value.get(name)
        if raw is not None:
            try:
                return int(raw)
            except (TypeError, ValueError):
                return 0
    return 0
