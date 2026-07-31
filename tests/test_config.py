"""Foundation tests for notebook-derived typed configuration."""

from collections.abc import Callable
from typing import cast

import pytest

from codeframe.config import (
    ClusteringConfig,
    CodebookLanguage,
    CodingConfig,
    CodingMode,
    LanguageConfig,
    ModelConfig,
    ProjectConfig,
)


@pytest.mark.unit
def test_notebook_defaults_are_preserved() -> None:
    language = LanguageConfig()
    models = ModelConfig()
    coding = CodingConfig()
    clustering = ClusteringConfig()

    assert language.text_column == "final_text_fr"
    assert language.translate_source_language_codes is None
    assert models.reasoning_model == "gpt-5.4-mini"
    assert models.coding_model == "gpt-4.1-mini"
    assert models.embedding_model == "text-embedding-3-small"
    assert coding.mode == "manual"
    assert coding.maximum_codes_per_response == 3
    assert clustering.random_seed == 42
    assert clustering.cluster_selection_epsilon == 0.4


@pytest.mark.unit
@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (lambda: LanguageConfig(target_language_code=" "), "target_language_code"),
        (
            lambda: LanguageConfig(codebook_language_code=cast(CodebookLanguage, "es")),
            "codebook_language_code",
        ),
        (lambda: LanguageConfig(uncertain_threshold=0.5), "uncertain_threshold"),
        (lambda: LanguageConfig(minimum_alpha_characters=0), "minimum_alpha_characters"),
        (lambda: LanguageConfig(mixed_language_margin=-0.1), "mixed_language_margin"),
        (lambda: LanguageConfig(translation_batch_size=0), "translation_batch_size"),
        (lambda: ModelConfig(reasoning_model=""), "reasoning_model"),
        (lambda: ModelConfig(embedding_batch_size=0), "embedding_batch_size"),
        (lambda: ModelConfig(timeout_seconds=0), "timeout_seconds"),
        (lambda: ModelConfig(maximum_retries=-1), "maximum_retries"),
        (
            lambda: CodingConfig(mode=cast(CodingMode, "automatic")),
            "mode",
        ),
        (lambda: CodingConfig(coding_batch_size=0), "coding_batch_size"),
        (lambda: CodingConfig(maximum_codes_per_response=0), "maximum_codes_per_response"),
        (lambda: CodingConfig(generation_max_tokens=0), "generation_max_tokens"),
        (
            lambda: CodingConfig(generation_max_tokens=10, generation_retry_max_tokens=9),
            "generation_retry_max_tokens",
        ),
        (lambda: CodingConfig(target_code_cap=0), "target_code_cap"),
        (lambda: ClusteringConfig(umap_components=0), "umap_components"),
        (lambda: ClusteringConfig(umap_neighbors=1), "umap_neighbors"),
        (lambda: ClusteringConfig(minimum_samples=0), "minimum_samples"),
        (
            lambda: ClusteringConfig(cluster_selection_epsilon=-0.1),
            "cluster_selection_epsilon",
        ),
        (
            lambda: ClusteringConfig(representatives_per_cluster=0),
            "representatives_per_cluster",
        ),
    ],
)
def test_invalid_configuration_fails_safely(factory: Callable[[], object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        factory()


@pytest.mark.unit
def test_project_requires_context_and_question() -> None:
    with pytest.raises(ValueError, match="survey_question"):
        ProjectConfig(survey_question="", survey_context="context")
    with pytest.raises(ValueError, match="survey_context"):
        ProjectConfig(survey_question="question", survey_context="")

    project = ProjectConfig(survey_question="Why?", survey_context="Consumer study")
    assert project.language.text_column == "final_text_fr"
