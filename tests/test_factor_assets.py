from __future__ import annotations

import json
from pathlib import Path

from factor_autoresearch.factor_assets import (
    AssetCandidateRecord,
    get_factor_record,
    ingest_block3_batch,
    list_factor_records,
    read_asset_index,
    rebuild_asset_store,
    retire_factor,
    summarize_batch_memory,
)


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _run_payload(run_id: str = "run_001") -> dict[str, object]:
    return {
        "run_id": run_id,
        "source_universe_key": "univ_trade_zz500",
        "forward_return_definition": "next_open_to_open_v1",
        "sample_protocol_hash": "sha256:sample",
        "preprocess_config_hash": "sha256:prep",
        "engine_version": "compute_v1",
        "created_at": "2026-06-28T10:00:00+08:00",
    }


def _candidate_record(
    *,
    factor_id: str,
    decision: str,
    run_id: str = "run_001",
    matched_factor_id: str | None = None,
    quality: float = 0.12,
    reject_reason: str | None = None,
) -> AssetCandidateRecord:
    return AssetCandidateRecord(
        decision=decision,
        candidate_payload={
            "candidate_id": factor_id,
            "expression": f"cs_rank({factor_id})",
            "category": "intraday",
            "economic_rationale": f"rationale-{factor_id}",
            "metrics": {
                "directional_rankic_mean": quality,
                "directional_rankic_ir": quality * 8.0,
                "matched_factor_id": matched_factor_id,
            },
        },
        run_payload=_run_payload(run_id),
        matched_factor_id=matched_factor_id,
        reject_reason=reject_reason,
        existing_metrics={"directional_rankic_mean": 0.08} if matched_factor_id else None,
        metrics_delta={"improvement_ratio": quality / 0.08} if matched_factor_id else None,
    )


def test_ingest_block3_batch_creates_active_snapshot_and_index(tmp_path: Path) -> None:
    asset_dir = tmp_path / "factor_assets"

    summary = ingest_block3_batch(
        asset_dir,
        records=[_candidate_record(factor_id="fa_001", decision="admitted")],
    )

    events = _read_jsonl(asset_dir / "events.jsonl")
    factors = _read_jsonl(asset_dir / "factors.jsonl")
    asset_index = read_asset_index(asset_dir)
    assert summary.admitted_factor_ids == ("fa_001",)
    assert [event["event_type"] for event in events] == ["factor_admitted"]
    assert factors[0]["factor_id"] == "fa_001"
    assert factors[0]["status"] == "active"
    assert asset_index["status"]["active"] == ["fa_001"]
    assert asset_index["factor_id"]["fa_001"]["expression_hash"].startswith("sha256:")


def test_ingest_block3_batch_writes_reject_and_duplicate_events_without_active_snapshot(tmp_path: Path) -> None:
    asset_dir = tmp_path / "factor_assets"

    ingest_block3_batch(
        asset_dir,
        records=[
            _candidate_record(
                factor_id="fa_reject",
                decision="reject",
                reject_reason="weak_rankic_mean",
            ),
            _candidate_record(
                factor_id="fa_dup",
                decision="duplicate",
                matched_factor_id="active_001",
                reject_reason="library_duplicate_or_replace",
            ),
        ],
    )

    events = _read_jsonl(asset_dir / "events.jsonl")
    assert [event["event_type"] for event in events] == ["factor_rejected", "factor_duplicate"]
    assert list_factor_records(asset_dir) == []
    memory = summarize_batch_memory(asset_dir)
    assert memory[0]["rejected_count"] == 1
    assert memory[0]["duplicate_count"] == 1


def test_ingest_block3_batch_is_idempotent_for_duplicate_import(tmp_path: Path) -> None:
    asset_dir = tmp_path / "factor_assets"
    record = _candidate_record(factor_id="fa_001", decision="admitted")

    ingest_block3_batch(asset_dir, records=[record])
    ingest_block3_batch(asset_dir, records=[record])

    events = _read_jsonl(asset_dir / "events.jsonl")
    assert len(events) == 1
    assert events[0]["factor_id"] == "fa_001"


