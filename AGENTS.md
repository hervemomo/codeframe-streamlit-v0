# AGENTS.md

This file is the durable rulebook for this repository. It is read automatically at the
start of every task, at every phase boundary, and after any context compaction. If a
master-prompt instruction and this file ever disagree, this file wins.

Procedural detail (phase-by-phase scope, exit gates, task lists) lives in
`docs/IMPLEMENTATION_PLAN.md`, not here. Keep this file limited to rules that must hold
true for the entire project regardless of which phase is active.

## Mission

Convert `notebook_original.ipynb` into a modular, testable, CI/CD-ready Streamlit
application for coding open-ended survey responses, without changing its behavior.

```text
Survey upload
→ preprocessing and language normalization
→ AI-generated codebook coding OR user-supplied codebook coding
→ optional code splitting and merging
→ reporting and downloads
```

The AI-generated and user-supplied codebook paths are alternatives. Never require a user
to run both.

## Source of Truth and No Silent Omissions

`notebook_original.ipynb` is the behavioral baseline until parity is verified.

- Extract **all** functionality, transformations, validations, fallbacks, diagnostics,
  reports, charts, files, and outputs from the notebook — including sections not
  mentioned in any task prompt.
- Never omit, compress, merge, simplify, or replace notebook behavior unless the
  difference is documented in `docs/KNOWN_ISSUES.md` and covered by a regression test.
- Re-inspect the relevant notebook cells whenever behavior is ambiguous, incomplete,
  contradictory, or unclear. Never invent behavior from module names, comments, or
  memory of the notebook.
- Never overwrite or substantially modify `notebook_original.ipynb`. CI enforces this
  (see CI/CD section) — do not rely on prompt discipline alone.

## Parity Rules

For equivalent inputs, configuration, and mocked external-model responses, preserve the
notebook's row counts/ordering/IDs, cleaning and validation rules, language detection and
translation routing, column names/types/schemas, prompts/parsing/retry/fallback behavior,
codebook fields and ordering, coding limits and catch-all rules, split/merge behavior,
frequency and co-occurrence calculations, and workbook/export schemas and defaults.

If exact reproduction is impossible:

1. document the discrepancy in `docs/KNOWN_ISSUES.md`;
2. link it from `docs/TRACEABILITY_MATRIX.md`;
3. implement the closest safe equivalent;
4. add a regression test capturing the difference;
5. classify it as `Equivalent with documented difference` or `Blocked` — never claim
   `Parity verified` without evidence.

## Architecture

Dependency direction is fixed:

```text
Streamlit UI → reusable Python package → external services, files, models, reporting
```

The reusable package must never import Streamlit, touch `st.session_state`, depend on
notebook globals or cell order, hard-code output directories, read credentials at import
time, or make remote API calls at import time. Use typed configs, explicit schemas,
dependency injection for external clients, and pure functions where practical. All
file-writing functions accept an explicit `output_dir`.

Suggested module layout (adapt to what the notebook actually needs — don't force this if
inspection shows a clearer split):

```text
src/codeframe/
├── config.py        ├── llm_client.py     ├── codebook.py      ├── split_codes.py
├── schemas.py        ├── loaders.py        ├── ai_coding.py      ├── merge_codes.py
├── exceptions.py     ├── preprocessing.py  ├── user_codebook.py ├── reporting.py
├── validation.py      ├── language.py       ├── embeddings.py    ├── exports.py
├── usage.py            ├── translation.py    ├── clustering.py    └── paths.py
```

## Scope and Diff Discipline

Minimize the diff. Do not reformat, rename, reorganize, or refactor unrelated files.
Every changed file must be necessary for the active phase, its tests, required
documentation, CI/CD support, or a discovered defect blocking correct implementation. A
minimal cross-phase change is allowed only to preserve architecture, unblock the active
phase, or repair a discovered defect — document it and update the affected phase status.

## Git and Review Checkpoints

- Commit at the end of each coherent implementation unit with a descriptive message.
- Open work for a phase on its own branch (`phase-1-foundation`, `phase-2-preprocessing`,
  etc.) rather than committing directly to `main`.
- **Stop for human review before starting Phase 2 and before starting Phase 4.** These
  are the points where architecture (Phase 1) and the AI-codebook pipeline (Phase 3)
  lock in decisions that are expensive to unwind later. Post the phase completion report
  and wait; do not open the next phase's branch until reviewed.
- All other phase transitions may proceed automatically per the execution loop in the
  master prompt.
- If a single phase exceeds roughly 150 tool calls or a full working session without
  reaching its exit gate, stop and report status rather than continuing indefinitely.

## Genuine Blockers

A genuine blocker exists only when work depends on unavailable credentials, an
unavailable proprietary service, a missing essential source file, unsupported system
access, or a required product decision with no safe backward-compatible default.
Failing tests, implementation difficulty, task length, an ambiguous notebook cell, or a
resolvable dependency conflict are **not** blockers by themselves — investigate,
re-inspect, document, and continue.

## Required Project Documents

Maintain throughout development:

```text
docs/
├── NOTEBOOK_INVENTORY.md   ├── TRACEABILITY_MATRIX.md  ├── CI_CD.md
├── WORKFLOW_MAP.md         ├── PARITY_PLAN.md          ├── RELEASE_PROCESS.md
├── ARCHITECTURE.md         ├── KNOWN_ISSUES.md         ├── ROLLBACK.md
├── DATA_SCHEMAS.md         ├── IMPLEMENTATION_PLAN.md  └── FINAL_PARITY_REPORT.md
└── IMPLEMENTATION_STATUS.md
```

