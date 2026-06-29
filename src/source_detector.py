"""
Fase 2 — Source Detection: già determinato dal percorso del file.

Il discovery ritorna (file_path, source_name) basato sulla cartella
in sources/*/. Qui carichiamo il config per quella sorgente.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from src.config_loader import load_source_config


class SourceDetectionError(Exception):
    """Raised when source config cannot be loaded."""
    pass


def detect_source(
    file_path: Path,
    source_name: str,
    sources_dir: Path,
) -> tuple[str, dict[str, Any]]:
    """
    Carica il config per la sorgente data.
    
    Parametri:
      file_path: path del file (solo per logging)
      source_name: nome della cartella sorgente (es. 'trade_republic')
      sources_dir: percorso a sources/
    
    Ritorna:
      (source_name, config_dict)
    
    Lancia:
      SourceDetectionError se il config non esiste o è invalido
    """
    source_dir = sources_dir / source_name
    
    if not source_dir.is_dir():
        raise SourceDetectionError(
            f"E_SOURCE_NOT_FOUND: sources/{source_name} non esiste"
        )
    
    try:
        config = load_source_config(source_dir)
        return source_name, config
    except Exception as exc:
        raise SourceDetectionError(
            f"E_CONFIG_LOAD_ERROR: {source_dir / 'config.json'}: {exc}"
        ) from exc
