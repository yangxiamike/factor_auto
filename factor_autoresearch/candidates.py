from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from factor_autoresearch.config import ExperimentConfig

FORBIDDEN_FIELDS = {
    "universe",
    "date_start",
    "date_end",
    "forward_return_definition",
    "gate",
    "data_source",
}


class CandidateValidationError(ValueError):
    """Raised when candidate JSONL content is invalid."""


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    name: str
    expression: str
    expected_direction: str
    hypothesis: str
    category: str
    lookback_days: int
    created_at: str
    notes: str

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["id"] = payload.pop("candidate_id")
        return payload


@dataclass(frozen=True)
class InvalidCandidateRecord:
    candidate_id: str
    failure_bucket: str
    details: dict[str, object]


def _parse_candidate(raw: dict[str, object], config: ExperimentConfig) -> Candidate:
    forbidden = FORBIDDEN_FIELDS.intersection(raw.keys())
    if forbidden:
        fields = ", ".join(sorted(forbidden))
        raise CandidateValidationError(f"candidate contains forbidden fields: {fields}")

    required = {
        "id",
        "name",
        "expression",
        "expected_direction",
        "hypothesis",
        "category",
        "lookback_days",
        "created_at",
        "notes",
    }
    missing = sorted(required.difference(raw.keys()))
    if missing:
        raise CandidateValidationError(f"candidate missing required fields: {', '.join(missing)}")

    expected_direction = str(raw["expected_direction"])
    if expected_direction not in {"positive", "negative"}:
        raise CandidateValidationError("expected_direction must be 'positive' or 'negative'")

    category = str(raw["category"])
    if category not in config.categories:
        raise CandidateValidationError(f"unknown category: {category}")

    try:
        lookback_days = int(raw["lookback_days"])
    except (TypeError, ValueError) as exc:
        raise CandidateValidationError("lookback_days must be an integer") from exc

    return Candidate(
        candidate_id=str(raw["id"]),
        name=str(raw["name"]),
        expression=str(raw["expression"]),
        expected_direction=expected_direction,
        hypothesis=str(raw["hypothesis"]),
        category=category,
        lookback_days=lookback_days,
        created_at=str(raw["created_at"]),
        notes=str(raw["notes"]),
    )


def load_candidates(path: str | Path, config: ExperimentConfig) -> list[Candidate]:
    candidates, invalid_records = load_candidate_batch(path, config)
    if invalid_records:
        first = invalid_records[0]
        raise CandidateValidationError(str(first.details["message"]))
    return candidates


def load_candidate_batch(path: str | Path, config: ExperimentConfig) -> tuple[list[Candidate], list[InvalidCandidateRecord]]:
    candidate_path = Path(path)
    if not candidate_path.exists():
        raise CandidateValidationError(f"candidate file not found: {candidate_path}")

    candidates: list[Candidate] = []
    invalid_records: list[InvalidCandidateRecord] = []
    seen: set[str] = set()
    with candidate_path.open("r", encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                raw = json.loads(text)
            except json.JSONDecodeError as exc:
                invalid_records.append(
                    InvalidCandidateRecord(
                        candidate_id=f"line_{lineno}",
                        failure_bucket="validate_failed",
                        details={"message": f"line {lineno}: invalid json: {exc.msg}"},
                    )
                )
                continue
            if not isinstance(raw, dict):
                invalid_records.append(
                    InvalidCandidateRecord(
                        candidate_id=f"line_{lineno}",
                        failure_bucket="validate_failed",
                        details={"message": f"line {lineno}: candidate must be a json object"},
                    )
                )
                continue
            try:
                candidate = _parse_candidate(raw, config)
            except CandidateValidationError as exc:
                invalid_records.append(
                    InvalidCandidateRecord(
                        candidate_id=str(raw.get("id", f"line_{lineno}")),
                        failure_bucket="validate_failed",
                        details={"message": str(exc), "line": lineno},
                    )
                )
                continue
            if candidate.candidate_id in seen:
                invalid_records.append(
                    InvalidCandidateRecord(
                        candidate_id=candidate.candidate_id,
                        failure_bucket="validate_failed",
                        details={"message": f"duplicate candidate id: {candidate.candidate_id}"},
                    )
                )
                continue
            seen.add(candidate.candidate_id)
            candidates.append(candidate)
    return candidates, invalid_records
