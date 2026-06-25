"""负责保存单次评估运行共享的稳定上下文。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from factor_autoresearch.config import ExperimentConfig

# ============== 运行上下文 ==============

@dataclass(frozen=True)
class EvaluationContext:
    """保存一次 evaluate run 共享的路径与配置。"""

    config: ExperimentConfig
    dataset_path: Path
    candidates_path: Path
    registry_path: Path
    runs_dir: Path
    run_id: str
    engine: str = "legacy"
    jobs: str = "auto"
    verbose: bool = False
    quiet: bool = False

    def __post_init__(self) -> None:
        """统一把路径字段规范成 Path 对象。"""
        object.__setattr__(self, "dataset_path", Path(self.dataset_path))
        object.__setattr__(self, "candidates_path", Path(self.candidates_path))
        object.__setattr__(self, "registry_path", Path(self.registry_path))
        object.__setattr__(self, "runs_dir", Path(self.runs_dir))
        if self.engine not in {"legacy", "v1"}:
            raise ValueError("engine must be one of: legacy, v1")
        if self.jobs != "auto":
            try:
                jobs_value = int(self.jobs)
            except ValueError as exc:
                raise ValueError("jobs must be 'auto' or a positive integer") from exc
            if jobs_value < 1:
                raise ValueError("jobs must be 'auto' or a positive integer")

    @property
    def run_dir(self) -> Path:
        """返回当前 run 的根目录。"""
        return self.runs_dir / self.run_id

    @property
    def manifest_path(self) -> Path:
        """返回 manifest 文件路径。"""
        return self.run_dir / "manifest.json"

    @property
    def summary_path(self) -> Path:
        """返回 summary 文件路径。"""
        return self.run_dir / "summary.md"

    @property
    def logs_dir(self) -> Path:
        """返回日志目录路径。"""
        return self.run_dir / "logs"

    @property
    def factors_dir(self) -> Path:
        """返回因子产物目录路径。"""
        return self.run_dir / "factors"

    @property
    def results_dir(self) -> Path:
        """返回结果产物目录路径。"""
        return self.run_dir / "results"

    @property
    def diagnostics_path(self) -> Path:
        """Return the diagnostics parquet path for the current run."""
        return self.results_dir / "diagnostics.parquet"
