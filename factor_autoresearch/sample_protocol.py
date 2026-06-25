"""独立样本协议模块，负责生成稳定样本切片与 sample protocol hash。"""

from __future__ import annotations

import json
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

import pandas as pd

SUPPORTED_SAMPLE_PROTOCOLS = {"sandbox_v1", "mining_v1"}
MINING_V1_DRAFT_PATH = (
    Path(__file__).resolve().parent.parent / "configs" / "mining_v1_sample_protocol_v1.toml"
)
REQUIRED_MANIFEST_FIELDS = {
    "dataset_id",
    "date_start",
    "date_end",
    "forward_return_definition",
    "universe",
}


@dataclass(frozen=True)
class SampleSlice:
    """单个样本切片。"""

    slice_id: str
    role: str
    date_start: str
    date_end: str
    pair_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "slice_id": self.slice_id,
            "role": self.role,
            "date_start": self.date_start,
            "date_end": self.date_end,
        }
        if self.pair_id is not None:
            payload["pair_id"] = self.pair_id
        return payload


@dataclass(frozen=True)
class SampleProtocol:
    """完整样本协议对象，包含规则、切片与稳定 hash。"""

    sample_protocol_id: str
    dataset_id: str
    purpose: str
    split_policy: str
    universe: str
    forward_return_definition: str
    dataset_date_range: dict[str, str]
    observed_date_range: dict[str, str]
    trade_date_count: int
    rules: dict[str, Any]
    slices: tuple[SampleSlice, ...]
    sample_protocol_hash: str

    def as_dict(self, *, include_hash: bool = True) -> dict[str, Any]:
        payload = {
            "sample_protocol_id": self.sample_protocol_id,
            "dataset_id": self.dataset_id,
            "purpose": self.purpose,
            "split_policy": self.split_policy,
            "universe": self.universe,
            "forward_return_definition": self.forward_return_definition,
            "dataset_date_range": dict(self.dataset_date_range),
            "observed_date_range": dict(self.observed_date_range),
            "trade_date_count": self.trade_date_count,
            "rules": dict(self.rules),
            "slices": [sample_slice.as_dict() for sample_slice in self.slices],
        }
        if include_hash:
            payload["sample_protocol_hash"] = self.sample_protocol_hash
        return payload


def canonical_json(payload: Mapping[str, Any]) -> str:
    """输出稳定 canonical JSON，用于 hash。"""

    return json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def build_sample_protocol(
    *,
    dataset_manifest: Mapping[str, Any],
    trade_dates: Iterable[object],
    sample_protocol_id: str | None = None,
) -> SampleProtocol:
    """基于 manifest 与交易日序列生成样本协议。"""

    manifest = _validate_manifest(dataset_manifest)
    protocol_id = _resolve_sample_protocol_id(manifest, sample_protocol_id)
    normalized_dates = _normalize_trade_dates(trade_dates)
    _validate_observed_dates_against_manifest(manifest, normalized_dates)

    if protocol_id == "sandbox_v1":
        return _build_sandbox_protocol(manifest, normalized_dates)
    if protocol_id == "mining_v1":
        return _build_mining_protocol(manifest, normalized_dates)
    raise ValueError(f"unsupported sample_protocol_id: {protocol_id}")


def build_sample_protocol_from_dataset(
    dataset_path: str | Path,
    *,
    sample_protocol_id: str | None = None,
) -> SampleProtocol:
    """直接从 dataset 目录读取 manifest 和交易日并生成样本协议。"""

    dataset_dir = Path(dataset_path).resolve()
    manifest = _load_manifest(dataset_dir)
    trade_dates = _load_trade_dates(dataset_dir)
    return build_sample_protocol(
        dataset_manifest=manifest,
        trade_dates=trade_dates,
        sample_protocol_id=sample_protocol_id,
    )


def _load_manifest(dataset_dir: Path) -> dict[str, Any]:
    manifest_path = dataset_dir / "manifest.json"
    with manifest_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_trade_dates(dataset_dir: Path) -> list[object]:
    panel_path = dataset_dir / "panel.parquet"
    panel = pd.read_parquet(panel_path, columns=["trade_date"])
    return panel["trade_date"].tolist()


def _validate_manifest(dataset_manifest: Mapping[str, Any]) -> dict[str, Any]:
    manifest = dict(dataset_manifest)
    missing_fields = sorted(REQUIRED_MANIFEST_FIELDS.difference(manifest))
    if missing_fields:
        raise ValueError(f"dataset manifest missing required fields: {', '.join(missing_fields)}")
    return manifest


