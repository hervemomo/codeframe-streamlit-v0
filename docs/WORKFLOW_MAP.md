# Workflow Map

## Notebook-verified workflow

```text
Project configuration
        ↓
CSV/XLS/XLSX survey → blank removal → stable IDs → cleaning
        ↓
invalid + exact-duplicate audit → language detection → translation routing
        ↓
                 PreprocessedRun
                  /           \
      AI-generated path       User-codebook path
 embeddings → UMAP →          load → preserve → enrich missing only
 HDBSCAN → codebook →         → catch-all → code responses
 code responses                    /
                  \               /
                    CodedRun
                       ↓
          [confirmed split and/or merge]*
                       ↓
      frequencies + co-occurrence + workbook + charts
```

The AI-generated and user-supplied paths are alternatives. Part 1 of the user
codebook workflow may run before survey preprocessing because it uses no responses.

## State transitions and invalidation

| From | Explicit action | To | Invalidates |
|---|---|---|---|
| No project | Save project settings | Configured | Nothing |
| Configured | Load and preprocess survey | Preprocessed | Both coding paths and all descendants |
| Preprocessed | Run AI codebook workflow | AI-coded | Prior active coding/refinement/results |
| Preprocessed | Run user-codebook coding | User-coded | Prior active coding/refinement/results |
| User codebook source | Enhance missing fields | Enhanced codebook | User coding/refinement/results |
| Coded/refined | Confirm and apply split | New refined run | Current displayed reports/downloads |
| Coded/refined | Confirm and apply merge | New refined run | Current displayed reports/downloads |
| Coded/refined | Generate reports | Report bundle | Prior report bundle only |

## Failure and cancellation rules

- Translation failure leaves no committed preprocessed result.
- Malformed batch translation retries individual rows; any unresolved row aborts.
- Coding batch parse failures retry only the affected items individually.
- Split/merge configs default empty and confirmations default false.
- A skipped, cancelled, or failed refinement never exposes stale “new” results.
- Merge assignment is deterministic OR/max and never uses LLM reclassification.

## Implemented six-page UI

1. Project Setup
2. Preprocessing
3. AI Codebook
4. User Codebook
5. Refinement (Split and Merge tabs)
6. Results & Downloads

The application uses `workflow_state` for deterministic invalidation, first-seen output
deduplication, refinement history, usage summaries, and elapsed session time. OpenAI
clients are created only inside explicit actions, and the domain package never reads
credentials.
