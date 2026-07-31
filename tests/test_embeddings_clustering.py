"""Embedding, reduction, clustering, and representative selection tests."""

from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
import pytest

from codeframe.clustering import (
    cluster_responses,
    discover_themes,
    get_representative_samples,
    reduce_dimensions_umap,
)
from codeframe.config import ModelConfig
from codeframe.embeddings import generate_embeddings
from codeframe.usage import UsageTracker


class FakeEmbeddings:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)
        items = [
            SimpleNamespace(index=index, embedding=[float(value), float(index)])
            for index, value in reversed(list(enumerate(range(len(kwargs["input"])))))
        ]
        return SimpleNamespace(data=items, usage=SimpleNamespace(total_tokens=7))


@pytest.mark.unit
def test_generate_embeddings_normalizes_batches_sorts_and_tracks_usage() -> None:
    resource = FakeEmbeddings()
    client = SimpleNamespace(embeddings=resource)
    tracker = UsageTracker()

    embeddings = generate_embeddings(
        ["a", None, "c"],
        client,
        batch_size=2,
        usage_tracker=tracker,
    )

    assert resource.calls[0]["input"] == ["a", ""]
    assert resource.calls[1]["input"] == ["c"]
    assert embeddings.dtype == np.float32
    assert embeddings.tolist() == [[0.0, 0.0], [1.0, 1.0], [0.0, 0.0]]
    assert tracker.totals.total_tokens == 14


@pytest.mark.unit
def test_representatives_prefer_probability_and_exclude_noise() -> None:
    texts = ["noise", "low", "high", "middle", "other"]
    labels = [-1, 0, 0, 0, 1]

    result = get_representative_samples(
        texts,
        labels,
        probabilities=[0.9, 0.1, 0.9, 0.5, 0.4],
        n_samples=2,
    )

    assert result == {0: ["high", "middle"], 1: ["other"]}
    assert get_representative_samples(texts, labels, n_samples=2)[0] == ["low", "middle"]


@pytest.mark.unit
def test_umap_rejects_too_few_rows_before_library_call() -> None:
    with pytest.raises(ValueError, match="at least 3"):
        reduce_dimensions_umap(np.ones((2, 4), dtype=np.float32))


@pytest.mark.parity
def test_umap_uses_capped_notebook_parameters(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: dict[str, Any] = {}

    class FakeReducer:
        def __init__(self, **kwargs: Any) -> None:
            observed.update(kwargs)

        def fit_transform(self, values: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
            return np.zeros((len(values), observed["n_components"]), dtype=np.float32)

    monkeypatch.setattr("codeframe.clustering.umap.UMAP", FakeReducer)
    reduced = reduce_dimensions_umap(
        np.ones((6, 3), dtype=np.float32),
        n_components=10,
        n_neighbors=15,
    )

    assert reduced.shape == (6, 3)
    assert observed == {
        "n_components": 3,
        "n_neighbors": 5,
        "min_dist": 0.0,
        "metric": "cosine",
        "random_state": 42,
        "n_jobs": 1,
        "low_memory": True,
    }


@pytest.mark.parity
def test_hdbscan_uses_notebook_parameters_and_cosine_distance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    class FakeClusterer:
        def __init__(self, **kwargs: Any) -> None:
            observed.update(kwargs)

        def fit_predict(self, values: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
            observed["fit_input"] = values
            return np.asarray([0, 0, -1])

    monkeypatch.setattr("codeframe.clustering.hdbscan.HDBSCAN", FakeClusterer)
    labels, _ = cluster_responses(
        np.asarray([[1.0, 0.0], [0.8, 0.2], [0.0, 1.0]]),
        min_cluster_size=3,
        metric="cosine",
    )

    assert labels.tolist() == [0, 0, -1]
    assert observed["min_cluster_size"] == 3
    assert observed["min_samples"] == 1
    assert observed["cluster_selection_epsilon"] == 0.4
    assert observed["metric"] == "precomputed"
    assert observed["cluster_selection_method"] == "eom"
    assert np.diag(observed["fit_input"]).tolist() == pytest.approx([0.0, 0.0, 0.0])


@pytest.mark.integration
def test_discover_themes_resets_index_and_preserves_cluster_contract() -> None:
    dataframe = pd.DataFrame(
        {"final_text_fr": [f"response {index}" for index in range(10)]},
        index=range(20, 30),
    )
    labels = np.asarray([0, 0, 0, 0, 0, 1, 1, 1, 1, -1])
    probabilities = np.linspace(0.1, 1.0, 10)
    observed: dict[str, Any] = {}

    def embed(texts: list[object], client: Any) -> np.ndarray[Any, np.dtype[np.float32]]:
        observed["texts"] = texts
        return np.ones((10, 4), dtype=np.float32)

    def reduce(values: np.ndarray[Any, np.dtype[np.float32]]) -> np.ndarray[Any, Any]:
        assert values.shape == (10, 4)
        return np.ones((10, 2), dtype=np.float32)

    def cluster(values: np.ndarray[Any, Any], minimum: int) -> tuple[np.ndarray[Any, Any], Any]:
        observed["minimum"] = minimum
        return labels, SimpleNamespace(probabilities_=probabilities)

    result, returned_labels, representatives, sizes = discover_themes(
        dataframe,
        SimpleNamespace(),
        text_column="final_text_fr",
        embed=embed,
        reduce=reduce,
        cluster=cluster,
    )

    assert result.index.tolist() == list(range(10))
    assert returned_labels.tolist() == labels.tolist()
    assert result["cluster_probability"].tolist() == probabilities.tolist()
    assert sizes == {0: 5, 1: 4}
    assert observed["minimum"] == 3
    assert set(representatives) == {0, 1}


@pytest.mark.integration
def test_discover_themes_uses_configured_embedding_model_and_tracker() -> None:
    dataframe = pd.DataFrame({"final_text_fr": [f"response {index}" for index in range(10)]})
    resource = FakeEmbeddings()
    tracker = UsageTracker()

    def reduce(values: np.ndarray[Any, np.dtype[np.float32]]) -> np.ndarray[Any, Any]:
        return values

    def cluster(values: np.ndarray[Any, Any], minimum: int) -> tuple[np.ndarray[Any, Any], Any]:
        return np.asarray([0] * len(values)), SimpleNamespace(probabilities_=np.ones(len(values)))

    discover_themes(
        dataframe,
        SimpleNamespace(embeddings=resource),
        text_column="final_text_fr",
        model_config=ModelConfig(embedding_model="custom-embedding", embedding_batch_size=4),
        usage_tracker=tracker,
        reduce=reduce,
        cluster=cluster,
    )

    assert [call["model"] for call in resource.calls] == ["custom-embedding"] * 3
    assert tracker.totals.total_tokens == 21


@pytest.mark.unit
def test_discover_themes_requires_ten_rows() -> None:
    with pytest.raises(ValueError, match="≥ 10"):
        discover_themes(
            pd.DataFrame({"final_text_fr": ["x"] * 9}),
            SimpleNamespace(),
            text_column="final_text_fr",
        )
