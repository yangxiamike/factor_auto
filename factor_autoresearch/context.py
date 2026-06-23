"""Run-level immutable evaluation context."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from factor_autoresearch.config import ExperimentConfig


@dataclass(frozen=True)
class EvaluationContext:
    """Stable context shared by one evaluation run."""

    config: ExperimentConfig
    dataset_path: Path
    candidates_path: Path
    registry_path: Path
    runs_dir: Path
    run_id: str
    verbose: bool = False
    quiet: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "dataset_path", Path(self.dataset_path))
        object.__setattr__(self, "candidates_path", Path(self.candidates_path))
        object.__setattr__(self, "registry_path", Path(self.registry_path))
        object.__setattr__(self, "runs_dir", Path(self.runs_dir))

    @property
    def run_dir(self) -> Path:
        return self.runs_dir / self.run_id

    @property
    def manifest_path(self) -> Path:
        return self.run_dir / "manifest.json"

    @property
    def summary_path(self) -> Path:
        return self.run_dir / "summary.md"

    @property
    def logs_dir(self) -> Path:
        return self.run_dir / "logs"

    @property
    def factors_dir(self) -> Path:
        return self.run_dir / "factors"

    @property
    def results_dir(self) -> Path:
        return self.run_dir / "results"
