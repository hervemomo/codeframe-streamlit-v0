# Notebook Parity Plan

## Purpose

Verify that the extracted package and Streamlit application preserve notebook behavior for equivalent inputs, configuration, and mocked external responses.

## Comparison principles

- Compare deterministic transformations exactly.
- Mock LLM, translation, and embedding services where needed.
- Compare request construction, parsing, validation, and downstream transformations for nondeterministic operations.
- Never claim exact live-LLM wording parity.

## Required parity areas

| Area | Baseline fixture | Comparison | Tolerance | Status | Evidence |
|---|---|---|---|---|---|
| Loading | TBD | Row count, ordering, columns | Exact | NOT STARTED | |
| Preprocessing | TBD | Cleaned text and exclusions | Exact | NOT STARTED | |
| Language routing | TBD | Status/confidence decisions | Notebook-defined | NOT STARTED | |
| Translation | Fixed mocked output | Routing and final columns | Exact | NOT STARTED | |
| Embeddings | Fixed mocked vectors | Input order and shapes | Exact | NOT STARTED | |
| UMAP/HDBSCAN | Fixed seed/input | Labels and shapes | Notebook-defined | NOT STARTED | |
| Codebook generation | Fixed mocked response | Parsing/schema/order | Exact | NOT STARTED | |
| Coding | Fixed mocked response | Assignments/normalization | Exact | NOT STARTED | |
| Split | Fixture run | Columns, assignments, codebook | Exact | NOT STARTED | |
| Merge | Fixture run | OR result, columns, codebook | Exact | NOT STARTED | |
| Reporting | Fixture run | Tables, sheets, filenames | Exact | NOT STARTED | |

## Discrepancy protocol

When exact parity cannot be achieved:

1. re-inspect the notebook;
2. document the issue in `KNOWN_ISSUES.md`;
3. implement the closest safe equivalent;
4. add a regression test;
5. update the traceability matrix;
6. classify the result honestly.
