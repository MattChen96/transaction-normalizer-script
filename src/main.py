"""
Entry point del Transaction Normalizer.

Utilizzo:
    python -m src.main                              # run ETL completo
    python -m src.main --validate-only sources/trade_republic/  # validazione standalone
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import jsonschema

from src.config_loader import load_source_config, get_all_input_columns
from src.discovery import discover_input_files, discover_unsupported_files
from src.exporter import export_csv, export_excel, export_rejected
from src.field_mapper import map_dataframe
from src.file_reader import read_file
from src.logger import RunLogger
from src.output_validator import validate_output
from src.row_filter import apply_filters
from src.source_detector import detect_source, SourceDetectionError

# ── Percorsi di progetto ──────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent
SOURCES_DIR = PROJECT_ROOT / "sources"
OUTPUT_DIR = PROJECT_ROOT / "output"
LOGS_DIR = PROJECT_ROOT / "logs"


# ── Modalità: validazione standalone ─────────────────────────────────────────

def run_validate_only(source_path: Path, logger: RunLogger) -> bool:
    """
    Valida la struttura di un config.json senza elaborare dati reali.
    Ritorna True se la validazione passa (anche con warning).
    """
    source_dir = Path(source_path)
    if not source_dir.is_dir():
        logger.critical(f"Path non valido: {source_dir}")
        return False

    logger.info(f"VALIDATION REPORT — {source_dir / 'config.json'}")
    logger.info("=" * 52)

    try:
        config = load_source_config(source_dir)
    except FileNotFoundError as exc:
        logger.critical(str(exc))
        return False
    except json.JSONDecodeError as exc:
        logger.critical(str(exc))
        return False
    except jsonschema.ValidationError as exc:
        logger.critical(str(exc))
        return False
    except ValueError as exc:
        logger.critical(str(exc))
        return False

    logger.info(f"Status: PASSED")
    logger.info(f"Source: {config['source']['name']}")
    if not config["source"].get("version"):
        logger.warning("W002: source.version non presente")

    # Verifica sample.csv / sample.xlsx
    _check_sample(source_dir, config, logger)

    return True


def _check_sample(
    source_dir: Path,
    config: dict,
    logger: RunLogger,
) -> None:
    sample = next(
        (p for p in source_dir.iterdir() if p.stem.lower() == "sample"),
        None,
    )
    if sample is None:
        logger.warning("W003: nessun file sample trovato nella cartella sorgente")
        return

    try:
        from src.file_reader import read_file
        df = read_file(sample, config["file"])
        headers = set(df.columns.str.strip())
    except Exception as exc:
        logger.warning(f"W003: impossibile leggere il sample: {exc}")
        return

    declared_cols = get_all_input_columns(config)
    for col in declared_cols:
        if col.strip() not in headers:
            logger.warning(f"W001: colonna '{col}' dichiarata nel config non trovata nel sample")


# ── Run ETL principale ────────────────────────────────────────────────────────

def run_etl(
    sources_dir: Path,
    output_dir: Path,
    logger: RunLogger,
) -> None:
    """Esegue il pipeline ETL completo su tutti i file in sources/*/"""

    # Fase 1 — Discovery: scansiona sources/*/ per file supportati
    files_with_sources = discover_input_files(sources_dir)
    unsupported = discover_unsupported_files(sources_dir)

    for file_path, source_name in unsupported:
        logger.warning(f"W_FILE_SKIPPED: {file_path.name} — estensione non supportata")

    if not files_with_sources:
        logger.info("Nessun file da elaborare in sources/*/")
        return

    logger.info(f"Run started. Found {len(files_with_sources)} file(s)")

    all_output_frames = []
    all_rejected_frames = []

    for file_path, source_name in files_with_sources:
        _process_file(file_path, source_name, sources_dir, all_output_frames, all_rejected_frames, logger)

    # Fase 8 — Export (merge)
    if all_output_frames:
        import pandas as pd
        merged = pd.concat(all_output_frames, ignore_index=True)
        csv_path = export_csv(merged, output_dir, logger.run_id)
        excel_path = export_excel(merged, output_dir, logger.run_id)
        logger.info(f"Output CSV scritto: {csv_path} ({len(merged)} righe)")
        logger.info(f"Output XLSX scritto: {excel_path} ({len(merged)} righe)")
        logger.stats.files_processed += 1
    else:
        logger.warning("W_NO_VALID_ROWS: nessuna riga valida prodotta. Nessun file di output.")

    if all_rejected_frames:
        import pandas as pd
        merged_rejected = pd.concat(all_rejected_frames, ignore_index=True)
        rej_path = export_rejected(merged_rejected, output_dir, logger.run_id)
        if rej_path:
            logger.info(f"Scarti scritti: {rej_path} ({len(merged_rejected)} righe)")

    logger.print_summary()


