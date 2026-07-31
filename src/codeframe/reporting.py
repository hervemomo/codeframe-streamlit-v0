"""Notebook-equivalent frequency, co-occurrence, chart, and workbook reporting."""

import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from codeframe.codebook import (
    CodebookMapping,
    clean_code_id,
    codebook_has_code_ids,
    get_code_columns,
)
from codeframe.paths import ensure_output_dir

logger = logging.getLogger(__name__)


def calculate_frequencies(dataframe: pd.DataFrame, codebook: CodebookMapping) -> pd.DataFrame:
    """Count assigned responses and percentages in notebook sort order."""

    entries = get_code_columns(dataframe, codebook)
    columns = (
        ["code_id", "code", "count", "percentage"]
        if codebook_has_code_ids(codebook)
        else ["code", "count", "percentage"]
    )
    if not entries:
        return pd.DataFrame(columns=columns)
    total = len(dataframe)
    identifiers_by_name = {
        code["name"]: clean_code_id(code.get("code_id", "")) for code in codebook.get("codes", [])
    }
    rows: list[dict[str, Any]] = []
    for name, code_column, _ in entries:
        count = int(dataframe[code_column].sum())
        row: dict[str, Any] = {
            "code": name,
            "count": count,
            "percentage": round(count / total * 100, 1) if total else 0,
        }
        if codebook_has_code_ids(codebook):
            row["code_id"] = identifiers_by_name.get(name, "")
        rows.append(row)
    return pd.DataFrame(rows)[columns].sort_values("count", ascending=False).reset_index(drop=True)


def generate_cooccurrence_matrix(
    dataframe: pd.DataFrame, codebook: CodebookMapping
) -> pd.DataFrame:
    """Build the notebook's code-by-code binary co-occurrence matrix."""

    entries = get_code_columns(dataframe, codebook)
    code_columns = [entry[1] for entry in entries]
    names = [entry[0] for entry in entries]
    if not code_columns:
        return pd.DataFrame()
    binary = dataframe[code_columns].values.astype(int)
    return pd.DataFrame(binary.T @ binary, index=names, columns=names)


def plot_frequency_chart(
    frequency_dataframe: pd.DataFrame,
    *,
    output_dir: Path,
    file_stem: str,
    title: str = "Fréquence des codes",
    figsize: tuple[int, int] = (12, 7),
) -> str:
    """Save the notebook's horizontal frequency chart."""

    destination_dir = ensure_output_dir(output_dir)
    plot_dataframe = frequency_dataframe.sort_values("count", ascending=True)
    figure = Figure(figsize=figsize)
    FigureCanvasAgg(figure)
    axis = figure.subplots()
    colors = sns.color_palette("viridis", len(plot_dataframe))
    bars = axis.barh(plot_dataframe["code"], plot_dataframe["count"], color=colors)
    axis.set_xlabel("Nombre de réponses")
    axis.set_title(title)
    for bar, percentage in zip(bars, plot_dataframe["percentage"], strict=True):
        axis.text(
            bar.get_width() + 0.3,
            bar.get_y() + bar.get_height() / 2,
            f"{percentage}%",
            va="center",
            fontsize=9,
        )
    figure.tight_layout()
    destination = destination_dir / f"{file_stem}_frequencies.png"
    figure.savefig(destination, dpi=150, bbox_inches="tight")
    logger.info("Frequency chart -> %s", destination)
    return str(destination)


def plot_cooccurrence_heatmap(
    cooccurrence_dataframe: pd.DataFrame,
    *,
    output_dir: Path,
    file_stem: str,
    title: str = "Co-occurrence des codes",
    figsize: tuple[int, int] = (12, 10),
) -> str | None:
    """Save a diagonal-masked annotated heatmap, or none for an empty matrix."""

    if cooccurrence_dataframe.empty:
        logger.warning("Co-occurrence matrix empty - skipping heatmap.")
        return None
    destination_dir = ensure_output_dir(output_dir)
    figure = Figure(figsize=figsize)
    FigureCanvasAgg(figure)
    axis = figure.subplots()
    sns.heatmap(
        cooccurrence_dataframe,
        mask=np.eye(len(cooccurrence_dataframe), dtype=bool),
        annot=True,
        fmt="d",
        cmap="YlOrRd",
        square=True,
        linewidths=0.5,
        cbar_kws={"label": "Co-occurrences"},
        ax=axis,
    )
    axis.set_title(title)
    axis.tick_params(axis="x", labelrotation=45)
    for label in axis.get_xticklabels():
        label.set_horizontalalignment("right")
    figure.tight_layout()
    destination = destination_dir / f"{file_stem}_cooccurrence.png"
    figure.savefig(destination, dpi=150, bbox_inches="tight")
    logger.info("Co-occurrence heatmap -> %s", destination)
    return str(destination)


