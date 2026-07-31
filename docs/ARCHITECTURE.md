# Architecture

## Dependency direction

```text
Streamlit pages and session-state adapter
                  ↓
       workflow/application services
                  ↓
  deterministic domain modules + schemas
                  ↓
 injected OpenAI clients, tabular files, and explicit output destinations
```

Only the root `app.py`, `pages/`, and `ui/` presentation layer may import Streamlit
or access `st.session_state`. The
`src/codeframe` package remains UI-agnostic and performs no remote call, credential
read, or file write at import time.

## Package boundaries

| Module | Notebook responsibility | Phase |
|---|---|---:|
| `config` | Typed replacement for cell 5 globals | 1 |
| `schemas`, `exceptions` | Shared codebook/result contracts and safe errors | 1–4 |
| `parity` | Immutable source-notebook baseline | 1 |
| `loaders`, `preprocessing` | Survey load, IDs, cleaning, invalid/duplicate audit | 2 |
| `language`, `translation` | Lingua status/confidence and translation routing | 2 |
| `reporting`, `exports`, `paths` | Frequency/co-occurrence, charts, workbooks, destinations | 2 |
| `llm_client`, `usage` | Injected model protocol, retry, parameter compatibility, usage | 3 |
| `embeddings`, `clustering` | Embeddings, UMAP, HDBSCAN, representative selection | 3 |
| `codebook`, `ai_coding` | Codebook generation, normalization, automated coding | 3 |
| `user_codebook` | Import, preservation, enrichment, Part 2 coding | 4 |
| `split_codes`, `merge_codes` | Confirmed refinement transformations | 4 |
| `workflow_state` | Framework-neutral state transitions, invalidation, outputs | 5 |
| Streamlit `app.py`, `pages/`, `ui/` | Explicit actions, integrations, downloads | 5 |

## Service boundaries

- External model calls accept a client/protocol explicitly.
- Tabular readers accept a file-like object or path and explicit sheet/column mapping.
- Every writer accepts an explicit destination or `output_dir`.
- Workflow results are returned, not stored in notebook-style globals.
- `workflow_state` owns testable transitions while the UI owns the mutable session.
- Split and merge services are pure with respect to UI confirmation: the UI must
  confirm first, while the service receives an already-authorized request.

## State model

```text
ProjectConfig
   └─ SurveySource → PreprocessedRun
                         ├─ AICodingRun
                         └─ UserCodebookRun
                                ↓
                         RefinementRun*
                                ↓
                         ReportBundle
```

Project and survey fingerprints avoid retaining an extra copy of source text.
Changing project settings invalidates preprocessing and all descendants. Re-running
preprocessing invalidates coding/refinement state. Preparing a new user codebook
invalidates coding/refinement state but preserves preprocessing. Existing files remain
available for download, while no stale result remains active.

## Architectural decisions

| Decision | Rationale | Consequence |
|---|---|---|
| Python 3.12 package under `src/` | Matches notebook kernel and prevents accidental root imports | Clean editable/install builds |
| Frozen dataclass configuration | Replaces mutable globals with explicit validated inputs | Configuration changes create new runs |
| TypedDict wire schemas | Preserves notebook dictionaries and JSON compatibility | No forced schema transformation |
| Inject clients, never read keys in domain modules | Enables mocked tests and safe imports | UI/bootstrap creates live clients |
| Preserve per-code name-based columns | Required for notebook parity | Duplicate code names remain invalid |
| Byte-level notebook checksum | Detects any source-of-truth drift | CI fails closed |
| Keep `pyproject.toml` authoritative | Prevents dependency divergence | `requirements.txt` delegates to the project |
| Lazy workflow imports on dependent pages | Fast safe prerequisite navigation | Scientific stack loads only when usable |
