"""
Catalogo completo delle trasformazioni supportate dalla pipeline.

Ogni handler ha firma:
    handler(value: str, params: dict, row: dict[str, str]) -> str

- value : valore corrente (stringa grezza o già parzialmente trasformata)
- params: l'intero oggetto transform dal config (include "type" e i parametri)
- row   : la riga grezza completa come dict {nome_colonna: valore_stringa}
          necessario per trasformazioni che leggono altre colonne (conditional,
          sign_from_column, coalesce, concat con riferimenti $Col)
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Callable

from dateutil import parser as dateutil_parser


# ── Helpers interni ──────────────────────────────────────────────────────────

def _to_float(value: str) -> float:
    """Converte una stringa numerica normalizzata (punto come decimale) a float."""
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"valore vuoto non convertibile a numero")
    return float(cleaned)


def _normalize_number(value: str, decimal_sep: str, thousands_sep: str) -> str:
    """
    Converte un numero in formato locale a stringa con punto decimale.
    es. "1.234,56" con decimal_sep="," thousands_sep="." → "1234.56"
    """
    v = value.strip()
    if thousands_sep:
        v = v.replace(thousands_sep, "")
    if decimal_sep and decimal_sep != ".":
        v = v.replace(decimal_sep, ".")
    return v


# ── Trasformazioni ───────────────────────────────────────────────────────────

def _trim(value: str, params: dict, row: dict) -> str:
    return value.strip()


def _lowercase(value: str, params: dict, row: dict) -> str:
    return value.lower()


def _uppercase(value: str, params: dict, row: dict) -> str:
    return value.upper()


def _titlecase(value: str, params: dict, row: dict) -> str:
    return value.title()


def _date_format(value: str, params: dict, row: dict) -> str:
    v = value.strip()
    if not v:
        return v
    output_fmt = params.get("output_format", "%Y-%m-%d")
    input_fmt = params.get("input_format")
    if input_fmt:
        dt = datetime.strptime(v, input_fmt)
    else:
        dt = dateutil_parser.parse(v, dayfirst=True)
    return dt.strftime(output_fmt)


def _number_normalize(value: str, params: dict, row: dict) -> str:
    decimal_sep = params.get("decimal_separator", ".")
    thousands_sep = params.get("thousands_separator", "")
    return _normalize_number(value, decimal_sep, thousands_sep)


def _number_abs(value: str, params: dict, row: dict) -> str:
    return str(abs(_to_float(value)))


def _number_negate(value: str, params: dict, row: dict) -> str:
    return str(-_to_float(value))


def _number_round(value: str, params: dict, row: dict) -> str:
    decimals = params.get("decimals", 2)
    rounded = round(_to_float(value), decimals)
    return f"{rounded:.{decimals}f}"


def _regex_extract(value: str, params: dict, row: dict) -> str:
    pattern = params["pattern"]
    group = params.get("group", 1)
    match = re.search(pattern, value)
    if match:
        return match.group(group)
    return ""


def _regex_replace(value: str, params: dict, row: dict) -> str:
    pattern = params["pattern"]
    replacement = params.get("replacement", "")
    return re.sub(pattern, replacement, value)


def _replace(value: str, params: dict, row: dict) -> str:
    find = params["find"]
    replacement = params.get("replacement", "")
    return value.replace(find, replacement)


def _replace_map(value: str, params: dict, row: dict) -> str:
    mapping: dict[str, str] = params.get("map", {})
    # Prova match esatto prima (case-sensitive)
    if value in mapping:
        return mapping[value]
    # Fallback case-insensitive
    value_lower = value.lower()
    for k, v in mapping.items():
        if k.lower() == value_lower:
            return v
    return value


def _concat(value: str, params: dict, row: dict) -> str:
    separator = params.get("separator", "")
    parts: list[str] = []
    for item in params.get("values", []):
        if isinstance(item, str) and item.startswith("$"):
            col_name = item[1:]
            parts.append(row.get(col_name, ""))
        else:
            parts.append(str(item))
    return separator.join(p for p in parts if p)


def _strip_chars(value: str, params: dict, row: dict) -> str:
    chars = params.get("chars", " ")
    return value.strip(chars)


def _split_take(value: str, params: dict, row: dict) -> str:
    separator = params.get("separator", " ")
    index = params.get("index", 0)
    parts = value.split(separator)
    if index < len(parts):
        return parts[index]
    return ""


def _coalesce(value: str, params: dict, row: dict) -> str:
    # Ritorna il primo valore non-vuoto tra le colonne elencate
    for col in params.get("columns", []):
        v = row.get(col, "").strip()
        if v:
            return v
    return value


def _conditional(value: str, params: dict, row: dict) -> str:
    for cond in params.get("conditions", []):
        col_val = row.get(cond["if_column"], "")
        operator = cond["operator"]
        cond_value = cond.get("value")
        matched = _evaluate_condition(col_val, operator, cond_value)
        if matched:
            then = cond["then"]
            return "" if then is None else str(then)
    else_val = params.get("else")
    return "" if else_val is None else str(else_val)


def _sign_from_column(value: str, params: dict, row: dict) -> str:
    """
    Determina il segno dell'importo leggendo una colonna indicatrice.
    Applica il segno positivo o negativo al valore numerico corrente.
    """
    indicator_col = params["column"]
    positive_values = [v.lower() for v in params.get("positive_values", [])]
    negative_values = [v.lower() for v in params.get("negative_values", [])]

    indicator = row.get(indicator_col, "").strip().lower()
    try:
        amount = _to_float(value)
    except (ValueError, TypeError):
        return value

    if indicator in positive_values:
        return str(abs(amount))
    if indicator in negative_values:
        return str(-abs(amount))
    return value


def _embedding_categorize(value: str, params: dict, row: dict) -> str:
    """
    Classifica una descrizione testuale nella categoria più vicina
    usando sentence-transformers (paraphrase-multilingual-MiniLM-L12-v2).

    Usato SOLO come transform diretto sul testo della descrizione.
    Per il fallback dopo category_mapping, usare il campo `embedding_fallback`
    nella definizione del campo (field_definition).

    Parametri config:
      source_column  : nome colonna input da usare come testo (opzionale)
      threshold      : float, punteggio minimo di similarità (default 0.20)
      fallback       : categoria da usare se sotto soglia (default '🎲 Altro')
    """
    from src.category_embedder import get_embedder

    source_col = params.get("source_column")
    text = value.strip() if value.strip() else row.get(source_col or "", "")

    threshold = float(params.get("threshold", 0.20))
    fallback = params.get("fallback", "🎲 Altro")

    if not text.strip():
        return fallback

    result = get_embedder().classify(text, threshold=threshold)
    return result


# ── Valutazione condizione (usata da _conditional e da row_filter) ────────────

def _evaluate_condition(
    cell_value: str,
    operator: str,
    cond_value: Any,
    case_sensitive: bool = False,
) -> bool:
    cv = cell_value if case_sensitive else cell_value.lower()

    if operator == "is_empty":
        return cv.strip() == ""
    if operator == "is_not_empty":
        return cv.strip() != ""

    if not case_sensitive and isinstance(cond_value, str):
        cond_value = cond_value.lower()
    if not case_sensitive and isinstance(cond_value, list):
        cond_value = [v.lower() if isinstance(v, str) else v for v in cond_value]

    if operator == "equals":
        return cv == str(cond_value)
    if operator == "not_equals":
        return cv != str(cond_value)
    if operator == "in":
        return cv in [str(v) for v in (cond_value or [])]
    if operator == "not_in":
        return cv not in [str(v) for v in (cond_value or [])]
    if operator == "contains":
        return str(cond_value) in cv
    if operator == "not_contains":
        return str(cond_value) not in cv
    if operator == "starts_with":
        return cv.startswith(str(cond_value))
    if operator == "ends_with":
        return cv.endswith(str(cond_value))
    if operator == "regex":
        flags = 0 if case_sensitive else re.IGNORECASE
        return bool(re.search(str(cond_value), cell_value, flags))
    # Numeric operators — usa il valore originale (non lowercased)
    try:
        num_cv = float(cell_value.strip().replace(",", "."))
        num_cond = float(str(cond_value).strip())
    except (ValueError, TypeError):
        return False
    if operator == "gt":
        return num_cv > num_cond
    if operator == "gte":
        return num_cv >= num_cond
    if operator == "lt":
        return num_cv < num_cond
    if operator == "lte":
        return num_cv <= num_cond
    return False


# ── Registro ─────────────────────────────────────────────────────────────────

_REGISTRY: dict[str, Callable[[str, dict, dict], str]] = {
    "trim":                  _trim,
    "lowercase":             _lowercase,
    "uppercase":             _uppercase,
    "titlecase":             _titlecase,
    "date_format":           _date_format,
    "number_normalize":      _number_normalize,
    "number_abs":            _number_abs,
    "number_negate":         _number_negate,
    "number_round":          _number_round,
    "regex_extract":         _regex_extract,
    "regex_replace":         _regex_replace,
    "replace":               _replace,
    "replace_map":           _replace_map,
    "concat":                _concat,
    "strip_chars":           _strip_chars,
    "split_take":            _split_take,
    "coalesce":              _coalesce,
    "conditional":           _conditional,
    "sign_from_column":      _sign_from_column,
    "embedding_categorize":  _embedding_categorize,
}


def apply_transform(transform_obj: dict, value: str, row: dict) -> str:
    """Applica una singola trasformazione e ritorna il nuovo valore."""
    t_type = transform_obj["type"]
    handler = _REGISTRY.get(t_type)
    if handler is None:
        raise ValueError(f"Transform type sconosciuto: {t_type!r}")
    result = handler(value, transform_obj, row)
    return "" if result is None else str(result)


def apply_pipeline(pipeline: list[dict], value: str, row: dict) -> str:
    """Applica una sequenza ordinata di trasformazioni."""
    for step in pipeline:
        value = apply_transform(step, value, row)
    return value
