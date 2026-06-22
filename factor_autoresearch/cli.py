from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from factor_autoresearch.cleanup import clean_experiment_outputs
from factor_autoresearch.config import load_experiment_config
from factor_autoresearch.evaluate import Evaluator, run_static_validation
from factor_autoresearch.prepare import prepare_fixed_dataset

app = typer.Typer(help="Factor autoresearch sandbox CLI.")
dataset_app = typer.Typer(help="Dataset commands.")
factor_app = typer.Typer(help="Factor commands.")
experiment_app = typer.Typer(help="Experiment commands.")

app.add_typer(dataset_app, name="dataset")
app.add_typer(factor_app, name="factor")
app.add_typer(experiment_app, name="experiment")


DEFAULT_CONFIG = Path("configs/csi500_ohlcv_sandbox_v1.toml")


@dataset_app.command("prepare-fixed")
def dataset_prepare_fixed(
    config: Annotated[Path, typer.Option(exists=True)] = DEFAULT_CONFIG,
    output: Annotated[Path, typer.Option(file_okay=False)] = ...,
) -> None:
    experiment_config = load_experiment_config(config)
    prepared = prepare_fixed_dataset(config=experiment_config, output_path=output)
    typer.echo(
        json.dumps(
            {
                "dataset_id": prepared.manifest["dataset_id"],
                "output": str(output),
                "rows": len(prepared.panel),
            },
            ensure_ascii=False,
        )
    )


@factor_app.command("validate")
def factor_validate(
    dataset: Annotated[Path, typer.Option(exists=True, file_okay=False)] = ...,
    candidates: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = ...,
    config: Annotated[Path, typer.Option(exists=True)] = DEFAULT_CONFIG,
    verbose: Annotated[bool, typer.Option("--verbose")] = False,
) -> None:
    _ = verbose
    experiment_config = load_experiment_config(config)
    results = run_static_validation(
        candidates_path=candidates,
        dataset_path=dataset,
        config=experiment_config,
    )
    invalid = [item for item in results if item["status"] != "valid"]
    typer.echo(
        json.dumps(
            {
                "checked": len(results),
                "invalid": len(invalid),
                "dataset": str(dataset),
            },
            ensure_ascii=False,
        )
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
    experiment_config = load_experiment_config(config)
    evaluator = Evaluator(
        config=experiment_config,
        dataset_path=dataset,
        candidates_path=candidates,
        registry_path=registry,
        runs_dir=runs_dir,
        run_id=run_id,
        verbose=verbose,
        quiet=quiet,
    )
    artifacts = evaluator.evaluate_batch()
    typer.echo(
        json.dumps(
            {
                "run_id": run_id,
                "summary": str(artifacts.run_dir / "summary.md"),
                "log": str(artifacts.run_dir / "logs" / "evaluate.log"),
            },
            ensure_ascii=False,
        )
    )


@experiment_app.command("clean")
def experiment_clean(
    experiment_id: Annotated[str, typer.Option()] = ...,
    yes: Annotated[bool, typer.Option("--yes")] = False,
    runs_dir: Annotated[Path, typer.Option()] = Path("runs"),
    registry: Annotated[Path, typer.Option()] = Path("candidate_factors/registry.jsonl"),
) -> None:
    report = clean_experiment_outputs(
        experiment_id=experiment_id,
        runs_dir=runs_dir,
        registry_path=registry,
        yes=yes,
    )
    typer.echo(
        json.dumps(
            {
                "experiment_id": report.experiment_id,
                "run_ids": report.run_ids,
                "registry_removed": report.registry_removed,
                "dry_run": report.dry_run,
            },
            ensure_ascii=False,
        )
    )


def main() -> None:
    app()
