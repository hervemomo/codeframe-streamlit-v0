# Data Schemas

These are notebook-derived contracts. Exact pandas dtypes will be verified with
fixtures in the implementation phase for each schema.

## Source survey

| Field | Type | Required | Source | Notes |
|---|---|---:|---|---|
| Selected response column | tabular scalar | yes | CSV/XLS/XLSX | Blank/null rows dropped |
| Optional selected ID column | tabular scalar | no | Source file | Preserved when selected |
| Other metadata columns | tabular scalar | no | Source file | Preserved in memory |

## Loaded and preprocessed responses

| Field | Type | Required | Derivation |
|---|---|---:|---|
| `response_id` | source value or 1-based integer | yes | Selected ID, otherwise assigned after blank removal |
| `original_text` | string | yes | Selected response converted to string |
| `cleaned_text` | string | yes | `clean_text` |
| `detected_lang` | string | yes | Lingua ISO code or `other` |
| `detected_lang_status` | enum string | yes | `detected`, `uncertain`, `mixed_language`, `unsupported_language`, `insufficient_text` |
| `detected_lang_confidence` | float or blank | yes | Lingua top confidence |
| `translation_status` | enum string | yes after routing | `not_requested`, `not_required`, `pending`, `translated`, `unresolved_translation` |
| `final_text_<target>` | string | yes after routing | Cleaned target-language text or translation |

## Removed-record audit

The audit workbook has `Invalid Records` and `Duplicate Records` sheets. Each
contains source metadata plus:

| Field | Type | Required | Derivation |
|---|---|---:|---|
| `response_id` | source value or integer | yes | Loader |
| `original_text` | string | yes | Loader |
| `cleaned_text` | string | yes | Cleaner |
| `is_valid` | bool | yes | Minimum-word/junk validation |
| `is_duplicate` | bool | yes | Exact cleaned-text duplicate, `keep="first"` |

## Codebook

Top-level required fields are `codes` and `multi_label`. Optional metadata includes
`version`, `source_version`, `generated_at`, `codebook_language`,
`max_codes_per_response`, deterministic `generated_code_ids`, and enhancement metadata
(`operation`, `prompt_version`, `generated_field_count`, and per-field provenance).

| Code field | Type | Required | Notes |
|---|---|---:|---|
| `name` | string | yes | Unique; assignment-column key |
| `code_id` | string | governed codebooks | All codes require IDs once any source ID exists |
| `definition` | string | operational codebook | Supplied content preserved |
| `inclusion_criteria` | list[string] | operational codebook | Supplied content preserved |
| `exclusion_criteria` | list[string] | operational codebook | Supplied content preserved |
| `example_verbatims` | list[string] | operational codebook | Supplied content preserved |
| `source` | string | no | Generated/user/split/merge provenance |
| `source_clusters` | list[integer] | generated non-catch-all | Cluster traceability |
| `estimated_response_count` | integer | generated | Sum of source cluster sizes |
| `parent_code`, `parent_code_id` | string | split-derived | Parent provenance |
| `merged_from`, `merged_from_ids` | list[string] | merge-derived | Source provenance |

## Coded dataset

The preprocessed columns remain. For each code named `N`:

| Field | Type | Required | Notes |
|---|---|---:|---|
| `code_N` | integer 0/1 | yes | Binary assignment |
| `conf_N` | float [0,1] | yes in working dataframe | Assignment confidence |
| `coding_result` | JSON string | yes | Normalized response-level result |
| `coding_status` | string | user path | `coded` or `catch_all` |
| `coding_prompt_version` | string | user path | Contract identifier |
| `codes_list` | list[string] | summary construction | Rebuilt from assignment columns |
| `code_ids_list` | list[string] | ID-governed summary | Rebuilt from codebook |
| `codes` | separator-joined string | yes after summary | Ordered assigned names |
| `code_ids` | separator-joined string | ID-governed | Ordered assigned IDs |
| `num_codes` | integer | yes after summary | Assignment count |
| `has_multi_label` | bool | yes after summary | `num_codes > 1` |
| `cluster` | integer | AI path | HDBSCAN label; `-1` is noise |
| `cluster_probability` | float | AI path | HDBSCAN membership strength |

## Export contracts

- Frequency columns: `code`, `count`, `percentage`; prepend `code_id` when IDs exist.
- Co-occurrence: square integer matrix, code names as rows and columns.
- Report workbook sheets in order: `Summary`, `Frequencies`, `Co-occurrence`,
  `Codebook`, `Coded Data`.
- Enhanced user codebook workbook: `Codebook` plus metadata/audit sheet as verified
  during Phase 4; JSON and XLSX names use
  `<file_stem>_codebook_s3_enhanced.{json,xlsx}`.
- Charts: `<file_stem>_frequencies.png` and
  `<file_stem>_cooccurrence.png`.
- AI-generated codebook: `<file_stem>_codebook_s2.json` as indented UTF-8 JSON.
- Removed audit: notebook default `removed_records.xlsx`.
- Usage log: `<file_stem>_llm_usage_log.csv` with timestamp, model, prompt,
  completion, total/cached tokens, approximate prompt characters, and system
  fingerprint when supplied by the API.

## Application state contract

The Streamlit session stores the validated `ProjectConfig`, source/config
fingerprints, preprocessed dataframe, one active alternative coding result, current
codebook/dataframe, refinement history, usage tracker, session timer, and deduplicated
output paths. `workflow_state` transitions clear dependent active results before new
work is promoted; saved files are retained for explicit download.
