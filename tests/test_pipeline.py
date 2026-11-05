import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from market_pipeline.pipeline import load_raw_excel, run_pipeline, standardize_raw_to_bronze, validate_bronze


DATASET = ROOT / "data" / "Mercado03-2026.xlsx"


def test_load_raw_excel_reads_source_sheet():
    raw = load_raw_excel(DATASET)
    assert not raw.empty
    assert "descricao_do_produto" in raw.columns


def test_standardize_raw_to_bronze_creates_bronze_table():
    raw = load_raw_excel(DATASET)
    bronze = standardize_raw_to_bronze(raw)

    assert not bronze.empty
    assert "produto_padronizado" in bronze.columns
    assert bronze["quantidade"].notna().all()
    assert bronze["valor_total"].notna().all()
    assert bronze["data_compra"].notna().all()


def test_validate_bronze_reports_no_issues_for_clean_dataset():
    raw = load_raw_excel(DATASET)
    bronze = standardize_raw_to_bronze(raw)
    issues = validate_bronze(bronze)

    assert issues == []


def test_run_pipeline_writes_bronze_csv(tmp_path):
    result = run_pipeline(DATASET, output_dir=tmp_path)

    assert result["rows_processed"] > 0
    assert result["rows_rejected"] == 0
    assert Path(result["output_file"]).exists()
    assert "mercado_bronze.csv" in result["output_file"]
    assert Path(result["rejected_file"]).exists()
    assert isinstance(result["issues"], list)


def test_run_pipeline_preserves_invalid_rows_with_rejection_reasons(tmp_path, monkeypatch):
    raw = load_raw_excel(DATASET).head(2).copy()
    rejected_source_row = raw.iloc[0]["linha_origem"]
    raw["qtde"] = raw["qtde"].astype(object)
    raw.loc[raw.index[0], "qtde"] = "not-a-number"
    monkeypatch.setattr("market_pipeline.pipeline.load_raw_excel", lambda _: raw.copy())

    result = run_pipeline(DATASET, output_dir=tmp_path)

    bronze = pd.read_csv(result["output_file"])
    rejected = pd.read_csv(result["rejected_file"])
    assert result["valid"] is False
    assert result["rows_valid"] == 1
    assert result["rows_rejected"] == 1
    assert len(bronze) == 1
    assert len(rejected) == 1
    assert rejected.iloc[0]["linha_origem"] == rejected_source_row
    assert "quantidade is missing or invalid" in rejected.iloc[0]["motivos_rejeicao"]
