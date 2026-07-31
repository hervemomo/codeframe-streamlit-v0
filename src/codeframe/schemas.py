"""Shared typed schemas derived from the notebook data contracts."""

from typing import NotRequired, TypedDict


class CodeEntry(TypedDict):
    """One normalized generated or user-supplied code."""

    name: str
    code_id: NotRequired[str]
    definition: str
    inclusion_criteria: list[str]
    exclusion_criteria: list[str]
    example_verbatims: list[str]
    source: NotRequired[str]
    source_clusters: NotRequired[list[int]]
    estimated_response_count: NotRequired[int]
    parent_code: NotRequired[str]
    parent_code_id: NotRequired[str]
    merged_from: NotRequired[list[str]]
    merged_from_ids: NotRequired[list[str]]
    definition_source: NotRequired[str]


class Codebook(TypedDict):
    """Notebook-equivalent codebook envelope."""

    codes: list[CodeEntry]
    multi_label: bool
    max_codes_per_response: NotRequired[int]
    version: NotRequired[str]
    source_version: NotRequired[str]
    codebook_language: NotRequired[str]
    generated_at: NotRequired[str]


class CodingSelection(TypedDict):
    """One code and confidence returned by a coding operation."""

    code: str
    confidence: float


class CodingResult(TypedDict):
    """Normalized per-response coding result."""

    codes: list[CodingSelection]
    reasoning: NotRequired[str]
    normalization_rule_version: NotRequired[str]
    fallback_reason: NotRequired[str]


class ReportOutputs(TypedDict, total=False):
    """Files produced by the reporting engine."""

    frequency_chart: str
    cooccurrence_chart: str | None
    summary_report: str
