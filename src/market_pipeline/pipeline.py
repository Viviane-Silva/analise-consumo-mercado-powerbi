from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Iterable

import pandas as pd

EXPECTED_COLUMNS = {
    "produto_descricao",
    "categoria",
    "quantidade",
    "unidade",
    "valor_unitario",
    "valor_total",
    "data_compra",
}


def _normalize_column_name(column_name: object) -> str:
    text = str(column_name or "")
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


def _coerce_decimal(value: object) -> float | None:
    if pd.isna(value):
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        cleaned = cleaned.replace("R$", "").replace(".", "").replace(",", ".")
        cleaned = cleaned.strip()
        if not cleaned:
            return None
        return float(cleaned)
    return float(value)


def load_raw_excel(excel_path: str | Path) -> pd.DataFrame:
    path = Path(excel_path)
    df = pd.read_excel(path, sheet_name="Mercado 03-2026")
    df = df.dropna(how="all").copy()

    if df.empty:
        raise ValueError(f"The source workbook '{path}' is empty.")

    df.columns = [_normalize_column_name(col) for col in df.columns]
    return df


def standardize_raw_to_bronze(raw_df: pd.DataFrame) -> pd.DataFrame:
    renamed = raw_df.copy()

    column_mapping = {
        "descricao_do_produto": "produto_descricao",
        "categoria": "categoria",
        "qtde": "quantidade",
        "unid": "unidade",
        "vlr_unit_r": "valor_unitario",
        "tot_r": "valor_total",
        "data_compra": "data_compra",
        "dia_de_semana": "dia_semana",
    }

    renamed = renamed.rename(columns=column_mapping)

    required = ["produto_descricao", "categoria", "quantidade", "unidade", "valor_unitario", "valor_total", "data_compra"]
    missing = [col for col in required if col not in renamed.columns]
    if missing:
        raise ValueError(f"Missing expected columns: {missing}")

    bronze = renamed[required].copy()
    bronze["produto_descricao"] = bronze["produto_descricao"].astype(str).str.strip()
    bronze["categoria"] = bronze["categoria"].astype(str).str.strip()
    bronze["unidade"] = bronze["unidade"].astype(str).str.strip()
    bronze["quantidade"] = bronze["quantidade"].map(_coerce_decimal)
    bronze["valor_unitario"] = bronze["valor_unitario"].map(_coerce_decimal)
    bronze["valor_total"] = bronze["valor_total"].map(_coerce_decimal)
    bronze["data_compra"] = pd.to_datetime(bronze["data_compra"], errors="coerce")

    bronze = bronze.dropna(subset=["produto_descricao", "categoria", "quantidade", "valor_unitario", "valor_total", "data_compra"]).copy()
    bronze = bronze.sort_values("data_compra").reset_index(drop=True)
    bronze["produto_padronizado"] = bronze["produto_descricao"].str.replace(r"\s+", " ", regex=True).str.strip()
    return bronze


def validate_bronze(bronze_df: pd.DataFrame) -> list[str]:
    issues: list[str] = []

    if bronze_df.empty:
        return ["Bronze dataset is empty after cleaning."]

    missing = EXPECTED_COLUMNS.difference(set(bronze_df.columns))
    if missing:
        issues.append(f"Missing required columns: {sorted(missing)}")

    if bronze_df["produto_padronizado"].str.len().lt(3).any():
        issues.append("Product descriptions shorter than three characters were found.")

    if (bronze_df["quantidade"] <= 0).any():
        issues.append("Negative or zero quantities were found.")

    if (bronze_df["valor_unitario"] <= 0).any():
        issues.append("Negative or zero unit prices were found.")

    if (bronze_df["valor_total"] <= 0).any():
        issues.append("Negative or zero total values were found.")

    if bronze_df["data_compra"].isna().any():
        issues.append("Some records have invalid dates after parsing.")

    return issues


def run_pipeline(excel_path: str | Path, output_dir: str | Path | None = None) -> dict[str, object]:
    source_path = Path(excel_path)
    if output_dir is None:
        output_dir = source_path.parent / "bronze"
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    raw_df = load_raw_excel(source_path)
    bronze_df = standardize_raw_to_bronze(raw_df)
    issues = validate_bronze(bronze_df)

    bronze_file = output_path / "mercado_bronze.csv"
    bronze_df.to_csv(bronze_file, index=False)
    return {
        "source_file": str(source_path),
        "output_file": str(bronze_file),
        "rows_processed": int(len(bronze_df)),
        "columns": list(bronze_df.columns),
        "issues": issues,
        "valid": not issues,
    }
