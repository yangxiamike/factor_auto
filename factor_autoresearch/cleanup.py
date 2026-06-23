"""负责清理指定实验的 run 目录和 registry 记录。"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path


# ============== 清理结果 ==============

@dataclass(frozen=True)
class CleanupReport:
    """描述一次清理操作命中的 run 和 registry 记录。"""

    experiment_id: str
    run_ids: list[str]
    registry_removed: int
    dry_run: bool


# ============== 清理入口 ==============

def clean_experiment_outputs(
    *,
    experiment_id: str,
    runs_dir: Path,
    registry_path: Path,
    yes: bool,
) -> CleanupReport:
    """按实验 ID 清理 runs 目录和 registry，支持 dry-run。"""
    runs_dir = runs_dir.resolve()
    registry_path = registry_path.resolve()
    run_targets: list[Path] = []
    for child in runs_dir.iterdir():
        if not child.is_dir():
            continue
        manifest_path = child / "manifest.json"
        if not manifest_path.exists():
            continue
        with manifest_path.open("r", encoding="utf-8") as handle:
            manifest = json.load(handle)
        if manifest.get("experiment_id") == experiment_id:
            run_targets.append(child)

    remaining_lines: list[str] = []
    removed = 0
    if registry_path.exists():
        with registry_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                text = line.strip()
                if not text:
                    continue
                payload = json.loads(text)
                if payload.get("experiment_id") == experiment_id:
                    removed += 1
                else:
                    remaining_lines.append(text)

    if yes:
        for target in run_targets:
            resolved = target.resolve()
            if runs_dir not in resolved.parents:
                raise ValueError(f"refusing to delete outside runs dir: {resolved}")
            shutil.rmtree(resolved)
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = registry_path.with_suffix(".tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            for line in remaining_lines:
                handle.write(line + "\n")
        temp_path.replace(registry_path)

    return CleanupReport(
        experiment_id=experiment_id,
        run_ids=[path.name for path in run_targets],
        registry_removed=removed,
        dry_run=not yes,
    )
