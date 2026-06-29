"""
Fase 5 — Row Filtering: applica le regole `filters` ai dati grezzi.

Semantica:
  include → AND logico: la riga passa solo se TUTTE le regole include sono vere
  exclude → OR logico:  la riga viene scartata se ALMENO UNA regola exclude è vera

Il filtraggio avviene prima del mapping, sui valori stringa grezzi.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from src.transforms import _evaluate_condition


def apply_filters(
    df: pd.DataFrame,
    filters_cfg: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Applica le regole include/exclude al DataFrame grezzo.

    Ritorna (df_filtrato, df_scartato) dove df_scartato contiene
    le righe escluse con una colonna aggiuntiva '_reject_reason'.
    """
    include_rules: list[dict] = filters_cfg.get("include", [])
    exclude_rules: list[dict] = filters_cfg.get("exclude", [])

    if not include_rules and not exclude_rules:
        return df, pd.DataFrame(columns=list(df.columns) + ["_reject_reason"])

    mask = pd.Series([True] * len(df), index=df.index)
    reject_reason: dict[int, str] = {}

    # ── Include (AND) ────────────────────────────────────────────────────────
    for rule in include_rules:
        col = rule["column"]
        if col not in df.columns:
            continue
        operator = rule["operator"]
        value = rule.get("value")
        case_sensitive = rule.get("case_sensitive", False)

        col_mask = df[col].apply(
            lambda cell: _evaluate_condition(
                str(cell), operator, value, case_sensitive
            )
        )
        newly_excluded = mask & ~col_mask
        for idx in df.index[newly_excluded]:
            if idx not in reject_reason:
                reject_reason[idx] = f"include_fail:{col}={rule.get('value','')}"
        mask = mask & col_mask

    # ── Exclude (OR) ─────────────────────────────────────────────────────────
    for rule in exclude_rules:
        col = rule["column"]
        if col not in df.columns:
            continue
        operator = rule["operator"]
        value = rule.get("value")
        case_sensitive = rule.get("case_sensitive", False)

        col_mask = df[col].apply(
            lambda cell: _evaluate_condition(
                str(cell), operator, value, case_sensitive
            )
        )
        newly_excluded = mask & col_mask
        for idx in df.index[newly_excluded]:
            if idx not in reject_reason:
                reject_reason[idx] = f"exclude_match:{col}={rule.get('value','')}"
        mask = mask & ~col_mask

    filtered_df = df[mask].reset_index(drop=True)

    rejected_df = df[~mask].copy()
    rejected_df["_reject_reason"] = rejected_df.index.map(
        lambda i: reject_reason.get(i, "filtered")
    )
    rejected_df = rejected_df.reset_index(drop=True)

    return filtered_df, rejected_df
