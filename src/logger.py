"""
Logger strutturato per ogni run ETL.
Scrive su console e su file in logs/ con timestamp nel nome.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class RunStats:
    """Contatori aggregati per il report finale."""
    files_processed: int = 0
    files_skipped: int = 0
    rows_read: int = 0
    rows_filtered: int = 0
    rows_mapped: int = 0
    rows_errors: int = 0
    rows_output: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class RunLogger:
    """
    Logger per una singola run ETL.
    Produce un file di log strutturato in logs/run_<run_id>.log.
    """

    _FMT = "[%(asctime)s] [%(levelname)-8s] %(message)s"
    _DATE_FMT = "%Y-%m-%d %H:%M:%S"

    def __init__(self, run_id: str, logs_dir: Path) -> None:
        self.run_id = run_id
        self.stats = RunStats()

        logs_dir.mkdir(parents=True, exist_ok=True)
        log_file = logs_dir / f"run_{run_id}.log"

        logger = logging.getLogger(f"etl.{run_id}")
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

        formatter = logging.Formatter(self._FMT, datefmt=self._DATE_FMT)

        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        logger.addHandler(fh)

        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

        self._logger = logger

    # ── livelli base ──────────────────────────────────────────────────────────

    def info(self, msg: str) -> None:
        self._logger.info(msg)

    def warning(self, msg: str) -> None:
        self._logger.warning(msg)
        self.stats.warnings.append(msg)

    def error(self, msg: str) -> None:
        self._logger.error(msg)
        self.stats.errors.append(msg)

    def critical(self, msg: str) -> None:
        self._logger.critical(msg)
        self.stats.errors.append(msg)

    # ── log strutturati ───────────────────────────────────────────────────────

    def log_row_error(
        self,
        filename: str,
        row_index: int,
        field: str,
        code: str,
        value: str,
    ) -> None:
        msg = (
            f"File: {filename} | Row: {row_index} | "
            f"Field: {field} | Code: {code} | Value: {value!r}"
        )
        self.error(msg)

    def log_row_warning(
        self,
        filename: str,
        row_index: int,
        field: str,
        code: str,
        value: str,
        fallback: str = "",
    ) -> None:
        parts = (
            f"File: {filename} | Row: {row_index} | "
            f"Field: {field} | Code: {code} | Value: {value!r}"
        )
        if fallback:
            parts += f" → fallback: {fallback!r}"
        self.warning(parts)

    def log_file_stats(
        self,
        filename: str,
        rows_read: int,
        rows_filtered: int,
        rows_mapped: int,
        rows_errors: int,
    ) -> None:
        self.info(
            f"Rows read: {rows_read} | "
            f"Rows filtered: {rows_filtered} | "
            f"Rows mapped: {rows_mapped} | "
            f"Rows with errors: {rows_errors}"
        )
        self.stats.rows_read += rows_read
        self.stats.rows_filtered += rows_filtered
        self.stats.rows_mapped += rows_mapped
        self.stats.rows_errors += rows_errors
        self.stats.rows_output += rows_mapped - rows_errors

    def print_summary(self) -> None:
        s = self.stats
        self.info(
            f"Run completed. "
            f"Total output rows: {s.rows_output} | "
            f"Errors: {len(s.errors)} | "
            f"Warnings: {len(s.warnings)}"
        )