`docs/TRACEABILITY_MATRIX.md` maps every behaviorally relevant notebook cell (or cell
group) to: notebook location, behavior, target module/function, tests, Streamlit
page/component, parity status, and known issues. No relevant cell may be unmapped at
completion.

Update only the documents affected by a change. At minimum, each phase must update
`IMPLEMENTATION_STATUS.md`, `TRACEABILITY_MATRIX.md`, and `KNOWN_ISSUES.md` /
`PARITY_PLAN.md` when discrepancies or parity checks occur.

## Testing Strategy

Use the narrowest useful validation during implementation: the directly affected test
first, dependent-module tests when a shared contract changes, phase-level tests at the
phase exit gate. Don't repeatedly run the full suite after small isolated edits — broaden
scope when changes touch shared schemas, config, LLM parsing, or CI configuration.

Markers: `unit`, `integration`, `parity`, `e2e`, `slow`, `live_api`. Default automated
tests never call live external APIs — mock OpenAI, translation, and embedding calls.
Live-API tests are optional, explicitly selected, and excluded from normal CI.

Test behavior, not line execution. Directly test deterministic logic (ID generation,
preprocessing, filtering, catch-all/exclusivity, split/merge transformations, frequency
and co-occurrence math, export schemas). For nondeterministic services, test prompt
construction, payloads, response parsing, malformed-response handling, retries,
fallbacks. Use temporary directories for all test writes.

**Before declaring the whole project complete**, run the full non-live validation suite
exactly once against the final tree: formatting, lint, type check, unit + integration +
mocked e2e tests, coverage gate (80% on core deterministic logic unless documented
otherwise), security scan, dependency audit, package build, Streamlit startup smoke
test, and final notebook-parity checks. Do not declare completion with failing required
checks.

## Python Environment

Project-local `.venv`; never use the global interpreter for dev, test, lint, type-check,
notebook execution, or Streamlit. Create it if missing; reuse it otherwise. Reinstall
dependencies only when `.venv` is missing/corrupt, dependency files changed, or an
import is missing.

```bash
python3 -m venv .venv && ./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -e ".[dev]"
./.venv/bin/python -m pytest
```
```powershell
py -m venv .venv; .\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
```

`pyproject.toml` is the authoritative dependency/tool config. Before choosing commands,
check `pyproject.toml`, existing `requirements*.txt`, README, CI workflows, and repo
scripts — commands in any prompt are examples only, not overrides.

## Streamlit Rules

`st.session_state` is used only in the Streamlit layer. Expensive operations
(translation, embeddings, UMAP/HDBSCAN, LLM codebook generation, response coding, split
recoding, report generation) run only on explicit user action, never on an ordinary
rerun. Changing an upstream input invalidates only its dependent downstream state, with a
warning before discarding completed results. Splitting and merging require explicit
confirmation and must never show stale results after a cancelled/failed operation. No
large tables or full codebooks in the sidebar.

## CI/CD Requirements

Established from Phase 1, not added at the end. One authoritative `pyproject.toml` with
runtime/dev/test/live-test dependency groups. Configure Ruff, mypy/Pyright, pytest +
pytest-cov, Bandit, pip-audit, pre-commit, GitHub Actions.

CI runs on PRs to `develop`/`main`, pushes to those branches, and manual dispatch. CI
validates: clean install, formatting, lint, type check, unit + integration tests,
coverage, security, dependency audit, package build, module imports, absence of
Streamlit imports in domain modules, Streamlit startup smoke test — **and a checksum
check that `notebook_original.ipynb` is byte-identical to its Phase-1 baseline.** Fail
the build if it differs.

Never claim branch protection, GitHub environments, secrets, required reviewers, or
hosted deployments are configured unless verified through available tools. Document any
manual repository-level configuration clearly.

## Secrets and Data Safety

Never commit API keys, tokens, passwords, private endpoints, production secrets,
sensitive survey responses, generated client reports, or local `.env` files. Use
environment variables, `.env.example`, and platform secret management. Ensure logs, test
artifacts, and exception messages never expose credentials or survey content.

## Command Discovery

Before running commands, inspect `AGENTS.md`, `pyproject.toml`, existing workflows,
repo scripts, README, and venv conventions. Use the repository's authoritative commands;
treat commands in any prompt as examples unless they match the repo's actual config. Use
PowerShell-compatible commands on Windows-oriented repos.

## Definition of Done

The project is complete only when: all five phases are complete; every behaviorally
relevant notebook cell is mapped with no unexplained gaps; all workflows run with mocked
services; the final non-live validation suite passes; the notebook is unchanged (verified
by CI checksum); reusable modules never import Streamlit; parity results and known
differences are documented in `FINAL_PARITY_REPORT.md`; local setup/run instructions are
verified; and deployment requirements plus any unconfigured external settings are
clearly documented as manual steps.

## Required Completion Report

At the end of each phase, report: active phase; files created/changed; functionality
implemented; tests run and why; test/coverage/lint/type-check/security results; notebook
parity results; traceability updates; known issues; cross-phase changes; recommended
commit message and PR title; next phase (and whether it requires the human checkpoint
above). At final completion, include the complete validation and parity summary.
