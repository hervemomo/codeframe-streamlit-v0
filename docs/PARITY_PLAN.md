# Notebook Parity Plan

## Immutable baseline

- Source: `original_notebook.ipynb`
- SHA-256:
  `202eefa5db6c0f39d72e63f1401e1c30edc821e83326483c92c1721b72c626f8`
- Recorded: 2026-07-31
- Enforcement: `codeframe.parity`, `scripts/check_notebook_baseline.py`,
  pre-commit, unit test, and CI

The digest covers exact bytes, including source, Markdown, outputs, and metadata.

## Comparison principles

- Compare deterministic transforms, schemas, ordering, filenames, and defaults exactly.
- Use fixed mocked model responses for Chat Completions and Embeddings.
- Compare request construction, parsing, retries, and fallbacks for nondeterministic work.
- Never use live API output as exact-wording parity evidence.
- Preserve the notebook as the oracle until each mapped behavior is verified.

## Required parity areas

| Area | Baseline fixture | Comparison | Tolerance | Status | Planned evidence |
|---|---|---|---|---|---|
| Notebook integrity | Notebook bytes | SHA-256 | Exact | VERIFIED | `tests/test_foundation.py` |
| Configuration defaults | Cell 5 | Values and validation | Exact | VERIFIED | `tests/test_config.py` |
| Loading | Generated CSV/XLSX fixtures | Rows/order/IDs/columns | Exact | VERIFIED | `test_loaders_preprocessing.py` |
| Preprocessing | Mixed-validity fixture | Text/exclusions/audit | Exact | VERIFIED | `test_loaders_preprocessing.py`, Phase 2 integration |
| Language routing | Fixed detector outputs + Lingua smoke | Status/confidence/route | Exact decisions | VERIFIED | `test_language.py` |
| Translation | Fixed mocked outputs | Batches/fallback/final columns | Exact | VERIFIED | `test_translation.py`, Phase 2 integration |
| Reporting | Fixed coded run | Math/sheets/filenames | Exact except KI-002 backend | EQUIVALENT WITH DOCUMENTED DIFFERENCE | `test_reporting_exports.py` |
| Embeddings | Fixed mocked vectors | Input order/shape/batches | Exact | VERIFIED | `test_embeddings_clustering.py` |
| UMAP/HDBSCAN | Fixed seed/input | Parameters/labels/shapes | Notebook-defined | VERIFIED | `test_embeddings_clustering.py` |
| Codebook generation | Fixed mocked response | Prompt/parse/schema/order | Exact | VERIFIED | `test_codebook_generation.py`, Phase 3 e2e |
| Coding | Fixed mocked response | Assignments/normalization | Exact | VERIFIED | `test_ai_coding.py`, Phase 3 e2e |
| User codebook | CSV/XLSX fixtures | Preservation/IDs/patches | Exact | VERIFIED | `test_user_codebook.py` |
| Split | Fixture run | Codebook/columns/affected rows | Exact | VERIFIED | `test_split_merge.py` |
| Merge | Fixture run | OR result/columns/codebook | Exact | VERIFIED | `test_split_merge.py` |
| UI workflows | Mocked services | State transitions/invalidation | Exact contract | VERIFIED | `test_workflow_state.py`, `test_streamlit_ui.py` |

## Phase 1 evidence

- All 78 cells mapped through 31 coherent groups.
- Exact notebook defaults captured in typed configuration.
- Domain-package import graph checked for Streamlit.
- Notebook source was not changed.

## Phase 2 evidence

- Blank removal occurs before generated 1-based response IDs.
- Source metadata and selected IDs remain ordered and unchanged.
- Invalid and exact-duplicate audit overlap matches the notebook.
- Lingua status precedence is insufficient/unsupported, mixed, uncertain, detected.
- Translation uses all non-target languages by default, exact status values, confident
  source hints, auto-detection for uncertain groups, batch then individual fallback,
  and unresolved/fatal fail-closed behavior.
- Frequency percentages use retained unique response count; co-occurrence is exact
  binary matrix multiplication.
- Workbook sheet order, columns, metrics, chart names, and processed CSV name verified.

## Phase 3 evidence

- Embedding inputs normalize missing values, batch at the configured size, preserve API
  index order, return `float32`, and record token usage without survey text.
- UMAP component/neighbor caps, cosine metric, zero minimum distance, random seed,
  single-thread setting, and HDBSCAN selection parameters match cell 22.
- Noise label `-1`, cluster probabilities, cluster sizes, and representative ordering
  follow the notebook, including evenly spaced fallback without probabilities.
- Codebook prompts preserve language, target-code, multi-label, concision, catch-all,
  and exhaustive one-code-per-cluster provenance instructions.
- Malformed or incomplete generated JSON retries once with the larger configured
  budget; validation rejects missing/duplicate cluster coverage.
- Coding preserves relevance order, recovers exact governed IDs, audits invalid and
  duplicate model output, clamps confidence, applies the single/multi-label cap, and
  makes the localized catch-all exclusive at confidence `0.50`.
- The mocked end-to-end fixture runs theme discovery → codebook generation → coding →
  summary columns → codebook JSON and report workbook without live API calls.

## Phase 4 evidence

- CSV and Excel codebooks auto-detect the notebook's English/French aliases, preserve
  supplied values and row order, reject duplicate names, and deterministically fill
  blank ID cells without changing supplied IDs.
- Enhancement requests expose only opaque code references and missing fields; validated
  patches cannot rename, reorder, remove, or overwrite supplied content.
- Enhanced JSON/XLSX output is re-importable and carries generated-field audit metadata.
- Part 2 keeps the fixed prompt prefix, validates exact-name arrays, retries invalid
  single-response output, falls back per item after malformed batches, deduplicates
  repeated texts, and applies the catch-all at `0.50`.
- Split tests verify that only parent-assigned rows are recoded, unaffected assignments
  remain unchanged, deterministic child IDs and parent provenance are retained, and a
  no-match row is routed through the main catch-all.
- Merge tests verify binary OR assignments, maximum source confidence, first-source
  insertion order, source-column removal, ID/provenance generation, and zero LLM
  reclassification for complete manual merges.
- Cancelled or unconfirmed split/merge plans return new unchanged state with empty
  output lists, preventing stale-result display.

## Phase 5 evidence

- Six Streamlit pages implement the notebook sequence while keeping AI-generated and
  user-supplied codebooks as alternative paths.
- Framework-neutral state tests verify stable fingerprints, project/survey/codebook
  invalidation, active-path promotion, repeated split/merge chaining, output
  deduplication, elapsed time, and model-usage aggregation.
- Streamlit `AppTest` coverage verifies safe prerequisite messages on all dependent
  pages, explicit project/path selection, no workflow execution before button actions,
  mocked AI and manual coding promotion, cancelled split freshness, and final result
  rendering.
- User-codebook Part 1 is available without preprocessed responses; Part 2 is gated on
  both inputs.
- Configured embedding model and batch settings plus the shared usage tracker now flow
  through AI theme discovery; KI-003 records the correction.
- The startup smoke script launches the final application headlessly and verifies the
  local Streamlit health endpoint without live model calls.

## Discrepancy protocol

Re-inspect the relevant cell, document the issue in `KNOWN_ISSUES.md`, implement the
closest safe equivalent, add a regression test, link traceability, and classify the
result honestly.
