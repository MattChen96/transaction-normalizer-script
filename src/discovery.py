"""
Fase 1 — Discovery: scansione delle cartelle sources/* per file supportati.
Ignora config.json e sample.* (usati solo per configurazione e test).
"""
from __future__ import annotations

from pathlib import Path

SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls"}
EXCLUDE_FILES = {"config.json"}
EXCLUDE_PREFIXES = {"sample"}


def discover_input_files(sources_dir: Path) -> list[tuple[Path, str]]:
    """
    Scansiona sources_dir e ritorna lista di (file_path, source_name).
    
    Per ogni cartella in sources/:
      - se contiene config.json, è una sorgente valida
      - cerca file supportati (escludendo config.json e sample.*)
      - restituisce (file_path, cartella_name)
    
    Ritorna lista vuota se nessun file trovato.
    """
    if not sources_dir.exists():
        return []

    files_with_source: list[tuple[Path, str]] = []
    
    for source_dir in sorted(sources_dir.iterdir()):
        if not source_dir.is_dir():
            continue
        
        # Sorgente valida solo se ha config.json
        if not (source_dir / "config.json").exists():
            continue
        
        source_name = source_dir.name
        
        # Cerca file supportati nella cartella (escludi config.json e sample.*)
        for file_path in sorted(source_dir.iterdir()):
            if not file_path.is_file():
                continue
            
            # Escludi config.json
            if file_path.name == "config.json":
                continue
            
            # Escludi sample.*
            if file_path.stem.lower() == "sample":
                continue
            
            # Includi solo estensioni supportate
            if file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                files_with_source.append((file_path, source_name))
    
    return files_with_source


def discover_unsupported_files(sources_dir: Path) -> list[tuple[Path, str]]:
    """Ritorna file con estensione non supportata in sources/*/"""
    if not sources_dir.exists():
        return []

    unsupported: list[tuple[Path, str]] = []
    
    for source_dir in sorted(sources_dir.iterdir()):
        if not source_dir.is_dir() or not (source_dir / "config.json").exists():
            continue
        
        source_name = source_dir.name
        
        for file_path in sorted(source_dir.iterdir()):
            if not file_path.is_file():
                continue
            if file_path.name == "config.json" or file_path.stem.lower() == "sample":
                continue
            if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                unsupported.append((file_path, source_name))
    
    return unsupported
