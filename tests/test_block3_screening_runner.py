from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from factor_autoresearch.block3_screening import Block3GateDecision
from factor_autoresearch.block3_screening_runner import run_block3_screening
from factor_autoresearch.candidates import Candidate
from factor_autoresearch.compute_v1.screening import Block3ScreeningMetricBundle


@dataclass(frozen=True)
class _Preprocess:
    winsorize_mad_scale: float = 5.0
    size_exposure: str = "log_market_cap"


@dataclass(frozen=True)
class _ExperimentConfig:
    config_hash: str = "sha256:experiment"
    forward_return_definition: str = "next_open_to_open_v1"
    sample_protocol_id: str | None = "mining_v1"
    source_universe_key: str = "univ_trade_zz500"
    dataset_id: str = "sandbox_v1"
    preprocess: _Preprocess = _Preprocess()


@dataclass(frozen=True)
class _ScreeningConfig:
    screening_sample_roles: list[str]
    admission_horizon: str = "5d"


@dataclass(frozen=True)
class _SampleView:
    sample_protocol_id: str = "mining_v1"
    sample_protocol_hash: str = "sha256:sample"
    source_universe_key: str = "univ_trade_zz500"
    dataset_id: str = "sandbox_v1"
    forward_return_definition: dict[str, object] = None

    def __post_init__(self):
        if self.forward_return_definition is None:
            object.__setattr__(self, "forward_return_definition", {"name": "next_open_to_open_v1"})


