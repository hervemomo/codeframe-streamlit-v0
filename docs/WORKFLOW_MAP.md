# Workflow Map

## Intended top-level flow

```text
Survey upload
→ preprocessing and language normalization
→ AI-generated codebook coding OR user-supplied codebook coding
→ optional code splitting and merging
→ results, reports, and downloads
```

Replace or expand this map during Phase 1 based on the notebook.

## State transitions

| From state | Action | To state | Invalidates | Notes |
|---|---|---|---|---|
| No project | Configure project | Project configured | N/A | |
| Project configured | Upload and preprocess survey | Preprocessed | Downstream coding | |
| Preprocessed | Run AI coding | AI-coded result | Prior active result as applicable | |
| Preprocessed | Apply user codebook | User-codebook result | Prior active result as applicable | |
| Coded result | Split codes | New refined run | None; preserve parent run | |
| Coded result | Merge codes | New refined run | None; preserve parent run | |

## Detailed diagrams

Populate with notebook-verified workflow diagrams during Phase 1.