def _process_file(
    file_path: Path,
    source_name: str,
    sources_dir: Path,
    all_output_frames: list,
    all_rejected_frames: list,
    logger: RunLogger,
) -> None:
    """Elabora un singolo file attraverso le fasi 2–7."""

    filename = file_path.name

    # Fase 2 — Source Detection
    try:
        source_name, config = detect_source(file_path, source_name, sources_dir)
    except SourceDetectionError as exc:
        logger.critical(str(exc))
        logger.stats.files_skipped += 1
        return

    logger.info(f"Processing: {filename} → source: {source_name}")

    # Fase 4 — File Reading
    try:
        df_raw = read_file(file_path, config["file"])
    except (OSError, ValueError) as exc:
        logger.critical(str(exc))
        logger.stats.files_skipped += 1
        return

    rows_read = len(df_raw)

    # Fase 5 — Row Filtering
    filters_cfg = config.get("filters", {})
    df_filtered, df_filter_rejected = apply_filters(df_raw, filters_cfg)
    n_filtered = len(df_filter_rejected)

    if n_filtered > 0:
        logger.info(f"W_ROWS_FILTERED: {n_filtered} righe scartate dai filtri")
        df_filter_rejected["_source_file"] = filename
        all_rejected_frames.append(df_filter_rejected)

    # Fase 6 — Field Mapping
    df_output, df_map_rejected, n_errors = map_dataframe(
        df_filtered, config["fields"], filename, logger
    )

    if not df_map_rejected.empty:
        df_map_rejected["_source_file"] = filename
        all_rejected_frames.append(df_map_rejected)

    # Fase 7 — Output Validation
    try:
        df_valid = validate_output(df_output, filename, logger)
    except ValueError as exc:
        logger.critical(str(exc))
        logger.stats.files_skipped += 1
        return

    validation_errors = len(df_output) - len(df_valid)
    n_errors += validation_errors

    rows_mapped = len(df_valid)

    logger.log_file_stats(
        filename=filename,
        rows_read=rows_read,
        rows_filtered=n_filtered,
        rows_mapped=rows_mapped,
        rows_errors=n_errors,
    )

    if not df_valid.empty:
        all_output_frames.append(df_valid)
    else:
        logger.warning(f"W_NO_VALID_ROWS: {filename} — nessuna riga valida dopo mapping e validazione")


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Transaction Normalizer — ETL pipeline per estratti conto"
    )
    parser.add_argument(
        "--validate-only",
        metavar="SOURCE_DIR",
        help="Valida il config.json di una sorgente senza elaborare dati reali",
    )
    parser.add_argument(
        "--sources-dir",
        metavar="PATH",
        default=str(SOURCES_DIR),
        help=f"Cartella sorgenti (default: {SOURCES_DIR})",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    logger = RunLogger(run_id, LOGS_DIR)

    if args.validate_only:
        success = run_validate_only(Path(args.validate_only), logger)
        return 0 if success else 1

    run_etl(
        sources_dir=Path(args.sources_dir),
        output_dir=OUTPUT_DIR,
        logger=logger,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
