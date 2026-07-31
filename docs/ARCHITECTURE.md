# Architecture

Populate and confirm during Phase 1.

## Required dependency direction

```text
Streamlit UI
    ↓
Reusable Python package
    ↓
External services, files, models, and reporting
```

## Non-negotiable constraints

- Reusable modules do not import Streamlit.
- Domain logic does not access `st.session_state`.
- No notebook globals or cell-order dependencies.
- External services are injected behind testable interfaces.
- File writers accept explicit destinations or `output_dir`.
- No credentials are read or remote calls made at import time.

## Proposed package boundaries

Codex must replace this section with notebook-informed architecture.

## Architectural decisions

| Decision | Rationale | Alternatives considered | Consequences |
|---|---|---|---|
| | | | |
