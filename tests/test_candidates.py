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
