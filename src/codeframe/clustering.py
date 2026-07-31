"""UMAP, HDBSCAN, and representative-sample services."""

from collections.abc import Callable, Sequence
from typing import Any

import hdbscan  # type: ignore[import-untyped]
import numpy as np
import pandas as pd
import umap  # type: ignore[import-untyped]
from numpy.typing import NDArray
from sklearn.metrics.pairwise import cosine_distances  # type: ignore[import-untyped]

from codeframe.config import ClusteringConfig, ModelConfig
from codeframe.embeddings import EmbeddingClient, generate_embeddings
from codeframe.usage import UsageTracker


def reduce_dimensions_umap(
    embeddings: NDArray[np.floating[Any]],
    *,
    config: ClusteringConfig | None = None,
    n_components: int | None = None,
    n_neighbors: int | None = None,
) -> NDArray[np.floating[Any]]:
    """Reduce embeddings using the notebook's capped deterministic UMAP settings."""

    settings = config or ClusteringConfig()
    components = min(
        n_components or settings.umap_components,
        len(embeddings) - 2,
        embeddings.shape[1],
    )
    neighbors = min(n_neighbors or settings.umap_neighbors, len(embeddings) - 1)
    if components < 1 or neighbors < 2:
        raise ValueError("UMAP requires at least 3 embedding rows.")
    reducer = umap.UMAP(
        n_components=components,
        n_neighbors=neighbors,
        min_dist=0.0,
        metric="cosine",
        random_state=settings.random_seed,
        n_jobs=1,
        low_memory=True,
    )
    return np.asarray(reducer.fit_transform(embeddings))


def cluster_responses(
    embeddings: NDArray[np.floating[Any]],
    *,
    min_cluster_size: int = 5,
    config: ClusteringConfig | None = None,
    min_samples: int | None = None,
    epsilon: float | None = None,
    metric: str = "euclidean",
) -> tuple[NDArray[np.integer[Any]], Any]:
    """Cluster embeddings, including the notebook's optional cosine-distance path."""

    settings = config or ClusteringConfig()
    resolved_samples = min_samples or settings.minimum_samples
    resolved_epsilon = settings.cluster_selection_epsilon if epsilon is None else epsilon
    fit_input: NDArray[np.floating[Any]]
    hdbscan_metric: str
    if metric == "cosine":
        fit_input = np.asarray(cosine_distances(embeddings))
        hdbscan_metric = "precomputed"
    else:
        fit_input = embeddings
        hdbscan_metric = metric
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=resolved_samples,
        cluster_selection_epsilon=resolved_epsilon,
        metric=hdbscan_metric,
        cluster_selection_method="eom",
    )
    return np.asarray(clusterer.fit_predict(fit_input)), clusterer


def get_representative_samples(
    texts: Sequence[str],
    labels: Sequence[int],
    *,
    probabilities: Sequence[float] | None = None,
    n_samples: int | None = None,
    config: ClusteringConfig | None = None,
) -> dict[int, list[str]]:
    """Pick top-probability members, or evenly spaced members as fallback."""

    settings = config or ClusteringConfig()
    count = n_samples or settings.representatives_per_cluster
    representatives: dict[int, list[str]] = {}
    for cluster_id in sorted(set(labels)):
        if cluster_id == -1:
            continue
        if probabilities is not None:
            ranked_members = [
                (text, probability)
                for text, label, probability in zip(texts, labels, probabilities, strict=True)
                if label == cluster_id
            ]
            ranked_members.sort(key=lambda item: item[1], reverse=True)
            representatives[int(cluster_id)] = [
                text for text, _ in ranked_members[: min(count, len(ranked_members))]
            ]
        else:
            cluster_members = [
                text for text, label in zip(texts, labels, strict=True) if label == cluster_id
            ]
            indexes = np.linspace(
                0,
                len(cluster_members) - 1,
                min(count, len(cluster_members)),
                dtype=int,
            )
            representatives[int(cluster_id)] = [cluster_members[index] for index in indexes]
    return representatives


type EmbeddingFunction = Callable[[list[object], EmbeddingClient], NDArray[np.float32]]
type ReducerFunction = Callable[[NDArray[np.float32]], NDArray[np.floating[Any]]]
type ClusterFunction = Callable[
    [NDArray[np.floating[Any]], int], tuple[NDArray[np.integer[Any]], Any]
]


def discover_themes(
    dataframe: pd.DataFrame,
    client: EmbeddingClient,
    *,
    text_column: str = "final_text_fr",
    config: ClusteringConfig | None = None,
    model_config: ModelConfig | None = None,
    usage_tracker: UsageTracker | None = None,
    embed: EmbeddingFunction | None = None,
    reduce: ReducerFunction | None = None,
    cluster: ClusterFunction | None = None,
) -> tuple[pd.DataFrame, NDArray[np.integer[Any]], dict[int, list[str]], dict[int, int]]:
    """Run the notebook embedding-to-clustering pipeline."""

    settings = config or ClusteringConfig()
    result = dataframe.copy().reset_index(drop=True)
    texts = result[text_column].tolist()
    if len(texts) < 10:
        raise ValueError("Need ≥ 10 responses for clustering.")
    embeddings = (
        embed(texts, client)
        if embed is not None
        else generate_embeddings(
            texts,
            client,
            model_config=model_config,
            usage_tracker=usage_tracker,
        )
    )
    reduced = (
        reduce(embeddings)
        if reduce is not None
        else reduce_dimensions_umap(embeddings, config=settings)
    )
    minimum_cluster_size = max(3, len(texts) // 50)
    labels, clusterer = (
        cluster(reduced, minimum_cluster_size)
        if cluster is not None
        else cluster_responses(
            reduced,
            min_cluster_size=minimum_cluster_size,
            config=settings,
        )
    )
    probabilities = getattr(clusterer, "probabilities_", None)
    representatives = get_representative_samples(
        [str(text) for text in texts],
        labels.tolist(),
        probabilities=probabilities,
        config=settings,
    )
    result["cluster"] = labels
    result["cluster_probability"] = probabilities if probabilities is not None else 0.0
    cluster_sizes = {
        int(cluster_id): int((labels == cluster_id).sum())
        for cluster_id in sorted(set(labels))
        if cluster_id != -1
    }
    return result, labels, representatives, cluster_sizes
