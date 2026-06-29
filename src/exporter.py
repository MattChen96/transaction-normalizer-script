"""
Fase 8 — Export: scrittura del dataset normalizzato in output/.

Modalità default: merge — tutti i file elaborati in un unico CSV e XLSX per run.
Il nome del file include il timestamp della run.
Viene prodotto anche un file separato con le righe scartate.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def export_csv(
    df: pd.DataFrame,
    output_dir: Path,
    run_id: str,
) -> Path:
    """
    Scrive df in output/normalized_<run_id>.csv.
    Ritorna il path del file scritto.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"normalized_{run_id}.csv"
    df.to_csv(
        out_path,
        index=False,
        encoding="utf-8",
        sep=",",
        decimal=".",
    )
    return out_path


def export_excel(
    df: pd.DataFrame,
    output_dir: Path,
    run_id: str,
) -> Path:
    """
    Scrive df in output/normalized_<run_id>.xlsx.
    Ritorna il path del file scritto.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"normalized_{run_id}.xlsx"
    df.to_excel(
        out_path,
        sheet_name="Transazioni",
        index=False,
        engine="openpyxl",
    )
    return out_path


def export_rejected(
    df: pd.DataFrame,
    output_dir: Path,
    run_id: str,
) -> Path | None:
    """
    Scrive le righe scartate in output/rejected_<run_id>.csv.
    Ritorna il path del file scritto, o None se df è vuoto.
    """
    if df.empty:
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"rejected_{run_id}.csv"
    df.to_csv(
        out_path,
        index=False,
        encoding="utf-8",
        sep=",",
    )
    return out_path
