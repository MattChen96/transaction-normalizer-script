"""
Lettura di file CSV e Excel con i parametri della sezione `file` del config.
Tutte le colonne vengono mantenute come stringhe grezze.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def read_file(file_path: Path, file_cfg: dict[str, Any]) -> pd.DataFrame:
    """
    Legge il file di input e ritorna un DataFrame con tutte le colonne
    come stringhe grezze (dtype=str). La conversione di tipo avviene
    in seguito durante il field mapping.

    Lancia:
        ValueError → E_FILE_EMPTY se il file non contiene righe dati
        Exception  → E_FILE_UNREADABLE per qualsiasi errore di lettura
    """
    fmt = file_cfg.get("format", "csv").lower()
    skip_rows = file_cfg.get("skip_rows", 0)
    header_row = file_cfg.get("header_row", 0)

    try:
        if fmt == "csv":
            df = _read_csv(file_path, file_cfg, skip_rows, header_row)
        elif fmt in ("xlsx", "xls"):
            df = _read_excel(file_path, file_cfg, skip_rows, header_row)
        else:
            raise ValueError(f"Formato file non supportato: {fmt!r}")
    except (ValueError, KeyError):
        raise
    except Exception as exc:
        raise OSError(f"E_FILE_UNREADABLE: {file_path}: {exc}") from exc

    if df.empty:
        raise ValueError(f"E_FILE_EMPTY: {file_path} non contiene righe dati")

    # Normalizza tutti i valori a stringhe; NaN → stringa vuota
    df = df.astype(str).replace({"nan": "", "None": "", "<NA>": ""})

    return df


def _read_csv(
    path: Path,
    cfg: dict[str, Any],
    skip_rows: int,
    header_row: int,
) -> pd.DataFrame:
    encoding = cfg.get("encoding", "utf-8")
    delimiter = cfg.get("delimiter", ",")
    quotechar = cfg.get("quotechar", '"')

    # skiprows salta righe prima dell'header; header è 0-based dopo il salto
    return pd.read_csv(
        path,
        encoding=encoding,
        sep=delimiter,
        quotechar=quotechar,
        skiprows=skip_rows if skip_rows else None,
        header=header_row,
        dtype=str,
        keep_default_na=False,
        na_values=[],
    )


def _read_excel(
    path: Path,
    cfg: dict[str, Any],
    skip_rows: int,
    header_row: int,
) -> pd.DataFrame:
    sheet_name = cfg.get("sheet_name", 0)

    return pd.read_excel(
        path,
        sheet_name=sheet_name,
        skiprows=skip_rows if skip_rows else None,
        header=header_row,
        dtype=str,
        keep_default_na=False,
        na_values=[],
        engine="openpyxl",
    )
