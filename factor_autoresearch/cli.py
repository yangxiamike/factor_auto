"""
CLI 入口模块: 负责解析命令行参数，并调度 dataset、screening、asset 和 legacy diagnose 流程。
不在这里拼装样本视图，也不在这里计算 Gate 指标。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer

from factor_autoresearch.block3_screening_runner import run_block3_screening
from factor_autoresearch.cleanup import clean_experiment_outputs
from factor_autoresearch.config import load_experiment_config
from factor_autoresearch.context import EvaluationContext
from factor_autoresearch.data_quality import FAIL, build_data_quality_report
from factor_autoresearch.evaluate import Evaluator, run_static_validation
from factor_autoresearch.factor_asset_benchmark import benchmark_admission_round, build_test_library
from factor_autoresearch.factor_assets import (
    get_factor_record,
    list_factor_records,
    rebuild_asset_store,
    retire_factor,
    summarize_batch_memory,
)
from factor_autoresearch.logging_config import configure_logging
from factor_autoresearch.prepare import prepare_fixed_dataset
from factor_autoresearch.sample_protocol import build_sample_protocol_from_dataset

# ============== Typer app 定义 ==============
app = typer.Typer(help="Factor autoresearch sandbox CLI.")
dataset_app = typer.Typer(help="Dataset commands.")
factor_app = typer.Typer(help="Factor commands.")
asset_app = typer.Typer(help="Asset commands.")
experiment_app = typer.Typer(help="Experiment commands.")

app.add_typer(dataset_app, name="dataset")
app.add_typer(factor_app, name="factor")
app.add_typer(asset_app, name="asset")
app.add_typer(experiment_app, name="experiment")


# ============== 默认配置 ==============
DEFAULT_CONFIG = Path("configs/csi500_ohlcv_sandbox_v1.toml")
DEFAULT_SCREENING_GATE_CONFIG = Path("configs/block3_screening_gate_v1.toml")
DEFAULT_ASSET_STORE = Path("factor_assets")


# ============== 输出辅助 ==============
def _echo_json(payload: dict[str, object]) -> None:
    """输出 JSON: 统一命令行结果的 JSON 打印方式。"""

    typer.echo(json.dumps(payload, ensure_ascii=False))



def _command_payload(command: str, **kwargs: object) -> dict[str, object]:
    """命令载荷: 统一补齐 ok 和 command 字段。"""

    return {"ok": True, "command": command, **kwargs}



def _exit_with_error(command: str, message: str, *, code: int = 1) -> None:
    """错误 JSON: 保证失败场景的 stdout 仍是稳定 JSON。"""

    _echo_json({"ok": False, "command": command, "error": {"message": message}})
    raise typer.Exit(code=code)



def _asset_run_id(prefix: str) -> str:
    """资产命令 run_id: 生成简短稳定的命令运行标识。"""

    return f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S')}"


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


@dataset_app.command("check-quality")
def dataset_check_quality(
    dataset: Annotated[Path, typer.Option(exists=True, file_okay=False)] = ...,
    config: Annotated[Path, typer.Option(exists=True)] = DEFAULT_CONFIG,
) -> None:
    """检查固定数据集质量: 生成 JSON/Markdown 报告，并在合同破坏时返回非零状态。"""
    experiment_config = load_experiment_config(config)
    report = build_data_quality_report(dataset, config=experiment_config)
    report_json_path = dataset / "data_quality_report.json"
    report_markdown_path = dataset / "data_quality_report.md"
    report_json_path.write_text(
        json.dumps(report.as_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    report_markdown_path.write_text(report.to_markdown(), encoding="utf-8")
    _echo_json(
        {
            "dataset": str(dataset),
            "overall_outcome": report.overall_outcome,
            "report_json": str(report_json_path),
            "report_markdown": str(report_markdown_path),
        }
    )
    if report.overall_outcome == FAIL:
        raise typer.Exit(code=1)


@dataset_app.command("show-slices")
def dataset_show_slices(
    dataset: Annotated[Path, typer.Option(exists=True, file_okay=False)] = ...,
    sample_protocol: Annotated[str | None, typer.Option("--sample-protocol")] = None,
) -> None:
    """展示样本切片: 从固定 dataset 生成稳定的 sample protocol 与 slices。"""
    protocol = build_sample_protocol_from_dataset(
        dataset,
        sample_protocol_id=sample_protocol,
    )
    _echo_json(protocol.as_dict())


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
    output_dir: Annotated[Path, typer.Option(file_okay=False)] = ...,
    config: Annotated[Path, typer.Option(exists=True)] = DEFAULT_CONFIG,
    screening_gate_config: Annotated[Path, typer.Option(exists=True)] = DEFAULT_SCREENING_GATE_CONFIG,
) -> None:
    """运行 Block3 screening: 作为研究因子入库筛选的主入口。"""
    summary = run_block3_screening(
        config_path=config,
        candidates_path=candidates,
        dataset_path=dataset,
        output_dir=output_dir,
        screening_gate_config_path=screening_gate_config,
    )
    _echo_json(
        {
            "output_dir": str(summary.output_dir),
            "evaluation_log": str(summary.evaluation_log_path),
            "research_factor_library": str(summary.research_factor_library_path),
            "replacement_queue": str(summary.replacement_queue_path),
            "total_candidates": summary.total_candidates,
            "admitted": summary.admitted_count,
            "rejected": summary.reject_count,
            "duplicates": summary.duplicate_count,
            "replace_candidates": summary.replace_candidate_count,
        }
    )


@factor_app.command("diagnose")
def factor_diagnose(
    dataset: Annotated[Path, typer.Option(exists=True, file_okay=False)] = ...,
    candidates: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = ...,
    run_id: Annotated[str, typer.Option()] = ...,
    config: Annotated[Path, typer.Option(exists=True)] = DEFAULT_CONFIG,
    registry: Annotated[Path, typer.Option()] = Path("candidate_factors/registry.jsonl"),
    runs_dir: Annotated[Path, typer.Option()] = Path("runs"),
    engine: Annotated[str, typer.Option()] = "legacy",
    jobs: Annotated[str, typer.Option()] = "auto",
    verbose: Annotated[bool, typer.Option("--verbose")] = False,
    quiet: Annotated[bool, typer.Option("--quiet")] = False,
) -> None:
    """旧评估诊断入口: 保留 Evaluator 链路用于诊断和回溯。"""
    experiment_config = load_experiment_config(config)
    context = EvaluationContext(
        config=experiment_config,
        dataset_path=dataset,
        candidates_path=candidates,
        registry_path=registry,
        runs_dir=runs_dir,
        run_id=run_id,
        engine=engine,
        jobs=jobs,
        verbose=verbose,
        quiet=quiet,
    )
    artifacts = Evaluator(context).evaluate_batch()
    _echo_json(
        {
            "run_id": run_id,
            "summary": str(artifacts.run_dir / "summary.md"),
            "log": str(artifacts.run_dir / "logs" / "evaluate.log"),
        }
    )


# ============== asset 命令 ==============
@asset_app.command("ingest-block3")
def asset_ingest_block3(
    dataset: Annotated[Path, typer.Option(exists=True, file_okay=False)] = ...,
    candidates: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = ...,
    output_dir: Annotated[Path, typer.Option(file_okay=False)] = ...,
    asset_store: Annotated[Path, typer.Option(file_okay=False)] = DEFAULT_ASSET_STORE,
    config: Annotated[Path, typer.Option(exists=True)] = DEFAULT_CONFIG,
    screening_gate_config: Annotated[Path, typer.Option(exists=True)] = DEFAULT_SCREENING_GATE_CONFIG,
    verbose: Annotated[bool, typer.Option("--verbose")] = False,
    quiet: Annotated[bool, typer.Option("--quiet")] = False,
) -> None:
    """摄入 Block3 结果: 跑 screening 并把结果写入区块4资产库。"""

    configure_logging(run_dir=asset_store, verbose=verbose, quiet=quiet, log_name="asset.log")
    summary = run_block3_screening(
        config_path=config,
        candidates_path=candidates,
        dataset_path=dataset,
        output_dir=output_dir,
        screening_gate_config_path=screening_gate_config,
        asset_store_dir=asset_store,
    )
    _echo_json(
        _command_payload(
            "asset.ingest-block3",
            asset_store=str(asset_store),
            output_dir=str(summary.output_dir),
            total_candidates=summary.total_candidates,
            admitted=summary.admitted_count,
            rejected=summary.reject_count,
            duplicates=summary.duplicate_count,
            replace_candidates=summary.replace_candidate_count,
            asset_log=str(asset_store / "logs" / "asset.log"),
        )
    )


@asset_app.command("list")
def asset_list(
    asset_store: Annotated[Path, typer.Option(file_okay=False)] = DEFAULT_ASSET_STORE,
    status: Annotated[str | None, typer.Option()] = None,
) -> None:
    """列出资产库因子: 按状态筛选当前快照记录。"""

    items = list_factor_records(asset_store, status=status)
    _echo_json(
        _command_payload(
            "asset.list",
            asset_store=str(asset_store),
            items=items,
            total=len(items),
        )
    )


@asset_app.command("show")
def asset_show(
    factor_id: Annotated[str, typer.Argument()],
    asset_store: Annotated[Path, typer.Option(file_okay=False)] = DEFAULT_ASSET_STORE,
) -> None:
    """展示资产详情: 返回单个因子的状态快照。"""

    record = get_factor_record(asset_store, factor_id)
    if record is None:
        _exit_with_error("asset.show", f"factor not found: {factor_id}")
    _echo_json(_command_payload("asset.show", asset_store=str(asset_store), asset=record))


@asset_app.command("retire")
def asset_retire(
    factor_id: Annotated[str, typer.Argument()],
    asset_store: Annotated[Path, typer.Option(file_okay=False)] = DEFAULT_ASSET_STORE,
    reason: Annotated[str, typer.Option()] = "manual_retire",
    source_run_id: Annotated[str | None, typer.Option()] = None,
    verbose: Annotated[bool, typer.Option("--verbose")] = False,
    quiet: Annotated[bool, typer.Option("--quiet")] = False,
) -> None:
    """退役 active 因子: 只改状态，不删除值文件。"""

    record = get_factor_record(asset_store, factor_id)
    if record is None:
        _exit_with_error("asset.retire", f"factor not found: {factor_id}")
    configure_logging(run_dir=asset_store, verbose=verbose, quiet=quiet, log_name="asset.log")
    retire_factor(
        asset_store,
        factor_id=factor_id,
        source_run_id=source_run_id or _asset_run_id("asset_retire"),
        reason=reason,
        created_at=datetime.now().astimezone().isoformat(timespec="seconds"),
    )
    updated = get_factor_record(asset_store, factor_id)
    _echo_json(
        _command_payload(
            "asset.retire",
            asset_store=str(asset_store),
            factor_id=factor_id,
            previous_status=record["status"],
            current_status=updated["status"],
            asset_log=str(asset_store / "logs" / "asset.log"),
        )
    )


@asset_app.command("rebuild-index")
def asset_rebuild_index(
    asset_store: Annotated[Path, typer.Option(file_okay=False)] = DEFAULT_ASSET_STORE,
    verbose: Annotated[bool, typer.Option("--verbose")] = False,
    quiet: Annotated[bool, typer.Option("--quiet")] = False,
) -> None:
    """重建索引: 从事件账本恢复快照、批次记忆和查询索引。"""

    configure_logging(run_dir=asset_store, verbose=verbose, quiet=quiet, log_name="asset.log")
    paths = rebuild_asset_store(asset_store)
    _echo_json(
        _command_payload(
            "asset.rebuild-index",
            asset_store=str(asset_store),
            rebuilt_paths={key: str(value) for key, value in paths.items() if key != "root"},
            asset_log=str(asset_store / "logs" / "asset.log"),
        )
    )


@asset_app.command("summarize-memory")
def asset_summarize_memory(
    asset_store: Annotated[Path, typer.Option(file_okay=False)] = DEFAULT_ASSET_STORE,
) -> None:
    """汇总批次记忆: 输出 source_run 维度的记忆记录。"""

    items = summarize_batch_memory(asset_store)
    _echo_json(
        _command_payload(
            "asset.summarize-memory",
            asset_store=str(asset_store),
            items=items,
            total=len(items),
        )
    )


@asset_app.command("build-test-library")
def asset_build_test_library(
    asset_store: Annotated[Path, typer.Option(file_okay=False)] = DEFAULT_ASSET_STORE,
    library_size: Annotated[int, typer.Option()] = 30,
    dataset: Annotated[Path | None, typer.Option(exists=True, file_okay=False)] = None,
    config: Annotated[Path, typer.Option(exists=True)] = DEFAULT_CONFIG,
    screening_gate_config: Annotated[Path, typer.Option(exists=True)] = DEFAULT_SCREENING_GATE_CONFIG,
    verbose: Annotated[bool, typer.Option("--verbose")] = False,
    quiet: Annotated[bool, typer.Option("--quiet")] = False,
) -> None:
    """构造测试库: 生成一批可复用 active 因子和值文件。"""

    configure_logging(run_dir=asset_store, verbose=verbose, quiet=quiet, log_name="asset.log")
    summary = build_test_library(
        asset_store,
        library_size=library_size,
        config_path=config if dataset is not None else None,
        dataset_path=dataset,
        screening_gate_config_path=screening_gate_config if dataset is not None else None,
    )
    _echo_json(
        _command_payload(
            "asset.build-test-library",
            **summary.as_dict(),
            asset_log=str(asset_store / "logs" / "asset.log"),
        )
    )


@asset_app.command("benchmark-admission-round")
def asset_benchmark_admission_round(
    dataset: Annotated[Path, typer.Option(exists=True, file_okay=False)] = ...,
    candidates: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = ...,
    output_dir: Annotated[Path, typer.Option(file_okay=False)] = ...,
    asset_store: Annotated[Path, typer.Option(file_okay=False)] = DEFAULT_ASSET_STORE,
    config: Annotated[Path, typer.Option(exists=True)] = DEFAULT_CONFIG,
    screening_gate_config: Annotated[Path, typer.Option(exists=True)] = DEFAULT_SCREENING_GATE_CONFIG,
    verbose: Annotated[bool, typer.Option("--verbose")] = False,
    quiet: Annotated[bool, typer.Option("--quiet")] = False,
) -> None:
    """测量 admission round: 输出区块4 benchmark JSON 摘要。"""

    configure_logging(run_dir=asset_store, verbose=verbose, quiet=quiet, log_name="asset.log")
    benchmark = benchmark_admission_round(
        config_path=config,
        candidates_path=candidates,
        dataset_path=dataset,
        output_dir=output_dir,
        screening_gate_config_path=screening_gate_config,
        asset_store_dir=asset_store,
    )
    _echo_json(
        _command_payload(
            "asset.benchmark-admission-round",
            **benchmark.as_dict(),
            asset_log=str(asset_store / "logs" / "asset.log"),
        )
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