def test_run_block3_screening_orchestrates_block2_compute_gate_and_writer(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []
    writer_calls: list[tuple[Block3GateDecision, dict[str, object], dict[str, object]]] = []

    experiment_config = _ExperimentConfig()
    screening_config = _ScreeningConfig(screening_sample_roles=["validation"])
    sample_view = _SampleView()
    candidate = Candidate(
        candidate_id="fa_runner_001",
        name="runner candidate",
        expression="cs_rank(close_hfq / open_hfq)",
        expected_direction="positive",
        hypothesis="runner",
        category="intraday",
        lookback_days=1,
        created_at="2026-06-28",
        notes="runner",
        economic_rationale="economic narrative",
    )
    metrics = Block3ScreeningMetricBundle(
        gate0_metrics={"expression_depth": 4},
        gate1_metrics={"directional_rankic_mean": 0.08, "directional_rankic_ir": 0.9},
        gate2_metrics={"matched_factor_id": None},
        gate3_metrics={"directional_long_short_sharpe": 1.3},
        factor_exposure_ref="memory://factor",
        engine_version="compute_v1",
    )
    decision = Block3GateDecision(
        decision="admitted",
        gate0_status="pass",
        gate1_status="pass",
        gate2_status="pass",
        gate3_status="pass",
        reject_reason=None,
        matched_factor_id=None,
        metrics={"expression_depth": 4},
    )

    monkeypatch.setattr(
        "factor_autoresearch.block3_screening_runner.load_experiment_config",
        lambda path: calls.append("load_experiment_config") or experiment_config,
    )
    monkeypatch.setattr(
        "factor_autoresearch.block3_screening_runner.load_block3_screening_config",
        lambda path: calls.append("load_block3_screening_config") or screening_config,
    )
    monkeypatch.setattr(
        "factor_autoresearch.block3_screening_runner.build_screening_sample_view",
        lambda **kwargs: calls.append("build_screening_sample_view") or sample_view,
    )
    monkeypatch.setattr(
        "factor_autoresearch.block3_screening_runner.load_candidate_batch",
        lambda path, config: calls.append("load_candidate_batch") or ([candidate], []),
    )
    monkeypatch.setattr(
        "factor_autoresearch.block3_screening_runner.compute_block3_screening_metrics",
        lambda **kwargs: calls.append("compute_block3_screening_metrics") or metrics,
    )
    monkeypatch.setattr(
        "factor_autoresearch.block3_screening_runner.apply_block3_screening_gate",
        lambda inputs: calls.append("apply_block3_screening_gate") or decision,
    )

    class _Writer:
        def __init__(self, output_dir: str | Path) -> None:
            self.output_dir = Path(output_dir)
            self.evaluation_log_path = self.output_dir / "evaluation_log.jsonl"
            self.research_factor_library_path = self.output_dir / "research_factor_library.jsonl"
            self.replacement_queue_path = self.output_dir / "replacement_queue.jsonl"
            calls.append("Block3ScreeningWriter")

        def write(self, decision_obj, candidate_payload, run_payload) -> None:
            calls.append("Block3ScreeningWriter.write")
            writer_calls.append((decision_obj, candidate_payload, run_payload))

    monkeypatch.setattr("factor_autoresearch.block3_screening_runner.Block3ScreeningWriter", _Writer)
    monkeypatch.setattr("factor_autoresearch.evaluate.Evaluator", object)

    summary = run_block3_screening(
        config_path=tmp_path / "experiment.toml",
        candidates_path=tmp_path / "candidates.jsonl",
        dataset_path=tmp_path / "dataset",
        output_dir=tmp_path / "outputs",
        screening_gate_config_path=tmp_path / "screening.toml",
    )

    assert calls == [
        "load_experiment_config",
        "load_block3_screening_config",
        "build_screening_sample_view",
        "load_candidate_batch",
        "Block3ScreeningWriter",
        "compute_block3_screening_metrics",
        "apply_block3_screening_gate",
        "Block3ScreeningWriter.write",
    ]
    assert summary.total_candidates == 1
    assert summary.admitted_count == 1
    assert writer_calls[0][1]["economic_rationale"] == "economic narrative"
    assert writer_calls[0][2]["sample_protocol_hash"] == "sha256:sample"
    assert writer_calls[0][2]["engine_version"] == "compute_v1"


def test_run_block3_screening_passes_asset_library_values_and_existing_metrics_to_gate(monkeypatch, tmp_path: Path) -> None:
    captures: dict[str, object] = {}

    experiment_config = _ExperimentConfig()
    screening_config = _ScreeningConfig(screening_sample_roles=["validation"])
    sample_view = _SampleView()
    candidate = Candidate(
        candidate_id="fa_runner_001",
        name="runner candidate",
        expression="cs_rank(close_hfq / open_hfq)",
        expected_direction="positive",
        hypothesis="runner",
        category="intraday",
        lookback_days=1,
        created_at="2026-06-28",
        notes="runner",
        economic_rationale="economic narrative",
    )
    metrics = Block3ScreeningMetricBundle(
        gate0_metrics={"expression_depth": 4},
        gate1_metrics={"directional_rankic_mean": 0.08, "directional_rankic_ir": 0.9},
        gate2_metrics={"matched_factor_id": "active_001"},
        gate3_metrics={"directional_long_short_sharpe": 1.3},
        factor_exposure_ref="memory://factor",
        engine_version="compute_v1",
    )
    decision = Block3GateDecision(
        decision="admitted",
        gate0_status="pass",
        gate1_status="pass",
        gate2_status="pass",
        gate3_status="pass",
        reject_reason=None,
        matched_factor_id="active_001",
        metrics={"expression_depth": 4},
        existing_metrics={"directional_rankic_mean": 0.08},
        metrics_delta={"improvement_ratio": 1.5},
    )

    monkeypatch.setattr("factor_autoresearch.block3_screening_runner.load_experiment_config", lambda path: experiment_config)
    monkeypatch.setattr("factor_autoresearch.block3_screening_runner.load_block3_screening_config", lambda path: screening_config)
    monkeypatch.setattr("factor_autoresearch.block3_screening_runner.build_screening_sample_view", lambda **kwargs: sample_view)
    monkeypatch.setattr("factor_autoresearch.block3_screening_runner.load_candidate_batch", lambda path, config: ([candidate], []))

    class _LoadResult:
        values = {"active_001": "library_series"}
        loaded_factor_ids = ("active_001",)
        skipped = ()

    monkeypatch.setattr(
        "factor_autoresearch.block3_screening_runner.load_library_factor_values",
        lambda *args, **kwargs: (captures.setdefault("load_library_kwargs", kwargs), _LoadResult())[1],
    )

    def _compute_metrics(**kwargs):
        captures["library_factors"] = kwargs.get("library_factors")
        return metrics

    monkeypatch.setattr("factor_autoresearch.block3_screening_runner.compute_block3_screening_metrics", _compute_metrics)
    def _existing_metrics(asset_store_dir, factor_id):
        captures.setdefault("existing_factor_lookup", (asset_store_dir, factor_id))
        return {"directional_rankic_mean": 0.08}

    monkeypatch.setattr(
        "factor_autoresearch.block3_screening_runner.get_existing_factor_metrics",
        _existing_metrics,
    )

    def _apply_gate(inputs):
        captures["existing_factor_metrics"] = inputs.existing_factor_metrics
        return decision

    monkeypatch.setattr("factor_autoresearch.block3_screening_runner.apply_block3_screening_gate", _apply_gate)
    monkeypatch.setattr(
        "factor_autoresearch.block3_screening_runner._compute_candidate_factor_values",
        lambda **kwargs: ("raw_series", "preprocessed_series"),
    )
    monkeypatch.setattr(
        "factor_autoresearch.block3_screening_runner.save_factor_values",
        lambda *args, **kwargs: (captures.setdefault("saved_factor_kwargs", kwargs), {"value_scope_hash": "sha256_scope"})[1],
    )
    monkeypatch.setattr(
        "factor_autoresearch.block3_screening_runner.register_factor_value_scope",
        lambda *args, **kwargs: captures.setdefault("registered_scope", kwargs),
    )

    class _Summary:
        admitted_factor_ids = ("fa_runner_001",)
        replaced_factor_ids = ()
        retired_factor_ids = ()
        duplicate_factor_ids = ()
        rejected_factor_ids = ()

    monkeypatch.setattr(
        "factor_autoresearch.block3_screening_runner.ingest_block3_batch",
        lambda *args, **kwargs: (captures.setdefault("ingest_records", kwargs["records"]), _Summary())[1],
    )

    writer_calls: list[tuple[Block3GateDecision, dict[str, object], dict[str, object]]] = []

    class _Writer:
        def __init__(self, output_dir: str | Path) -> None:
            self.output_dir = Path(output_dir)
            self.evaluation_log_path = self.output_dir / "evaluation_log.jsonl"
            self.research_factor_library_path = self.output_dir / "research_factor_library.jsonl"
            self.replacement_queue_path = self.output_dir / "replacement_queue.jsonl"

        def write(self, decision_obj, candidate_payload, run_payload) -> None:
            writer_calls.append((decision_obj, candidate_payload, run_payload))

    monkeypatch.setattr("factor_autoresearch.block3_screening_runner.Block3ScreeningWriter", _Writer)

    run_block3_screening(
        config_path=tmp_path / "experiment.toml",
        candidates_path=tmp_path / "candidates.jsonl",
        dataset_path=tmp_path / "dataset",
        output_dir=tmp_path / "outputs",
        screening_gate_config_path=tmp_path / "screening.toml",
        asset_store_dir=tmp_path / "factor_assets",
    )

    assert captures["library_factors"] == {"active_001": "library_series"}
    assert captures["existing_factor_lookup"][1] == "active_001"
    assert captures["existing_factor_metrics"] == {"directional_rankic_mean": 0.08}
    assert writer_calls[0][1]["library_value_status"] == "loaded"
    assert captures["saved_factor_kwargs"]["factor_id"] == "fa_runner_001"
    assert captures["registered_scope"]["value_scope_hash"] == "sha256_scope"


def test_run_block3_screening_marks_library_empty_when_no_reusable_values(monkeypatch, tmp_path: Path) -> None:
    experiment_config = _ExperimentConfig()
    screening_config = _ScreeningConfig(screening_sample_roles=["validation"])
    sample_view = _SampleView()
    candidate = Candidate(
        candidate_id="fa_runner_001",
        name="runner candidate",
        expression="cs_rank(close_hfq / open_hfq)",
        expected_direction="positive",
        hypothesis="runner",
        category="intraday",
        lookback_days=1,
        created_at="2026-06-28",
        notes="runner",
        economic_rationale="economic narrative",
    )
    metrics = Block3ScreeningMetricBundle(
        gate0_metrics={"expression_depth": 4},
        gate1_metrics={"directional_rankic_mean": 0.08, "directional_rankic_ir": 0.9},
        gate2_metrics={"matched_factor_id": None},
        gate3_metrics={"directional_long_short_sharpe": 1.3},
        factor_exposure_ref="memory://factor",
        engine_version="compute_v1",
    )
    decision = Block3GateDecision(
        decision="duplicate",
        gate0_status="pass",
        gate1_status="pass",
        gate2_status="duplicate",
        gate3_status="skip",
        reject_reason="library_duplicate_or_replace",
        matched_factor_id=None,
        metrics={"expression_depth": 4},
    )

    monkeypatch.setattr("factor_autoresearch.block3_screening_runner.load_experiment_config", lambda path: experiment_config)
    monkeypatch.setattr("factor_autoresearch.block3_screening_runner.load_block3_screening_config", lambda path: screening_config)
    monkeypatch.setattr("factor_autoresearch.block3_screening_runner.build_screening_sample_view", lambda **kwargs: sample_view)
    monkeypatch.setattr("factor_autoresearch.block3_screening_runner.load_candidate_batch", lambda path, config: ([candidate], []))

    class _LoadResult:
        values = {}
        loaded_factor_ids = ()
        skipped = ({"factor_id": "active_001", "reason": "sample_protocol_hash_mismatch"},)

    monkeypatch.setattr("factor_autoresearch.block3_screening_runner.load_library_factor_values", lambda *args, **kwargs: _LoadResult())
    def _compute_metrics_when_library_empty(**kwargs):
        if kwargs.get("library_factors") is not None:
            raise AssertionError("library_factors should be None when asset store is empty")
        return metrics

    monkeypatch.setattr(
        "factor_autoresearch.block3_screening_runner.compute_block3_screening_metrics",
        _compute_metrics_when_library_empty,
    )
    monkeypatch.setattr("factor_autoresearch.block3_screening_runner.apply_block3_screening_gate", lambda inputs: decision)

    writer_calls: list[tuple[Block3GateDecision, dict[str, object], dict[str, object]]] = []

    class _Writer:
        def __init__(self, output_dir: str | Path) -> None:
            self.output_dir = Path(output_dir)
            self.evaluation_log_path = self.output_dir / "evaluation_log.jsonl"
            self.research_factor_library_path = self.output_dir / "research_factor_library.jsonl"
            self.replacement_queue_path = self.output_dir / "replacement_queue.jsonl"

        def write(self, decision_obj, candidate_payload, run_payload) -> None:
            writer_calls.append((decision_obj, candidate_payload, run_payload))

    monkeypatch.setattr("factor_autoresearch.block3_screening_runner.Block3ScreeningWriter", _Writer)

    class _EmptySummary:
        admitted_factor_ids = ()
        replaced_factor_ids = ()
        retired_factor_ids = ()
        duplicate_factor_ids = ()
        rejected_factor_ids = ()

    monkeypatch.setattr("factor_autoresearch.block3_screening_runner.ingest_block3_batch", lambda *args, **kwargs: _EmptySummary())

    run_block3_screening(
        config_path=tmp_path / "experiment.toml",
        candidates_path=tmp_path / "candidates.jsonl",
        dataset_path=tmp_path / "dataset",
        output_dir=tmp_path / "outputs",
        screening_gate_config_path=tmp_path / "screening.toml",
        asset_store_dir=tmp_path / "factor_assets",
    )

    assert writer_calls[0][1]["library_value_status"] == "library_empty"





