from __future__ import annotations

import logging
import sys
from pathlib import Path

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s run=%(run_id)s candidate=%(candidate_id)s stage=%(stage)s %(message)s"


def configure_logging(
    *,
    run_dir: Path | None,
    verbose: bool,
    quiet: bool = False,
) -> None:
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers.clear()

    formatter = logging.Formatter(
        LOG_FORMAT,
        defaults={"run_id": "-", "candidate_id": "-", "stage": "-"},
    )
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.WARNING if quiet else logging.DEBUG if verbose else logging.INFO)
    root.addHandler(console_handler)

    if run_dir is not None:
        logs_dir = run_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(logs_dir / "evaluate.log", encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)
        root.addHandler(file_handler)
