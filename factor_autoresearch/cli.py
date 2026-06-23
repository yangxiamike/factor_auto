"""
CLI 入口模块: 负责解析命令行参数、加载实验配置，并调用数据集准备、
因子校验、因子评估与实验清理等流程能力。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from factor_autoresearch.cleanup import clean_experiment_outputs
from factor_autoresearch.config import load_experiment_config
from factor_autoresearch.context import EvaluationContext
from factor_autoresearch.evaluate import Evaluator, run_static_validation
from factor_autoresearch.prepare import prepare_fixed_dataset

# ============== Typer app 定义 ==============
app = typer.Typer(help="Factor autoresearch sandbox CLI.")
dataset_app = typer.Typer(help="Dataset commands.")
factor_app = typer.Typer(help="Factor commands.")
experiment_app = typer.Typer(help="Experiment commands.")

app.add_typer(dataset_app, name="dataset")
app.add_typer(factor_app, name="factor")
app.add_typer(experiment_app, name="experiment")


# ============== 默认配置 ==============
DEFAULT_CONFIG = Path("configs/csi500_ohlcv_sandbox_v1.toml")


def _echo_json(payload: dict[str, object]) -> None:
    """输出 JSON: 统一命令行结果的 JSON 打印方式。"""
    typer.echo(json.dumps(payload, ensure_ascii=False))


# ============== dataset 命令 ==============
@dataset_app.command("prepare-fixed")
def dataset_prepare_fixed(
    config: Annotated[Path, typer.Option(exists=True)] = DEFAULT_CONFIG,
    output: Annotated[Path, typer.Option(file_okay=False)] = ...,
) -> None:
    """准备固定数据集: 根据配置生成评估所需的标准 dataset 目录。"""
    experiment_config = load_experiment_config(config)
    prepared = prepare_fixed_dataset(config=experiment_config, output_path=output)
    _echo_json(
        {
            "dataset_id": prepared.manifest["dataset_id"],
            "output": str(output),
            "rows": len(prepared.panel),
        }
    )


# ============== factor 命令 ==============
@factor_app.command("validate")
def factor_validate(
    dataset: Annotated[Path, typer.Option(exists=True, file_okay=False)] = ...,
    candidates: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = ...,
    config: Annotated[Path, typer.Option(exists=True)] = DEFAULT_CONFIG,
    verbose: Annotated[bool, typer.Option("--verbose")] = False,
) -> None:
    """校验因子: 检查候选因子在给定 dataset 上是否通过静态验证。"""
    _ = verbose
    experiment_config = load_experiment_config(config)
    results = run_static_validation(
        candidates_path=candidates,
        dataset_path=dataset,
        config=experiment_config,
    )
    invalid = [item for item in results if item["status"] != "valid"]
    _echo_json(
        {
            "checked": len(results),
            "invalid": len(invalid),
            "dataset": str(dataset),
        }
    )
    if invalid:
        raise typer.Exit(code=1)


@factor_app.command("evaluate")
def factor_evaluate(
    dataset: Annotated[Path, typer.Option(exists=True, file_okay=False)] = ...,
    candidates: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = ...,
    run_id: Annotated[str, typer.Option()] = ...,
    config: Annotated[Path, typer.Option(exists=True)] = DEFAULT_CONFIG,
    registry: Annotated[Path, typer.Option()] = Path("candidate_factors/registry.jsonl"),
    runs_dir: Annotated[Path, typer.Option()] = Path("runs"),
    verbose: Annotated[bool, typer.Option("--verbose")] = False,
    quiet: Annotated[bool, typer.Option("--quiet")] = False,
) -> None:
    """评估因子: 运行候选因子批量评估并输出本次 run 的产物位置。"""
    experiment_config = load_experiment_config(config)
    context = EvaluationContext(
        config=experiment_config,
        dataset_path=dataset,
        candidates_path=candidates,
        registry_path=registry,
        runs_dir=runs_dir,
        run_id=run_id,
        verbose=verbose,
        quiet=quiet,
    )
    evaluator = Evaluator(context)
    artifacts = evaluator.evaluate_batch()
    _echo_json(
        {
            "run_id": run_id,
            "summary": str(artifacts.run_dir / "summary.md"),
            "log": str(artifacts.run_dir / "logs" / "evaluate.log"),
        }
    )


# ============== experiment 命令 ==============
@experiment_app.command("clean")
def experiment_clean(
    experiment_id: Annotated[str, typer.Option()] = ...,
    yes: Annotated[bool, typer.Option("--yes")] = False,
    runs_dir: Annotated[Path, typer.Option()] = Path("runs"),
    registry: Annotated[Path, typer.Option()] = Path("candidate_factors/registry.jsonl"),
) -> None:
    """清理实验: 删除实验运行目录并同步清理注册表记录。"""
    report = clean_experiment_outputs(
        experiment_id=experiment_id,
        runs_dir=runs_dir,
        registry_path=registry,
        yes=yes,
    )
    _echo_json(
        {
            "experiment_id": report.experiment_id,
            "run_ids": report.run_ids,
            "registry_removed": report.registry_removed,
            "dry_run": report.dry_run,
        }
    )


# ============== 主入口 ==============
def main() -> None:
    """启动 CLI: 挂载并执行 factor autoresearch 的命令行应用。"""
    app()
