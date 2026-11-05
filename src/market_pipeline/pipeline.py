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
    "produto_padronizado",
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
        value = cleaned
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_raw_excel(excel_path: str | Path) -> pd.DataFrame:
    path = Path(excel_path)
    df = pd.read_excel(path, sheet_name="Mercado 03-2026")
    df = df.dropna(how="all").copy()

    if df.empty:
        raise ValueError(f"The source workbook '{path}' is empty.")

    df.columns = [_normalize_column_name(col) for col in df.columns]
    df["linha_origem"] = df.index + 2
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

    if "linha_origem" not in renamed.columns:
        renamed["linha_origem"] = renamed.index + 2

    bronze = renamed[["linha_origem", *required]].copy()
    for column in ["produto_descricao", "categoria", "unidade"]:
        cleaned = bronze[column].map(lambda value: None if pd.isna(value) else str(value).strip())
        bronze[column] = cleaned.map(lambda value: value or None)
    bronze["quantidade"] = bronze["quantidade"].map(_coerce_decimal)
    bronze["valor_unitario"] = bronze["valor_unitario"].map(_coerce_decimal)
    bronze["valor_total"] = bronze["valor_total"].map(_coerce_decimal)
    bronze["data_compra"] = pd.to_datetime(bronze["data_compra"], errors="coerce")

    normalized_product = bronze["produto_descricao"].fillna("").str.replace(r"\s+", " ", regex=True).str.strip()
    bronze["produto_padronizado"] = normalized_product.mask(normalized_product.eq(""), pd.NA)
    bronze = bronze.sort_values(["data_compra", "linha_origem"], na_position="last").reset_index(drop=True)
    return bronze


def _row_validation_reasons(row: pd.Series) -> list[str]:
    reasons: list[str] = []

    for column in ["produto_descricao", "categoria", "unidade"]:
        if pd.isna(row[column]) or not str(row[column]).strip():
            reasons.append(f"{column} is missing")

    if pd.isna(row["produto_padronizado"]):
        reasons.append("produto_padronizado is missing")
    elif len(str(row["produto_padronizado"])) < 3:
        reasons.append("product description is shorter than three characters")

    for column in ["quantidade", "valor_unitario", "valor_total"]:
        if pd.isna(row[column]):
            reasons.append(f"{column} is missing or invalid")
        elif row[column] <= 0:
            reasons.append(f"{column} must be positive")

    if pd.isna(row["data_compra"]):
        reasons.append("data_compra is missing or invalid")

    return reasons


def validate_bronze(bronze_df: pd.DataFrame) -> list[str]:
    if bronze_df.empty:
        return ["Bronze dataset is empty."]

    missing = EXPECTED_COLUMNS.difference(set(bronze_df.columns))
    if missing:
        return [f"Missing required columns: {sorted(missing)}"]

    issues: list[str] = []
    for _, row in bronze_df.iterrows():
        reasons = _row_validation_reasons(row)
        if reasons:
            source_row = row.get("linha_origem", "unknown")
            issues.append(f"Source row {source_row}: {'; '.join(reasons)}")
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
    reasons_by_source_row = {
        row["linha_origem"]: _row_validation_reasons(row)
        for _, row in bronze_df.iterrows()
    }
    rejected_reasons = {source_row: reasons for source_row, reasons in reasons_by_source_row.items() if reasons}
    valid_mask = ~bronze_df["linha_origem"].isin(rejected_reasons)
    valid_bronze_df = bronze_df.loc[valid_mask].copy()

    rejected_df = raw_df.loc[raw_df["linha_origem"].isin(rejected_reasons)].copy()
    rejected_df["motivos_rejeicao"] = rejected_df["linha_origem"].map(
        lambda source_row: "; ".join(rejected_reasons[source_row])
    )

    bronze_file = output_path / "mercado_bronze.csv"
    rejected_file = output_path / "mercado_rejeitados.csv"
    valid_bronze_df.to_csv(bronze_file, index=False)
    rejected_df.to_csv(rejected_file, index=False)
    return {
        "source_file": str(source_path),
        "output_file": str(bronze_file),
        "rejected_file": str(rejected_file),
        "rows_processed": int(len(raw_df)),
        "rows_valid": int(len(valid_bronze_df)),
        "rows_rejected": int(len(rejected_df)),
        "columns": list(valid_bronze_df.columns),
        "issues": issues,
        "valid": not issues,
    }
