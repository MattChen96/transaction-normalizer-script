"""
Fase 7 — Output Validation: verifica che il dataset prodotto rispetti
esattamente il contratto definito in config/output_schema.json.

Controlli per riga:
  - Data formato ISO 8601 (YYYY-MM-DD)
  - Importo è un numero decimale valido
  - Categoria è uno dei valori enum predefiniti
  - Wallet è uno dei valori enum predefiniti
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.config_loader import _load_json_strict
from src.logger import RunLogger
from src.field_mapper import OUTPUT_FIELDS

_OUTPUT_SCHEMA_PATH = Path(__file__).parent.parent / "config" / "output_schema.json"
_OUTPUT_SCHEMA = _load_json_strict(_OUTPUT_SCHEMA_PATH)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_CATEGORY_ENUM = set(_OUTPUT_SCHEMA["column_definitions"]["Categoria"]["enum"])
_WALLET_ENUM = set(_OUTPUT_SCHEMA["column_definitions"]["Wallet"]["enum"])


def validate_output(
    df: pd.DataFrame,
    filename: str,
    logger: RunLogger,
) -> pd.DataFrame:
    """
    Valida ogni riga del DataFrame di output.
    Le righe invalide vengono rimosse e loggate.
    Ritorna il DataFrame con le sole righe valide.
    """
    # Verifica colonne esatte
    if list(df.columns) != OUTPUT_FIELDS:
        raise ValueError(
            f"E_OUTPUT_SCHEMA_MISMATCH: colonne attese {OUTPUT_FIELDS}, "
            f"trovate {list(df.columns)}"
        )

    valid_mask = pd.Series([True] * len(df), index=df.index)

    for i, row in df.iterrows():
        row_valid = True

        # Data
        data_val = str(row["Data"])
        if not _DATE_RE.match(data_val):
            logger.log_row_error(
                filename, int(i) + 1, "Data",
                "R_DATE_INVALID", data_val,
            )
            row_valid = False
        else:
            try:
                datetime.strptime(data_val, "%Y-%m-%d")
            except ValueError:
                logger.log_row_error(
                    filename, int(i) + 1, "Data",
                    "R_DATE_INVALID", data_val,
                )
                row_valid = False

        # Importo
        importo_val = str(row["Importo"])
        try:
            float(importo_val)
        except ValueError:
            logger.log_row_error(
                filename, int(i) + 1, "Importo",
                "R_AMOUNT_INVALID", importo_val,
            )
            row_valid = False

        # Categoria
        categoria_val = str(row["Categoria"]).strip()
        if categoria_val not in _CATEGORY_ENUM:
            logger.log_row_error(
                filename, int(i) + 1, "Categoria",
                "R_CATEGORY_INVALID", categoria_val,
            )
            row_valid = False

        # Wallet
        wallet_val = str(row["Wallet"]).strip()
        if wallet_val not in _WALLET_ENUM:
            logger.log_row_error(
                filename, int(i) + 1, "Wallet",
                "R_WALLET_INVALID", wallet_val,
            )
            row_valid = False

        if not row_valid:
            valid_mask.at[i] = False

    return df[valid_mask].reset_index(drop=True)
