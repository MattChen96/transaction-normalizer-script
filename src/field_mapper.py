"""
Fase 6 — Field Mapping: costruisce una riga di output per ogni riga filtrata.

Sequenza di applicazione per ogni campo di output:
  1. constant → usa e salta tutto il resto
  2. input_columns (concat) oppure input_column → leggi il valore grezzo
  3. transform pipeline → applica ogni step nell'ordine
  4. category_mapping → lookup nel dizionario
  5. default → fallback se ancora vuoto
  6. Errore R_FIELD_NULL se il campo è ancora vuoto (campo obbligatorio)
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from src.transforms import apply_pipeline
from src.logger import RunLogger

OUTPUT_FIELDS = ["Data", "Acquisto", "Importo", "Categoria", "Tag", "Wallet", "Note"]

# Campi che possono stare vuoti senza essere marcati come errore
OPTIONAL_FIELDS = {"Tag", "Note"}


def _apply_category_mapping(value: str, cat_cfg: dict[str, Any]) -> str:
    mapping: dict[str, str] = cat_cfg.get("map", {})
    case_sensitive: bool = cat_cfg.get("case_sensitive", False)
    trim_before: bool = cat_cfg.get("trim_before_match", True)
    default: str = cat_cfg.get("default", "")

    lookup_value = value.strip() if trim_before else value
    if not case_sensitive:
        lookup_value = lookup_value.lower()
        normalized_map = {k.lower(): v for k, v in mapping.items()}
    else:
        normalized_map = mapping

    return normalized_map.get(lookup_value, default)


def map_row(
    row: dict[str, str],
    fields_cfg: dict[str, Any],
    row_index: int,
    filename: str,
    logger: RunLogger,
) -> dict[str, str] | None:
    """
    Costruisce la riga di output dalla riga grezza.
    Ritorna None se almeno un campo obbligatorio non può essere valorizzato.
    """
    output: dict[str, str] = {}

    for field_name in OUTPUT_FIELDS:
        field_def = fields_cfg.get(field_name, {})
        value = _resolve_field(field_name, field_def, row, row_index, filename, logger)
        if value is None:
            return None
        output[field_name] = value

    return output


def _resolve_field(
    field_name: str,
    field_def: dict[str, Any],
    row: dict[str, str],
    row_index: int,
    filename: str,
    logger: RunLogger,
) -> str | None:
    """
    Risolve il valore di un singolo campo di output.
    Ritorna None se il campo non può essere valorizzato.
    """

    # 1. constant
    if "constant" in field_def:
        return str(field_def["constant"])

    # 2. lettura dall'input
    if "input_columns" in field_def:
        separator = field_def.get("concat_separator", "")
        parts = [row.get(col, "").strip() for col in field_def["input_columns"]]
        value = separator.join(p for p in parts if p)
    elif "input_column" in field_def:
        col = field_def["input_column"]
        if col not in row:
            logger.log_row_error(
                filename, row_index, field_name,
                "E_MISSING_INPUT_COLUMN", col,
            )
            return None
        value = row.get(col, "")
    else:
        value = ""

    # 3. transform pipeline
    pipeline = field_def.get("transform", [])
    if pipeline:
        try:
            value = apply_pipeline(pipeline, value, row)
        except Exception as exc:
            logger.log_row_error(
                filename, row_index, field_name,
                "R_TRANSFORM_FAIL", f"{value!r} → {exc}",
            )
            return None

    # 4. category_mapping
    cat_cfg = field_def.get("category_mapping")
    if cat_cfg:
        mapped = _apply_category_mapping(value, cat_cfg)
        if not mapped and value:
            logger.log_row_warning(
                filename, row_index, field_name,
                "W_CATEGORY_UNMAPPED", value,
                fallback=cat_cfg.get("default", ""),
            )
        value = mapped if mapped else value

    # 4b. embedding_fallback: usato quando il category_mapping restituisce il default
    emb_cfg = field_def.get("embedding_fallback")
    if emb_cfg and cat_cfg:
        cat_default = cat_cfg.get("default", "")
        if value == cat_default:
            from src.category_embedder import get_embedder
            source_col = emb_cfg.get("source_column", "")
            threshold = float(emb_cfg.get("threshold", 0.20))
            text = row.get(source_col, "").strip()
            if text:
                value = get_embedder().classify(text, threshold=threshold)

    # 5. default fallback
    if not value and "default" in field_def:
        default_val = field_def["default"]
        value = "" if default_val is None else str(default_val)

    # 6. R_FIELD_NULL se ancora vuoto (solo per campi obbligatori)
    if not value:
        if field_name not in OPTIONAL_FIELDS:
            logger.log_row_error(
                filename, row_index, field_name,
                "R_FIELD_NULL", "(empty)",
            )
            return None
        # Per campi opzionali, permetti stringa vuota
        value = ""

    return value


def map_dataframe(
    df: pd.DataFrame,
    fields_cfg: dict[str, Any],
    filename: str,
    logger: RunLogger,
) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    """
    Applica il field mapping a tutto il DataFrame filtrato.
    Ritorna (df_output, df_rejected, n_righe_con_errori).
    df_rejected contiene le righe raw che non hanno passato il mapping,
    con una colonna aggiuntiva '_reject_reason'.
    """
    output_rows: list[dict[str, str]] = []
    rejected_rows: list[dict[str, str]] = []
    n_errors = 0

    for i, row in enumerate(df.to_dict(orient="records")):
        row_str = {k: str(v) for k, v in row.items()}
        result = map_row(row_str, fields_cfg, i + 1, filename, logger)
        if result is None:
            n_errors += 1
            row_str["_reject_reason"] = f"mapping_error:row_{i + 1}"
            rejected_rows.append(row_str)
        else:
            output_rows.append(result)

    raw_cols = list(df.columns) + ["_reject_reason"]
    rejected_df = (
        pd.DataFrame(rejected_rows, columns=raw_cols)
        if rejected_rows
        else pd.DataFrame(columns=raw_cols)
    )

    if not output_rows:
        return pd.DataFrame(columns=OUTPUT_FIELDS), rejected_df, n_errors

    return pd.DataFrame(output_rows, columns=OUTPUT_FIELDS), rejected_df, n_errors