def _resolve_sample_protocol_id(manifest: Mapping[str, Any], sample_protocol_id: str | None) -> str:
    if sample_protocol_id is not None:
        if sample_protocol_id not in SUPPORTED_SAMPLE_PROTOCOLS:
            raise ValueError(f"unsupported sample_protocol_id: {sample_protocol_id}")
        return sample_protocol_id

    manifest_protocol_id = manifest.get("sample_protocol_id")
    if isinstance(manifest_protocol_id, str) and manifest_protocol_id in SUPPORTED_SAMPLE_PROTOCOLS:
        return manifest_protocol_id

    dataset_id = manifest.get("dataset_id")
    if dataset_id in SUPPORTED_SAMPLE_PROTOCOLS:
        return str(dataset_id)

    raise ValueError("sample_protocol_id is required when manifest does not declare a supported protocol")


def _normalize_trade_dates(trade_dates: Iterable[object]) -> list[str]:
    normalized = sorted({pd.Timestamp(value).strftime("%Y-%m-%d") for value in trade_dates})
    if not normalized:
        raise ValueError("trade_dates must contain at least one date")
    return normalized


def _validate_observed_dates_against_manifest(
    manifest: Mapping[str, Any],
    observed_trade_dates: list[str],
) -> None:
    observed_start = observed_trade_dates[0]
    observed_end = observed_trade_dates[-1]
    manifest_start = str(manifest["date_start"])
    manifest_end = str(manifest["date_end"])
    if observed_start < manifest_start or observed_end > manifest_end:
        raise ValueError("observed trade dates fall outside manifest date range")


def _build_sandbox_protocol(manifest: Mapping[str, Any], trade_dates: list[str]) -> SampleProtocol:
    slices = (
        SampleSlice(
            slice_id="full_sample",
            role="full_sample",
            date_start=trade_dates[0],
            date_end=trade_dates[-1],
        ),
    )
    rules = {
        "date_source": "panel_trade_dates",
        "uses_full_dataset": True,
        "oos_enabled": False,
        "walk_forward_enabled": False,
    }
    return _finalize_protocol(
        sample_protocol_id="sandbox_v1",
        manifest=manifest,
        purpose="快速开发和 smoke test",
        split_policy="single_full_sample",
        trade_dates=trade_dates,
        rules=rules,
        slices=slices,
    )


