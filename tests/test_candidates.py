import json

from factor_autoresearch.candidates import load_candidate_batch


def test_load_candidate_batch_reports_invalid(tmp_path, test_config) -> None:
    path = tmp_path / "candidates.jsonl"
    rows = [
        {
            "id": "fa_good",
            "name": "good",
            "expression": "cs_rank(close_hfq)",
            "expected_direction": "positive",
            "hypothesis": "x",
            "category": "momentum",
            "lookback_days": 1,
            "created_at": "2026-06-22",
            "notes": "ok",
        },
        {
            "id": "fa_bad",
            "name": "bad",
            "expression": "close_hfq",
            "expected_direction": "sideways",
            "hypothesis": "x",
            "category": "momentum",
            "lookback_days": 1,
            "created_at": "2026-06-22",
            "notes": "bad",
        },
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    candidates, invalid = load_candidate_batch(path, test_config)
    assert [candidate.candidate_id for candidate in candidates] == ["fa_good"]
    assert invalid[0].candidate_id == "fa_bad"


def test_load_candidate_batch_reads_economic_rationale(tmp_path, test_config) -> None:
    path = tmp_path / "candidates.jsonl"
    path.write_text(
        json.dumps(
            {
                "id": "fa_reason",
                "name": "reason",
                "expression": "cs_rank(close_hfq)",
                "expected_direction": "positive",
                "hypothesis": "x",
                "category": "momentum",
                "lookback_days": 1,
                "created_at": "2026-06-22",
                "notes": "ok",
                "economic_rationale": "relative strength with delayed diffusion",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    candidates, invalid = load_candidate_batch(path, test_config)

    assert not invalid
    assert candidates[0].economic_rationale == "relative strength with delayed diffusion"


def test_load_candidate_batch_defaults_missing_economic_rationale_to_empty_string(
    tmp_path,
    test_config,
) -> None:
    path = tmp_path / "candidates.jsonl"
    path.write_text(
        json.dumps(
            {
                "id": "fa_blank",
                "name": "blank",
                "expression": "cs_rank(close_hfq)",
                "expected_direction": "positive",
                "hypothesis": "x",
                "category": "momentum",
                "lookback_days": 1,
                "created_at": "2026-06-22",
                "notes": "ok",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    candidates, invalid = load_candidate_batch(path, test_config)

    assert not invalid
    assert candidates[0].economic_rationale == ""


def test_load_candidate_batch_accepts_empty_economic_rationale(tmp_path, test_config) -> None:
    path = tmp_path / "candidates.jsonl"
    path.write_text(
        json.dumps(
            {
                "id": "fa_empty",
                "name": "empty",
                "expression": "cs_rank(close_hfq)",
                "expected_direction": "positive",
                "hypothesis": "x",
                "category": "momentum",
                "lookback_days": 1,
                "created_at": "2026-06-22",
                "notes": "ok",
                "economic_rationale": "",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    candidates, invalid = load_candidate_batch(path, test_config)

    assert not invalid
    assert candidates[0].economic_rationale == ""


def test_load_candidate_batch_rejects_non_string_economic_rationale(tmp_path, test_config) -> None:
    path = tmp_path / "candidates.jsonl"
    path.write_text(
        json.dumps(
            {
                "id": "fa_type_error",
                "name": "type error",
                "expression": "cs_rank(close_hfq)",
                "expected_direction": "positive",
                "hypothesis": "x",
                "category": "momentum",
                "lookback_days": 1,
                "created_at": "2026-06-22",
                "notes": "ok",
                "economic_rationale": 123,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    candidates, invalid = load_candidate_batch(path, test_config)

    assert not candidates
    assert invalid
    assert "economic_rationale" in invalid[0].details["message"]
