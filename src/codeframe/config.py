"""Typed configuration matching the notebook's Phase 1 baseline defaults."""

from dataclasses import dataclass
from typing import Literal

CodingMode = Literal["ai", "manual"]
CodebookLanguage = Literal["fr", "en"]


@dataclass(frozen=True, slots=True)
class LanguageConfig:
    """Language detection and translation routing settings."""

    target_language_code: str = "fr"
    codebook_language_code: CodebookLanguage = "fr"
    translate_source_language_codes: tuple[str, ...] | None = None
    uncertain_threshold: float = 0.80
    minimum_alpha_characters: int = 4
    mixed_language_margin: float = 0.05
    translation_batch_size: int = 15

    def __post_init__(self) -> None:
        if not self.target_language_code.strip():
            raise ValueError("target_language_code must not be blank")
        if self.codebook_language_code not in {"fr", "en"}:
            raise ValueError("codebook_language_code must be 'fr' or 'en'")
        if not 0.60 <= self.uncertain_threshold <= 0.95:
            raise ValueError("uncertain_threshold must be between 0.60 and 0.95")
        if self.minimum_alpha_characters < 1:
            raise ValueError("minimum_alpha_characters must be at least 1")
        if self.mixed_language_margin < 0:
            raise ValueError("mixed_language_margin must not be negative")
        if self.translation_batch_size < 1:
            raise ValueError("translation_batch_size must be at least 1")

    @property
    def text_column(self) -> str:
        """Notebook-equivalent downstream coding-text column."""

        return f"final_text_{self.target_language_code.lower().strip()}"


@dataclass(frozen=True, slots=True)
class ModelConfig:
    """External-model choices and request reliability settings."""

    reasoning_model: str = "gpt-5.4-mini"
    coding_model: str = "gpt-4.1-mini"
    embedding_model: str = "text-embedding-3-small"
    reasoning_temperature: float = 0.0
    reasoning_seed: int = 42
    embedding_batch_size: int = 100
    timeout_seconds: float = 180.0
    maximum_retries: int = 10

    def __post_init__(self) -> None:
        for field_name in ("reasoning_model", "coding_model", "embedding_model"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} must not be blank")
        if self.embedding_batch_size < 1:
            raise ValueError("embedding_batch_size must be at least 1")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.maximum_retries < 1:
            raise ValueError("maximum_retries must be at least 1")


@dataclass(frozen=True, slots=True)
class CodingConfig:
    """Code assignment and codebook-generation limits."""

    mode: CodingMode = "manual"
    coding_batch_size: int = 20
    maximum_codes_per_response: int = 3
    use_compact_codebook: bool = True
    save_reasoning: bool = False
    generation_max_tokens: int = 8_000
    generation_retry_max_tokens: int = 12_000
    target_code_cap: int | None = None

    def __post_init__(self) -> None:
        if self.mode not in {"ai", "manual"}:
            raise ValueError("mode must be 'ai' or 'manual'")
        if self.coding_batch_size < 1:
            raise ValueError("coding_batch_size must be at least 1")
        if self.maximum_codes_per_response < 1:
            raise ValueError("maximum_codes_per_response must be at least 1")
        if self.generation_max_tokens < 1:
            raise ValueError("generation_max_tokens must be at least 1")
        if self.generation_retry_max_tokens < self.generation_max_tokens:
            raise ValueError("generation_retry_max_tokens must be at least generation_max_tokens")
        if self.target_code_cap is not None and self.target_code_cap < 1:
            raise ValueError("target_code_cap must be positive when supplied")


@dataclass(frozen=True, slots=True)
class UserCodebookConfig:
    """Section 3 enhancement and coding defaults."""

    enhance_with_ai: bool = True
    enhancement_batch_size: int = 20
    enhancement_prompt_version: str = "user-codebook-enhancement-v1"
    enable_part2: bool = True
    part2_use_batch: bool = True
    part2_batch_size: int = 15
    part2_format_retries: int = 1
    part2_delay_seconds: float = 0.2
    part2_prompt_version: str = "user-codebook-coding-v1"

    def __post_init__(self) -> None:
        if self.enhancement_batch_size < 1:
            raise ValueError("enhancement_batch_size must be positive")
        if self.part2_batch_size < 1:
            raise ValueError("part2_batch_size must be positive")
        if self.part2_format_retries < 0:
            raise ValueError("part2_format_retries must not be negative")
        if self.part2_delay_seconds < 0:
            raise ValueError("part2_delay_seconds must not be negative")
        if not self.enhancement_prompt_version.strip():
            raise ValueError("enhancement_prompt_version must not be blank")
        if not self.part2_prompt_version.strip():
            raise ValueError("part2_prompt_version must not be blank")


@dataclass(frozen=True, slots=True)
class ClusteringConfig:
    """UMAP and HDBSCAN defaults from notebook cell 5."""

    umap_components: int = 10
    umap_neighbors: int = 15
    minimum_samples: int = 1
    cluster_selection_epsilon: float = 0.4
    representatives_per_cluster: int = 3
    random_seed: int = 42

    def __post_init__(self) -> None:
        if self.umap_components < 1:
            raise ValueError("umap_components must be at least 1")
        if self.umap_neighbors < 2:
            raise ValueError("umap_neighbors must be at least 2")
        if self.minimum_samples < 1:
            raise ValueError("minimum_samples must be at least 1")
        if self.cluster_selection_epsilon < 0:
            raise ValueError("cluster_selection_epsilon must not be negative")
        if self.representatives_per_cluster < 1:
            raise ValueError("representatives_per_cluster must be at least 1")


@dataclass(frozen=True, slots=True)
class ProjectConfig:
    """Top-level configuration passed explicitly into future workflow services."""

    survey_question: str
    survey_context: str
    language: LanguageConfig = LanguageConfig()
    models: ModelConfig = ModelConfig()
    coding: CodingConfig = CodingConfig()
    user_codebook: UserCodebookConfig = UserCodebookConfig()
    clustering: ClusteringConfig = ClusteringConfig()

    def __post_init__(self) -> None:
        if not self.survey_question.strip():
            raise ValueError("survey_question must not be blank")
        if not self.survey_context.strip():
            raise ValueError("survey_context must not be blank")