def _codebook_export_frame(codebook: CodebookMapping) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    has_identifiers = codebook_has_code_ids(codebook)
    for code in codebook["codes"]:
        row: dict[str, Any] = {
            "Code ID": clean_code_id(code.get("code_id", "")),
            "Code": code["name"],
            "Definition": code.get("definition", ""),
            "Inclusion": "; ".join(code.get("inclusion_criteria", [])),
            "Exclusion": "; ".join(code.get("exclusion_criteria", [])),
            "Examples": " | ".join(code.get("example_verbatims", [])[:3]),
            "Parent": code.get("parent_code", ""),
            "Parent Code ID": code.get("parent_code_id", ""),
            "Merged From": " | ".join(code.get("merged_from", [])),
            "Merged From IDs": " | ".join(code.get("merged_from_ids", [])),
            "Source": code.get("source", ""),
            "Estimated Response Count": code.get("estimated_response_count", ""),
        }
        if not has_identifiers:
            row.pop("Code ID")
            row.pop("Parent Code ID")
            row.pop("Merged From IDs")
        rows.append(row)
    return pd.DataFrame(rows)


def generate_reports(
    dataframe: pd.DataFrame,
    codebook: CodebookMapping,
    *,
    output_dir: Path,
    file_stem: str,
    text_column: str,
    output_file: str = "coding_summary.xlsx",
    include_charts: bool = True,
    include_excel: bool = True,
) -> dict[str, str | None]:
    """Generate the complete notebook report bundle into an explicit directory."""

    destination_dir = ensure_output_dir(output_dir)
    frequencies = calculate_frequencies(dataframe, codebook)
    cooccurrence = generate_cooccurrence_matrix(dataframe, codebook)
    outputs: dict[str, str | None] = {}
    if include_charts:
        outputs["frequency_chart"] = plot_frequency_chart(
            frequencies,
            output_dir=destination_dir,
            file_stem=file_stem,
        )
        outputs["cooccurrence_chart"] = plot_cooccurrence_heatmap(
            cooccurrence,
            output_dir=destination_dir,
            file_stem=file_stem,
        )
    if include_excel:
        path = destination_dir / output_file
        total = len(dataframe)
        valid = int(dataframe["is_valid"].sum()) if "is_valid" in dataframe.columns else total
        code_columns = [entry[1] for entry in get_code_columns(dataframe, codebook)]
        coded = int((dataframe[code_columns].sum(axis=1) > 0).sum()) if code_columns else 0
        summary = pd.DataFrame(
            {
                "Metric": [
                    "Total responses",
                    "Valid responses",
                    "Invalid/blank",
                    "Coded responses",
                    "Uncoded responses",
                    "Number of codes",
                    "Multi-label",
                ],
                "Value": [
                    total,
                    valid,
                    total - valid,
                    coded,
                    total - coded,
                    len(codebook["codes"]),
                    codebook.get("multi_label", True),
                ],
            }
        )
        codebook_frame = _codebook_export_frame(codebook)
        base_columns = [
            column
            for column in [
                "response_id",
                "original_text",
                "codes",
                "code_ids",
                "has_multi_label",
                "num_codes",
                text_column,
                "is_valid",
            ]
            if column in dataframe.columns
        ]
        assignment_columns = [
            column
            for column in dataframe.columns
            if column.startswith("code_") and column != "code_ids" and column not in base_columns
        ]
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            summary.to_excel(writer, sheet_name="Summary", index=False)
            frequencies.to_excel(writer, sheet_name="Frequencies", index=False)
            cooccurrence.to_excel(writer, sheet_name="Co-occurrence")
            codebook_frame.to_excel(writer, sheet_name="Codebook", index=False)
            dataframe[base_columns + assignment_columns].to_excel(
                writer, sheet_name="Coded Data", index=False
            )
        outputs["summary_report"] = str(path)
        logger.info("Report -> %s", path)
    return outputs