def _build_mining_protocol(manifest: Mapping[str, Any], trade_dates: list[str]) -> SampleProtocol:
    draft_protocol = _load_mining_v1_draft_protocol(manifest, trade_dates)
    if draft_protocol is not None:
        return draft_protocol

    total_dates = len(trade_dates)
    if total_dates < 8:
        raise ValueError("mining_v1 requires at least 8 unique trade dates")

    formation_count = total_dates // 2
    validation_count = total_dates // 4
    oos_count = total_dates - formation_count - validation_count
    if formation_count < 1 or validation_count < 1 or oos_count < 1:
        raise ValueError("mining_v1 could not allocate formation, validation and oos slices")

    formation_dates = trade_dates[:formation_count]
    validation_dates = trade_dates[formation_count : formation_count + validation_count]
    oos_dates = trade_dates[formation_count + validation_count :]

    slices: list[SampleSlice] = [
        SampleSlice(
            slice_id="formation",
            role="in_sample",
            date_start=formation_dates[0],
            date_end=formation_dates[-1],
        ),
        SampleSlice(
            slice_id="validation",
            role="validation",
            date_start=validation_dates[0],
            date_end=validation_dates[-1],
        ),
        SampleSlice(
            slice_id="oos",
            role="oos",
            date_start=oos_dates[0],
            date_end=oos_dates[-1],
        ),
    ]

    walk_forward_validation_count = max(1, total_dates // 8)
    walk_forward_step_count = walk_forward_validation_count
    walk_forward_cutoff = formation_count + validation_count
    pair_index = 1
    pair_start = 0
    while pair_start + formation_count + walk_forward_validation_count <= walk_forward_cutoff:
        pair_id = f"wf_{pair_index:03d}"
        wf_formation_dates = trade_dates[pair_start : pair_start + formation_count]
        wf_validation_dates = trade_dates[
            pair_start + formation_count : pair_start + formation_count + walk_forward_validation_count
        ]
        slices.append(
            SampleSlice(
                slice_id=f"{pair_id}_formation",
                role="walk_forward_formation",
                pair_id=pair_id,
                date_start=wf_formation_dates[0],
                date_end=wf_formation_dates[-1],
            )
        )
        slices.append(
            SampleSlice(
                slice_id=f"{pair_id}_validation",
                role="walk_forward_validation",
                pair_id=pair_id,
                date_start=wf_validation_dates[0],
                date_end=wf_validation_dates[-1],
            )
        )
        pair_index += 1
        pair_start += walk_forward_step_count

    rules = {
        "date_source": "panel_trade_dates",
        "main_windows": {
            "formation_fraction": "1/2",
            "validation_fraction": "1/4",
            "oos_fraction": "remainder",
            "formation_count": formation_count,
            "validation_count": validation_count,
            "oos_count": oos_count,
        },
        "walk_forward": {
            "formation_count": formation_count,
            "validation_count": walk_forward_validation_count,
            "step_count": walk_forward_step_count,
            "generated_pairs": pair_index - 1,
            "cutoff_before_oos_count": walk_forward_cutoff,
        },
    }
    return _finalize_protocol(
        sample_protocol_id="mining_v1",
        manifest=manifest,
        purpose="严肃挖因子评价",
        split_policy="time_ordered_oos_and_walk_forward",
        trade_dates=trade_dates,
        rules=rules,
        slices=tuple(slices),
    )


def _load_mining_v1_draft_protocol(
    manifest: Mapping[str, Any],
    trade_dates: list[str],
) -> SampleProtocol | None:
    if not MINING_V1_DRAFT_PATH.exists():
        return None
    with MINING_V1_DRAFT_PATH.open("rb") as handle:
        draft = tomllib.load(handle)
    if str(draft.get("sample_protocol_id")) != "mining_v1":
        return None
    if str(draft.get("universe")) != str(manifest["universe"]):
        return None
    if str(draft.get("forward_return_definition")) != str(manifest["forward_return_definition"]):
        return None

    observed_date_set = set(trade_dates)
    draft_start = str(draft["date_start"])
    draft_end = str(draft["date_end"])
    if draft_start not in observed_date_set or draft_end not in observed_date_set:
        return None

    slices: list[SampleSlice] = []
    for raw_slice in draft.get("slices", []):
        slice_start = str(raw_slice["date_start"])
        slice_end = str(raw_slice["date_end"])
        if slice_start not in observed_date_set or slice_end not in observed_date_set:
            return None
        slices.append(
            SampleSlice(
                slice_id=str(raw_slice["slice_id"]),
                role=str(raw_slice["role"]),
                pair_id=(
                    str(raw_slice["pair_id"])
                    if raw_slice.get("pair_id") is not None
                    else None
                ),
                date_start=slice_start,
                date_end=slice_end,
            )
        )
    if not slices:
        return None

    rules = {
        "date_source": "draft_config",
        "draft_config_path": str(MINING_V1_DRAFT_PATH),
        "declared_date_range": {
            "date_start": draft_start,
            "date_end": draft_end,
        },
        "slice_count": len(slices),
    }
    return _finalize_protocol(
        sample_protocol_id="mining_v1",
        manifest=manifest,
        purpose=str(draft["purpose"]),
        split_policy=str(draft["split_policy"]),
        trade_dates=trade_dates,
        rules=rules,
        slices=tuple(slices),
    )


def _finalize_protocol(
    *,
    sample_protocol_id: str,
    manifest: Mapping[str, Any],
    purpose: str,
    split_policy: str,
    trade_dates: list[str],
    rules: Mapping[str, Any],
    slices: tuple[SampleSlice, ...] | list[SampleSlice],
) -> SampleProtocol:
    protocol = SampleProtocol(
        sample_protocol_id=sample_protocol_id,
        dataset_id=str(manifest["dataset_id"]),
        purpose=purpose,
        split_policy=split_policy,
        universe=str(manifest["universe"]),
        forward_return_definition=str(manifest["forward_return_definition"]),
        dataset_date_range={
            "date_start": str(manifest["date_start"]),
            "date_end": str(manifest["date_end"]),
        },
        observed_date_range={
            "date_start": trade_dates[0],
            "date_end": trade_dates[-1],
        },
        trade_date_count=len(trade_dates),
        rules=dict(rules),
        slices=tuple(slices),
        sample_protocol_hash="",
    )
    payload = protocol.as_dict(include_hash=False)
    return SampleProtocol(
        sample_protocol_id=protocol.sample_protocol_id,
        dataset_id=protocol.dataset_id,
        purpose=protocol.purpose,
        split_policy=protocol.split_policy,
        universe=protocol.universe,
        forward_return_definition=protocol.forward_return_definition,
        dataset_date_range=protocol.dataset_date_range,
        observed_date_range=protocol.observed_date_range,
        trade_date_count=protocol.trade_date_count,
        rules=protocol.rules,
        slices=protocol.slices,
        sample_protocol_hash=f"sha256:{sha256(canonical_json(payload).encode('utf-8')).hexdigest()}",
    )


__all__ = [
    "SampleProtocol",
    "SampleSlice",
    "build_sample_protocol",
    "build_sample_protocol_from_dataset",
    "canonical_json",
]
