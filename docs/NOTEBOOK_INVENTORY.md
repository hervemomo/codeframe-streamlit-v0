# Notebook Inventory

## Notebook metadata

- File: `original_notebook.ipynb`
- Format: nbformat 4.5
- Cells: 78 total; 32 code and 46 Markdown
- Kernel: `.venv (3.12.10)`
- Python assumption: 3.12
- SHA-256: `202eefa5db6c0f39d72e63f1401e1c30edc821e83326483c92c1721b72c626f8`
- Primary workflow: survey preprocessing followed by either AI-generated-codebook
  coding or user-codebook coding, then optional split/merge refinement and reports
- External services: OpenAI Chat Completions and Embeddings, always invoked explicitly
- Required live environment variable: `OPENAI_API_KEY`
- Local files read by the configured example: survey workbook and optional codebook
- Files written: removed-record audit, JSON/Excel codebooks, five-sheet report
  workbooks, frequency charts, and co-occurrence heatmaps

Cell outputs were inspected for output type and side effects. They are not reproduced
here because the committed example workbook may contain survey responses.

## Cell and section inventory

| Order | Cell reference | Responsibility | Inputs / prerequisites | Outputs / mutations | External calls / files | Notes |
|---:|---|---|---|---|---|---|
| 1 | 0 | Notebook usage, two alternative paths, `(df, codebook)` contract, output contract | None | User instructions | None | Maps all top-level workflow branches |
| 2 | 1–3 | Section 0 setup and dependency list | Python environment | Imported runtime dependencies | Package installation when manually run | Dependency cell is installation guidance, not domain behavior |
| 3 | 4–5 | Project, language, model, cost, reliability, and clustering configuration | `.env`, survey path/question/context | Notebook globals; derived `TEXT_COL` and filenames | Reads `OPENAI_API_KEY` via dotenv | Defaults captured in `codeframe.config` |
| 4 | 6–7 | Imports, logging, warning policy, session start time | Installed dependencies | Logger and `SESSION_START_TIME` | None at import beyond library imports | Package extraction must avoid import-time remote calls |
| 5 | 8–9 | Invalid-response vocabulary and cleaning regexes | None | Constants | None | French/English junk phrases; two-word default |
| 6 | 10–11 L6–225 | Usage logging, Chat Completions parameter compatibility, retry/fail-fast wrapper | Injected OpenAI client, model/messages | Usage records and response | Chat Completions | Retries transient 429/5xx/timeouts; fails fast on quota/auth |
| 7 | 10–11 L233–813 | Code IDs, codebook normalization, prompt rendering, JSON extraction, validation, text cleaning | Codebook/values/text | Normalized structures and text | JSON codebook read/write | Catch-all bilingual; stable collision-checked IDs |
| 8 | 10–11 L815–1232 | Split/merge enrichment and user-codebook missing-field patch workflow | Injected client and incomplete codebook | Completed codebook plus provenance metadata | Chat Completions | Supplied fields are asserted unchanged |
| 9 | 12–13 | Frequencies, co-occurrence, charts, and five-sheet Excel reports | Coded dataframe/codebook/output dir | Tables and output-path mapping | PNG and XLSX writes | Writers currently use global `FILE_STEM`; extraction will make it explicit |
| 10 | 14–15 | Section 1 pipeline and methodology caveats | Raw survey | Documented expectations | `removed_records.xlsx` | Exact duplicates and one-word responses are removed |
| 11 | 16–17 L1–112 | Survey loading, stable IDs, cleaning partition, Lingua detection, audit | CSV/XLS/XLSX, selected sheet/text/ID | Retained dataframe; invalid and duplicate audits | Reads survey; writes two-sheet audit | IDs are assigned after blank-row removal when no ID column is selected |
| 12 | 16–17 L114–376 | Translation batch, source routing, single-item fallback, unresolved failure | Preprocessed dataframe and injected client | `translation_status`, `final_text_<target>` | Chat Completions | All non-target languages by default; unresolved rows abort |
| 13 | 18–19 | Section 1 run orchestration | API key and configured survey | `client`, `df_raw`, `df_preprocessed` | OpenAI client; audit file | Explicit execution cell |
| 14 | 20–22 | Embeddings, UMAP, HDBSCAN, representative samples, discovery orchestration | At least 10 preprocessed responses | Cluster labels/probabilities/representatives/sizes | Embeddings API | Fixed UMAP seed 42; noise `-1` excluded from codebook |
| 15 | 23–24 L1–192 | AI codebook prompt, JSON retry, validation, catch-all, cluster provenance | Representatives and cluster sizes | Generated codebook | Chat Completions | Token-budget retry on truncated/invalid JSON |
| 16 | 23–24 L194–577 | Deduplicated batch coding and authoritative assignment normalization | Texts/codebook/client | `code_*`, `conf_*`, summaries, raw result | Chat Completions | Max-code cap, exact names, exclusive catch-all at confidence 0.50 |
| 17 | 25–31 | AI path run gates: cluster, generate, code, report | `CODING_MODE="ai"` and preprocessing | `df_s2`, `codebook_s2`, current pair, reports | API calls and report files | Skips automatically in manual mode |
| 18 | 32–34 | User-codebook contract and Section 3 configuration | CSV/XLS/XLSX codebook | Paths, mappings, batch/retry defaults | None | Other input types rejected |
| 19 | 35–36 L1–215 | User-codebook load/preserve, deterministic missing IDs, JSON/XLSX export | Configured tabular codebook | Normalized codebook and audit metadata | Reads CSV/XLS/XLSX; writes JSON/XLSX | Auto-detects documented column aliases |
| 20 | 35–36 L218–585 | Part 2 prompt, parse/retry, batch/single fallback, assignment application | Enhanced codebook, context/question, responses | Coded dataframe and status/version fields | Chat Completions | Only completed codebooks with catch-all accepted |
| 21 | 37–41 | Manual path Part 1 and Part 2 orchestration | `CODING_MODE="manual"` | Enhanced codebook, `df_s3`, current pair, reports | API and files | Part 1 does not require survey responses |
| 22 | 42–48 | Manual-path result inspection and QA | Completed Part 2 | Frequencies, samples, multi-label/uncoded diagnostics | Display only | Skips when manual Part 2 did not run |
| 23 | 49–51 | Split contract, configs, active-code validation, confirmation | Current coded pair | No mutation unless explicitly confirmed | None | Default configs empty and confirmation false |
| 24 | 52–53 | Single/sequential split, optional proposal/enrichment, affected-row recoding | Confirmed parent/config and client | Updated pair and reports | Chat Completions and report files | Parent replaced by default; only affected rows recoded |
| 25 | 54–60 | Split run and non-stale inspection | Confirmed non-empty configs | Current pair, run flag, QA tables | API/files through split service | Inspect cells explicitly say skipped after no run |
| 26 | 61–63 | Merge contract, configs, source validation, confirmation | Current coded pair | No mutation unless explicitly confirmed | None | Default configs empty and confirmation false |
| 27 | 64–65 | Single/sequential merge and optional metadata enrichment | Confirmed distinct source groups | OR-merged assignments, updated codebook/reports | Optional Chat Completions; report files | No LLM reclassification; max source assignment/confidence |
| 28 | 66–72 | Merge run and non-stale inspection | Confirmed non-empty configs | Current pair, run flag, QA tables | API/files through merge service | Inspect cells explicitly say skipped after no run |
| 29 | 73 | Refinement chaining contract | Current pair | Documentation | None | Split and merge can be repeated in either order |
| 30 | 74–75 | Token/cost summary | Session usage log | Per-model and total usage displays | Display only | Pricing/cost depends on logged fields |
| 31 | 76–77 | Final run summary and output discovery | Current pair and known output globals | Response/code/cost/time/file summary | Reads output existence | Does not generate new analysis |

## Extracted callable inventory

- Shared/configuration: 45 helpers covering API retry/usage, IDs, codebook schemas,
  JSON extraction, cleaning, validation, enrichment, and summary columns.
- Preprocessing/translation: 10 functions plus `TranslationUnresolvedError`.
- Reporting: 5 functions.
- AI discovery/coding: 18 functions.
- User-codebook workflow: 12 functions.
- Split: `split_code`, `split_codes`.
- Merge: `merge_codes`, `merge_code_groups`.

The exact callable-to-module mapping is maintained in `TRACEABILITY_MATRIX.md`.

## No-silent-omissions confirmation

- [x] All 78 cells were inspected.
- [x] Markdown instructions that affect behavior were captured.
- [x] Disabled, optional, confirmation, retry, and fallback paths were captured.
- [x] Reports, exports, prompts, usage diagnostics, and run summaries were captured.
