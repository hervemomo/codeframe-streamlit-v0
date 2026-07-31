# Notebook Traceability Matrix

Status values: `MAPPED`, `IMPLEMENTED`, `PARITY VERIFIED`,
`EQUIVALENT WITH DOCUMENTED DIFFERENCE`, `BLOCKED`, `NOT APPLICABLE`.

| ID | Notebook cells | Stable behavior | Target module / callable | Test evidence | UI destination | Status | Issue |
|---|---|---|---|---|---|---|---|
| T01 | 0 | Top-level workflow, alternative coding paths, output contract | `workflow_state`, workflow services and result schemas | State and mocked UI workflow tests | Navigation / Results | PARITY VERIFIED | KI-001 |
| T02 | 1–3 | Environment and dependency contract | `pyproject.toml`, README | Clean install/build | Setup docs | IMPLEMENTED | |
| T03 | 4–5 | Project/language/model/coding/clustering defaults | `config` dataclasses | `test_config.py` | Project Setup | PARITY VERIFIED | |
| T04 | 6–7 | Imports, logging, session timer | `usage`, `workflow_state.elapsed_seconds`, UI bootstrap | Usage/state/UI tests | App shell | PARITY VERIFIED | |
| T05 | 8–9 | Empty responses, cleaning regexes, minimum words | `preprocessing` | `test_loaders_preprocessing.py` | Preprocessing | PARITY VERIFIED | |
| T06 | 10–11 L6–225 | Usage log, model-compatible kwargs, retries/fail-fast | `llm_client`, `usage` | `test_llm_client.py` | Run diagnostics | PARITY VERIFIED | |
| T07 | 10–11 L233–685 | IDs, normalized code entries, prompt format, summary columns, JSON I/O | `codebook`, `exports` | Codebook, user-codebook, split/merge tests | Codebook pages / Results | PARITY VERIFIED | |
| T08a | 10–11 L687–779 | JSON extraction and codebook validation | `codebook` | `test_codebook_generation.py` | Codebook pages | PARITY VERIFIED | |
| T08b | 10–11 L780–813 | Text cleaning and response validity | `preprocessing` | `test_loaders_preprocessing.py` | Preprocessing | PARITY VERIFIED | |
| T09 | 10–11 L815–998 | Split/merge-derived enrichment and fallbacks | `split_codes.enrich_derived_codebook` | `test_split_merge.py` | Refinement | PARITY VERIFIED | |
| T10 | 10–11 L1000–1232 | Missing-field-only user-codebook enhancement and preservation | `user_codebook.enhance_user_codebook_with_ai` | `test_user_codebook.py` | User Codebook | PARITY VERIFIED | |
| T11 | 12–13 | Frequency, co-occurrence, charts, five-sheet workbook | `reporting`, `exports` | `test_reporting_exports.py` | Results & Downloads | EQUIVALENT WITH DOCUMENTED DIFFERENCE | KI-002 |
| T12 | 14–15 | Preprocessing pipeline and methodology disclosures | `preprocessing`, UI help | Phase 2 parity fixtures | Preprocessing | PARITY VERIFIED | |
| T13 | 16–17 L1–112 | Load CSV/Excel, IDs, filtering, duplicate audit, language detection | `loaders`, `preprocessing`, `language` | Loader/preprocessing/language tests | Preprocessing | PARITY VERIFIED | |
| T14 | 16–17 L114–376 | Translation selection, batching, fallback, unresolved abort | `translation` | `test_translation.py` | Preprocessing | PARITY VERIFIED | |
| T15 | 18–19 | Explicit preprocessing orchestration | Phase 2 composable services | `test_phase2_integration.py` | Preprocessing action | PARITY VERIFIED | |
| T16 | 20–22 | Embeddings, UMAP, HDBSCAN, representatives, cluster sizes | `embeddings.generate_embeddings`, `clustering.discover_themes` | `test_embeddings_clustering.py` | AI Codebook | PARITY VERIFIED | KI-003 |
| T17 | 23–24 L1–192 | AI codebook prompt, retry, catch-all, cluster provenance | `codebook.generate_codebook` | `test_codebook_generation.py`, Phase 3 e2e | AI Codebook | PARITY VERIFIED | |
| T18 | 23–24 L194–577 | Deduped coding, normalization, catch-all/max-code rules | `ai_coding.code_batch`, `normalize_coding_result`, `apply_codes_to_dataframe` | `test_ai_coding.py`, Phase 3 e2e | AI Codebook | PARITY VERIFIED | |
| T19 | 25–31 | AI path mode gates and report orchestration | `ai_coding.run_ai_codebook_workflow` | `test_phase3_e2e.py` | AI Codebook | PARITY VERIFIED | |
| T20 | 32–34 | User codebook formats, preservation contract, defaults | `config.UserCodebookConfig`, `user_codebook` | `test_config.py`, `test_user_codebook.py` | User Codebook | PARITY VERIFIED | |
| T21 | 35–36 L1–215 | Load/alias/map, deterministic IDs, enhanced exports | `load_user_codebook`, `save_enhanced_codebook_excel` | `test_user_codebook.py` | User Codebook | PARITY VERIFIED | |
| T22 | 35–36 L218–585 | Part 2 prompt/parse/retry/batch/single application | `apply_enhanced_codebook_part2` and helpers | `test_user_codebook.py` | User Codebook | PARITY VERIFIED | |
| T23 | 37–41 | Manual path Part 1/2 orchestration and reports | `prepare_user_codebook`, `run_user_codebook_coding` | User-codebook e2e test | User Codebook | PARITY VERIFIED | |
| T24 | 42–48 | Manual result inspection and QA | `reporting`, results UI | Reporting and results-page AppTest | Results & Downloads | PARITY VERIFIED | |
| T25 | 49–51 | Split prerequisites/config validation/confirmation gate | `apply_confirmed_splits`, UI state | Split confirmation/stale tests | Refinement / Split | PARITY VERIFIED | |
| T26 | 52–53 | Split proposal/enrichment, selective recode, replacement, reports | `split_code`, `split_codes` | `test_split_merge.py` | Refinement / Split | PARITY VERIFIED | |
| T27 | 54–60 | Split execution flag and non-stale inspection | `SplitRunResult`, UI adapter | Split confirmation/stale tests | Refinement / Split | PARITY VERIFIED | |
| T28 | 61–63 | Merge prerequisites/config validation/confirmation gate | `apply_confirmed_merges`, UI state | Merge confirmation/stale tests | Refinement / Merge | PARITY VERIFIED | |
| T29 | 64–65 | Deterministic OR/max merge, provenance/enrichment, reports | `merge_codes`, `merge_code_groups` | `test_split_merge.py` | Refinement / Merge | PARITY VERIFIED | |
| T30 | 66–72 | Merge execution flag and non-stale inspection | `MergeRunResult`, UI adapter | Merge confirmation/stale tests | Refinement / Merge | PARITY VERIFIED | |
| T31 | 73–77 | Refinement chaining, usage and final run summaries | `workflow_state`, `usage`, results UI | State, mocked UI, and usage tests | Results & Downloads | PARITY VERIFIED | KI-003 |

## Completion checks

- [x] Every one of the 78 cells belongs to a stable mapped group.
- [x] Every mapping identifies a target module/callable category.
- [x] Every deterministic behavior has implemented test evidence.
- [x] Every user-facing behavior maps to an implemented UI destination.
- [x] Every current discrepancy links to `KNOWN_ISSUES.md`.
