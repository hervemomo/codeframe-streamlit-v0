# Known Issues and Documented Differences

## Status values

`OPEN` · `RESOLVED` · `ACCEPTED DIFFERENCE` · `BLOCKED`

| ID | Status | Notebook section | Description | Impact | Safe equivalent / resolution | Regression test | Traceability |
|---|---|---|---|---|---|---|---|
| KI-001 | RESOLVED | Repository governance | Scaffold named the source `notebook_original.ipynb`, but the committed file is `original_notebook.ipynb`. | Baseline and CI could have checked a nonexistent path. | Targeted filename correction in governance/docs; no notebook rename or byte change. | `test_notebook_matches_phase_one_baseline` | T01 |
| KI-002 | ACCEPTED DIFFERENCE | Cell 13 charts | The modular reporter uses Matplotlib's direct `Figure` plus an Agg canvas instead of stateful `pyplot`, because the server/CI environment has no Tk runtime. | Figure lifecycle/backend selection differs; chart data, labels, dimensions, DPI, filenames, and save options are preserved. | Headless deterministic rendering with the same plotting parameters. | `test_generate_reports_matches_workbook_and_chart_contract` | T11 |
| KI-003 | RESOLVED | Cells 20, 73–77 | Phase 5 integration review found that the AI workflow's default theme-discovery call did not forward a non-default embedding model or shared usage tracker. | A customized model could have been ignored and embedding tokens omitted from the final session usage summary. | `run_ai_codebook_workflow` now forwards both through `discover_themes`; defaults remain backward compatible. | `test_discover_themes_uses_configured_embedding_model_and_tracker` | T16, T31 |

## Notebook behaviors requiring deliberate parity

These are not current implementation differences:

- Exact duplicate cleaned responses are removed, so percentages use unique responses.
- The two-word default removes otherwise meaningful one-word answers.
- Report chart filenames receive `file_stem` explicitly and preserve the notebook name.
- User-codebook IDs are governed as a complete set: once any ID exists, every code
  requires one.

## Rules

- Never hide a discrepancy.
- Every accepted difference must have a regression test where technically possible.
- Every issue links back to the traceability matrix.
