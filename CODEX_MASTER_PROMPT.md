# Codex Master Prompt: Convert `original_notebook.ipynb` into a Streamlit Application

## Mission

You are the implementation agent for this repository. Convert `original_notebook.ipynb`
into a modular, testable, CI/CD-ready Streamlit application for coding open-ended survey
responses, while preserving its behavior exactly (see parity rules below).

**`AGENTS.md` already exists in this repository and is authoritative.** It contains the
durable rules for architecture, parity, testing, environment, CI/CD, secrets, and
documentation. Read it in full before doing anything else, and re-read it at the start of
every phase, after any context compaction, and whenever execution feels uncertain. If
notebook inspection reveals `AGENTS.md` is wrong or incomplete, propose a targeted edit to
it rather than rewriting it — do not regenerate it from scratch.

This prompt covers orchestration only: what to build, in what order, and when to pause.

## First Actions (before writing any code)

1. Inspect the repo tree, existing source, tests, workflows, docs, and Git status/diff.
2. Read `AGENTS.md` in full.
3. Read or create `docs/IMPLEMENTATION_PLAN.md` — write the five phases below into it in
   detail, adapted to what notebook inspection actually finds, along with
   `docs/IMPLEMENTATION_STATUS.md`, `docs/TRACEABILITY_MATRIX.md`,
   `docs/NOTEBOOK_INVENTORY.md`, `docs/WORKFLOW_MAP.md`, `docs/DATA_SCHEMAS.md`,
   `docs/PARITY_PLAN.md`, and `docs/KNOWN_ISSUES.md` if they don't already exist.
4. Preserve useful existing work rather than replacing it unnecessarily.

## Execution Loop

```text
FOR each phase:
    1. Re-read AGENTS.md and the docs/ files listed above.
    2. Inspect the relevant notebook cells and current implementation.
    3. Review Git status/diff, dependencies, existing tests.
    4. Implement the smallest coherent set of changes; commit per unit.
    5. Run the narrowest useful validation (see AGENTS.md § Testing Strategy).
    6. Repeat 4–5 until phase scope is complete.
    7. Run the phase exit gate for this phase (docs/IMPLEMENTATION_PLAN.md).
    8. Update status, traceability, parity, and known-issue docs.
    9. Post the phase completion report (AGENTS.md § Required Completion Report).
   10. If this phase is followed by a checkpoint phase (see below), stop and wait for
       review. Otherwise continue automatically to the next phase.
```

## Human Checkpoints

Per `AGENTS.md`, stop and wait for explicit review before starting **Phase 2** and
before starting **Phase 4** — these follow the points (architecture, AI-codebook
pipeline) where decisions are expensive to unwind. All other transitions proceed
automatically without asking for approval.

## Five Phases (overview — full scope lives in `docs/IMPLEMENTATION_PLAN.md`)

1. **Foundation** — notebook inventory, traceability matrix skeleton, architecture,
   package skeleton, `AGENTS.md` review, CI foundation.
   *[checkpoint after this phase]*
2. **Preprocessing & Reporting** — loading, cleaning, language/translation routing,
   frequency/co-occurrence, exports.
3. **AI-Generated Codebook** — embeddings → UMAP → HDBSCAN → LLM codebook generation →
   LLM response coding, fully mocked in tests.
   *[checkpoint after this phase]*
4. **User Codebook, Split, Merge** — user-supplied codebook ingestion, coding, split
   with confirmation, merge with deterministic OR-assignment.
5. **Streamlit UI & Release Readiness** — six-page UI (Setup, Preprocessing, AI
   Codebook, User Codebook, Refinement, Results), mocked end-to-end tests, final parity
   report, CI/CD/release/rollback docs, deployment readiness.

## Definition of Done

See `AGENTS.md` § Definition of Done. Do not mark the project complete while any
required check is failing, while any notebook cell remains unmapped in the traceability
matrix, or while `original_notebook.ipynb` has diverged from its Phase-1 checksum.

## Final Report

After Phase 5's exit gate and the final full validation run, provide one report
containing: final project structure; workflows delivered; docs created; test/coverage/
lint/type/security/build/smoke results; parity summary and documented differences; local
run instructions; deployment readiness and remaining manual steps.
