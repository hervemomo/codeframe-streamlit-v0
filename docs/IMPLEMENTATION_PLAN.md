# Implementation Plan

## Objective

Convert `notebook_original.ipynb` into a modular, tested, CI/CD-ready Streamlit
application while preserving notebook behavior. Cross-cutting rules (parity,
architecture, testing, CI/CD, secrets) live in `AGENTS.md` — this document covers phase
scope, exit gates, and sequencing only.

## Status legend

`NOT STARTED` · `IN PROGRESS` · `COMPLETE` · `BLOCKED`

## Human Checkpoints

Execution pauses for explicit review at two points:

- **After Phase 1, before starting Phase 2.**
- **After Phase 3, before starting Phase 4.**

All other transitions proceed automatically once the exit gate is met.

---

## Phase 1 — Notebook Analysis, Architecture, Foundation, and CI

**Status:** NOT STARTED

### Scope

- Inventory every behaviorally relevant notebook cell or logical cell group: inputs,
  outputs, transformations, prompts, model parameters, dependencies, globals, side
  effects, fallbacks, reports, and exports.
- Record the checksum of `notebook_original.ipynb` as the baseline CI will enforce
  against for the rest of the project.
- Establish architecture, schemas, package skeleton, dependency config
  (`pyproject.toml`), pre-commit, and CI foundation (lint, type check, test, build).
- Populate the traceability matrix skeleton (rows may stay `Not yet implemented`).

### Exit gate

- `docs/NOTEBOOK_INVENTORY.md` covers every notebook cell/group with no gaps.
- `docs/TRACEABILITY_MATRIX.md` has one row per behaviorally relevant cell/group.
- Notebook checksum is recorded in `docs/PARITY_PLAN.md`.
- Package skeleton imports cleanly in a fresh `.venv`; no Streamlit imports in domain
  modules.
- CI workflow files are present and syntactically valid; foundational tests pass.
- `docs/IMPLEMENTATION_STATUS.md` reflects Phase 1 complete.

**→ Stop for human review before opening Phase 2.**

---

## Phase 2 — Preprocessing, Language, Audit, Reporting, and Exports

**Status:** NOT STARTED

### Scope

- Survey loading/validation (CSV/Excel), worksheet and column selection.
- Stable response IDs and metadata preservation.
- Cleaning, invalid/malformed filtering, duplicate handling, and removed-record audit.
- Language detection, confidence, status labels, and translation routing (mocked).
- Frequency, co-occurrence, workbook, chart, and export generation.

### Exit gate

- Deterministic unit tests pass for loading, cleaning, ID generation, and language
  routing.
- Translation and any remote calls are mocked in the default test suite.
- Reports/exports generate correctly into a temporary directory with expected schemas.
- Phase 2 parity results (row counts, IDs, statuses, routing, final text, report
  schemas) are recorded in `docs/PARITY_PLAN.md`.
- Traceability rows for Phase 2 cells are updated.

---

## Phase 3 — Embeddings, Clustering, AI Codebook, and Automated Coding

**Status:** NOT STARTED

### Scope

- Notebook-equivalent embeddings (model, batching, ordering).
- UMAP and HDBSCAN with notebook-equivalent parameters, seeds, and noise handling.
- Representative response selection.
- AI-generated codebook: prompt construction, schema, parsing, retries, fallback.
- Automated response coding: single/multi-label rules, max codes, catch-all,
  confidence normalization, validation.

### Exit gate

- Full pipeline (embeddings → clustering → codebook → coding) runs end to end against
  fixtures with all model calls mocked.
- Fixed-input parity checks against notebook output are recorded in
  `docs/PARITY_PLAN.md`.
- Deterministic pieces (clustering params, catch-all logic, confidence normalization)
  have direct unit tests; nondeterministic pieces (prompts, parsing, retries) have
  contract tests against mocked responses.
- Traceability rows for Phase 3 cells are updated.

**→ Stop for human review before opening Phase 4.**

---

## Phase 4 — User Codebook, Enrichment, Coding, Split, and Merge

**Status:** NOT STARTED

### Scope

- User codebook loading (CSV/XLS/XLSX), aliases, required/optional field validation,
  exact preservation of supplied values.
- Deterministic missing-ID generation and LLM enrichment of missing fields only.
- Catch-all behavior and batch/individual-fallback coding.
- Code splitting: parent selection, subcode config, optional AI suggestions, explicit
  confirmation, selective recoding.
- Code merging: explicit confirmation, deterministic OR-assignment, no LLM
  reclassification during merge.

### Exit gate

- User-codebook workflow runs end to end with mocked services.
- At least one split and one merge scenario are tested; unaffected assignments are
  verified unchanged.
- Stale-result prevention (cancelled/failed split or merge) is tested.
- Parity checks cover schema preservation, generated values, catch-all, split, merge,
  frequencies, co-occurrence, and exports.
- Traceability rows for Phase 4 cells are updated.

---

## Phase 5 — Streamlit UI, End-to-End Validation, and Deployment Readiness

**Status:** NOT STARTED

### Scope

- Session-state architecture and navigation across six pages: Project Setup,
  Preprocessing, AI Codebook, User Codebook, Refinement (Split/Merge tabs), Results &
  Downloads.
- Explicit run/apply/generate/split/merge actions; safe downstream invalidation on
  upstream change.
- End-to-end mocked workflows covering both coding paths.
- `docs/FINAL_PARITY_REPORT.md` classifying every parity requirement as `Verified`,
  `Equivalent with documented difference`, `Not verified`, or `Blocked`.
- `docs/CI_CD.md`, `docs/RELEASE_PROCESS.md`, `docs/ROLLBACK.md`.

### Exit gate

- All five phases complete; every traceability row resolved with no unexplained gaps.
- Full final non-live validation suite (per `AGENTS.md`) passes once against the final
  tree, including the notebook-checksum check.
- `docs/FINAL_PARITY_REPORT.md` is complete.
- Local setup/run instructions verified; unconfigured deployment/hosting settings
  clearly listed as manual steps.

---

## Dependency order

```text
Phase 1 → [review] → Phase 2 → Phase 3 → [review] → Phase 4 → Phase 5
```

Minimal cross-phase work is allowed only when documented in `docs/KNOWN_ISSUES.md` and
required to preserve architecture or unblock correct implementation of the active phase.
