"""Survey loading with notebook-equivalent row and identifier behavior."""

import logging
from pathlib import Path

import pandas as pd

type PathLike = str | Path

logger = logging.getLogger(__name__)


def load_survey_data(
    filepath: PathLike,
    text_column: str,
    sheet_name: str | int = 0,
    id_column: str | None = None,
) -> pd.DataFrame:
    """Load CSV/Excel responses, drop blank text rows, and assign stable IDs.

    This preserves notebook cell 17 exactly: Excel is selected only for ``.xls``
    and ``.xlsx`` paths; every other suffix is read as CSV. When no usable ID
    column is selected, IDs are assigned from one after blank-row removal.
    """

    path = Path(filepath)
    if path.suffix.lower() in {".xlsx", ".xls"}:
        dataframe = pd.read_excel(path, sheet_name=sheet_name)
    else:
        dataframe = pd.read_csv(path)

    if text_column not in dataframe.columns:
        raise ValueError(f"Column '{text_column}' not found. Available: {list(dataframe.columns)}")

    initial_count = len(dataframe)
    has_text = dataframe[text_column].notna() & dataframe[text_column].astype(str).str.strip().ne(
        ""
    )
    dataframe = dataframe[has_text].copy()
    if id_column and id_column in dataframe.columns:
        dataframe["response_id"] = dataframe[id_column]
    else:
        dataframe["response_id"] = range(1, len(dataframe) + 1)
    dataframe["original_text"] = dataframe[text_column].astype(str)

    logger.info(
        "Loaded %s responses (%s blank rows removed)",
        len(dataframe),
        initial_count - len(dataframe),
    )
    return dataframe
