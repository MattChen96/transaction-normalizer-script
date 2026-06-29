"""
Caricamento e validazione strutturale dei config.json sorgente.
Usa JSON Schema (schemas/source_config_schema.json) per la validazione.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

_SCHEMA_PATH = Path(__file__).parent.parent / "schemas" / "source_config_schema.json"


def _load_json_strict(path: Path) -> Any:
    """Carica un file JSON segnalando chiavi duplicate come errore."""
    seen_keys: dict[str, list[str]] = {}

    def object_pairs_hook(pairs: list[tuple[str, Any]]) -> dict:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                seen_keys.setdefault(str(path), []).append(key)
            result[key] = value
        return result

    with path.open(encoding="utf-8") as f:
        data = json.load(f, object_pairs_hook=object_pairs_hook)

    if seen_keys:
        dupes = ", ".join(seen_keys.get(str(path), []))
        raise ValueError(f"E_CONFIG_DUPLICATE_KEY: chiavi duplicate trovate: {dupes}")

    return data


def load_source_config(source_dir: Path) -> dict[str, Any]:
    """
    Carica e valida strutturalmente il config.json di una sorgente.

    Lancia:
        FileNotFoundError  → E_CONFIG_NOT_FOUND
        json.JSONDecodeError → E_CONFIG_INVALID_JSON
        ValueError         → E_CONFIG_DUPLICATE_KEY
        jsonschema.ValidationError → E_CONFIG_SCHEMA_FAIL
    """
    config_path = source_dir / "config.json"

    if not config_path.exists():
        raise FileNotFoundError(
            f"E_CONFIG_NOT_FOUND: {config_path} non trovato"
        )

    try:
        config = _load_json_strict(config_path)
    except json.JSONDecodeError as exc:
        raise json.JSONDecodeError(
            f"E_CONFIG_INVALID_JSON: {config_path}: {exc.msg}",
            exc.doc,
            exc.pos,
        ) from exc

    schema = _load_json_strict(_SCHEMA_PATH)

    try:
        jsonschema.validate(config, schema)
    except jsonschema.ValidationError as exc:
        raise jsonschema.ValidationError(
            f"E_CONFIG_SCHEMA_FAIL: {config_path}: {exc.message}"
        ) from exc

    return config


def get_all_input_columns(config: dict[str, Any]) -> list[str]:
    """
    Raccoglie tutti i nomi di colonne di input referenziate nel config
    (in fields, filters). Usato per il header matching nel source detector
    e per la validazione di coerenza.
    """
    columns: set[str] = set()

    for field_def in config.get("fields", {}).values():
        if "input_column" in field_def:
            columns.add(field_def["input_column"])
        for col in field_def.get("input_columns", []):
            columns.add(col)
        for step in field_def.get("transform", []):
            if step.get("type") == "sign_from_column":
                columns.add(step["column"])
            if step.get("type") == "conditional":
                for cond in step.get("conditions", []):
                    columns.add(cond["if_column"])
            if step.get("type") == "coalesce":
                for col in step.get("columns", []):
                    columns.add(col)

    filters = config.get("filters", {})
    for rule in filters.get("include", []) + filters.get("exclude", []):
        columns.add(rule["column"])

    return sorted(columns)
