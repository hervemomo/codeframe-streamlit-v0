"""Batched embedding generation with an injected external client."""

from typing import Any, Protocol, cast

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from codeframe.config import ModelConfig
from codeframe.usage import UsageTracker


class EmbeddingsResource(Protocol):
    def create(self, **kwargs: Any) -> object:
        """Create embeddings for one ordered batch."""


class EmbeddingClient(Protocol):
    embeddings: EmbeddingsResource


def generate_embeddings(
    texts: list[object],
    client: EmbeddingClient,
    *,
    model_config: ModelConfig | None = None,
    model: str | None = None,
    batch_size: int | None = None,
    usage_tracker: UsageTracker | None = None,
) -> NDArray[np.float32]:
    """Encode texts in batches, preserving API index order and notebook dtype."""

    config = model_config or ModelConfig()
    selected_model = model or config.embedding_model
    selected_batch_size = batch_size or config.embedding_batch_size
    if selected_batch_size < 1:
        raise ValueError("batch_size must be at least 1")
    normalized = ["" if pd.isna(cast(Any, text)) else str(text) for text in texts]
    vectors: list[list[float]] = []
    for start in range(0, len(normalized), selected_batch_size):
        response = client.embeddings.create(
            model=selected_model,
            input=normalized[start : start + selected_batch_size],
            timeout=config.timeout_seconds,
        )
        data = cast(Any, response).data
        vectors.extend(list(item.embedding) for item in sorted(data, key=lambda item: item.index))
        if usage_tracker is not None:
            usage_tracker.record(selected_model, getattr(response, "usage", None))
    return np.asarray(vectors, dtype=np.float32)
