from pathlib import Path
import logging

from factor_autoresearch.logging_config import configure_logging


def test_configure_logging_creates_file_handler(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    configure_logging(run_dir=run_dir, verbose=True, quiet=False)
    logger = logging.getLogger("factor_autoresearch.test")
    logger.info("hello", extra={"run_id": "run1", "candidate_id": "c1", "stage": "test"})
    configure_logging(run_dir=run_dir, verbose=False, quiet=False)
    assert (run_dir / "logs" / "evaluate.log").exists()
