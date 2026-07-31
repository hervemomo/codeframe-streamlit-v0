# Codeframe Streamlit

Codeframe converts the workflow in `original_notebook.ipynb` into a modular,
testable Streamlit application for coding open-ended survey responses.

The application implements both notebook workflows as alternatives:

- AI-generated codebook: embeddings → clustering → codebook generation → coding.
- User-supplied codebook: import/review/enrichment → coding.

Either coded result can then be refined through repeated confirmed splits and merges
before reports are downloaded.

## Local setup

PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
```

The project supports Python 3.12, matching the notebook kernel. Never place an
API key in source control. Copy `.env.example` to `.env` locally and provide the
key only when running an explicitly selected live workflow.

## Run the application

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open the local URL printed by Streamlit. Complete Project Setup and Preprocessing,
then use only the coding path selected in Project Setup. Model calls occur only after
an explicit run/apply action.

For Streamlit-managed secrets, create the ignored file
`.streamlit/secrets.toml`:

```toml
OPENAI_API_KEY = "your-key"
```

## Validation commands

```powershell
.\.venv\Scripts\python.exe scripts\check_notebook_baseline.py
.\.venv\Scripts\python.exe scripts\check_architecture.py
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy src tests scripts
.\.venv\Scripts\python.exe -m pytest -m "not live_api"
.\.venv\Scripts\python.exe scripts\smoke_streamlit.py
```

Deployment-provider settings are intentionally not claimed or configured. See
`docs/CI_CD.md`, `docs/RELEASE_PROCESS.md`, and `docs/ROLLBACK.md` for verified
repository automation and remaining manual controls.