def test_ingest_block3_batch_replaces_old_active_factor(tmp_path: Path) -> None:
    asset_dir = tmp_path / "factor_assets"
    ingest_block3_batch(asset_dir, records=[_candidate_record(factor_id="fa_old", decision="admitted")])

    summary = ingest_block3_batch(
        asset_dir,
        records=[
            _candidate_record(
                factor_id="fa_new",
                decision="replace_candidate",
                matched_factor_id="fa_old",
                quality=0.16,
            )
        ],
    )

    old_record = get_factor_record(asset_dir, "fa_old")
    new_record = get_factor_record(asset_dir, "fa_new")
    assert summary.replaced_factor_ids == ("fa_old",)
    assert old_record["status"] == "replaced"
    assert old_record["replaced_by_factor_id"] == "fa_new"
    assert new_record["status"] == "active"
    assert new_record["replaces_factor_id"] == "fa_old"


def test_ingest_block3_batch_rejects_replace_candidate_without_matched_active_factor(tmp_path: Path) -> None:
    asset_dir = tmp_path / "factor_assets"

    try:
        ingest_block3_batch(
            asset_dir,
            records=[
                _candidate_record(
                    factor_id="fa_new",
                    decision="replace_candidate",
                    matched_factor_id="fa_missing",
                    quality=0.16,
                )
            ],
        )
    except ValueError as exc:
        assert "matched active factor" in str(exc)
    else:
        raise AssertionError("expected replace_candidate ingest to fail when matched factor is missing")

    assert not (asset_dir / "events.jsonl").exists()
    assert list_factor_records(asset_dir) == []


def test_ingest_block3_batch_keeps_only_strongest_replacement_candidate(tmp_path: Path) -> None:
    asset_dir = tmp_path / "factor_assets"
    ingest_block3_batch(asset_dir, records=[_candidate_record(factor_id="fa_old", decision="admitted")])

    summary = ingest_block3_batch(
        asset_dir,
        records=[
            _candidate_record(
                factor_id="fa_challenger_a",
                decision="replace_candidate",
                matched_factor_id="fa_old",
                quality=0.11,
            ),
            _candidate_record(
                factor_id="fa_challenger_b",
                decision="replace_candidate",
                matched_factor_id="fa_old",
                quality=0.17,
            ),
        ],
    )

    assert summary.admitted_factor_ids == ("fa_challenger_b",)
    assert summary.duplicate_factor_ids == ("fa_challenger_a",)
    assert get_factor_record(asset_dir, "fa_old")["replaced_by_factor_id"] == "fa_challenger_b"
    assert get_factor_record(asset_dir, "fa_challenger_b")["status"] == "active"
    assert get_factor_record(asset_dir, "fa_challenger_a") is None


def test_retire_factor_marks_active_factor_as_retired(tmp_path: Path) -> None:
    asset_dir = tmp_path / "factor_assets"
    ingest_block3_batch(asset_dir, records=[_candidate_record(factor_id="fa_001", decision="admitted")])

    retire_factor(
        asset_dir,
        factor_id="fa_001",
        source_run_id="run_retire",
        reason="manual_cleanup",
        created_at="2026-06-28T12:00:00+08:00",
    )

    factor = get_factor_record(asset_dir, "fa_001")
    events = _read_jsonl(asset_dir / "events.jsonl")
    assert factor["status"] == "retired"
    assert events[-1]["event_type"] == "factor_retired"


def test_rebuild_asset_store_restores_snapshot_memory_and_index_from_events(tmp_path: Path) -> None:
    asset_dir = tmp_path / "factor_assets"
    ingest_block3_batch(asset_dir, records=[_candidate_record(factor_id="fa_001", decision="admitted")])
    ingest_block3_batch(
        asset_dir,
        records=[_candidate_record(factor_id="fa_002", decision="reject", reject_reason="weak_rankic_mean")],
    )
    (asset_dir / "factors.jsonl").unlink()
    (asset_dir / "batch_memory.jsonl").unlink()
    (asset_dir / "asset_index.json").unlink()

    rebuild_asset_store(asset_dir)

    assert get_factor_record(asset_dir, "fa_001")["status"] == "active"
    assert summarize_batch_memory(asset_dir)[0]["source_run_id"] == "run_001"
    assert read_asset_index(asset_dir)["status"]["active"] == ["fa_001"]
