"""
区块4因子资产库模块
负责事件账本、状态快照、批次记忆和查询索引。
不负责因子值 Parquet 的读写，也不负责区块3指标计算。
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

VALID_STATUSES = {"active", "replaced", "retired"}
VALID_EVENT_TYPES = {
    "factor_admitted",
    "factor_rejected",
    "factor_duplicate",
    "factor_replaced",
    "factor_retired",
}


# ============== 数据结构 ==============
@dataclass(frozen=True)
class AssetCandidateRecord:
    """资产候选记录: 承接一条 Block3 决策与追溯字段。"""

    decision: str
    candidate_payload: Mapping[str, object]
    run_payload: Mapping[str, object]
    matched_factor_id: str | None = None
    reject_reason: str | None = None
    existing_metrics: Mapping[str, object] | None = None
    metrics_delta: Mapping[str, object] | None = None


@dataclass(frozen=True)
class AssetIngestSummary:
    """资产入库摘要: 汇总本轮账本写入与激活结果。"""

    source_run_id: str
    admitted_factor_ids: tuple[str, ...]
    replaced_factor_ids: tuple[str, ...]
    retired_factor_ids: tuple[str, ...]
    duplicate_factor_ids: tuple[str, ...]
    rejected_factor_ids: tuple[str, ...]


# ============== 路径与基础辅助 ==============
def _asset_paths(asset_store_dir: str | Path) -> dict[str, Path]:
    """资产路径: 统一管理账本、快照、索引和值目录位置。"""

    root = Path(asset_store_dir)
    return {
        "root": root,
        "events": root / "events.jsonl",
        "factors": root / "factors.jsonl",
        "batch_memory": root / "batch_memory.jsonl",
        "asset_index": root / "asset_index.json",
        "values": root / "values",
        "logs": root / "logs",
    }


def _canonical_json(payload: object) -> str:
    """稳定 JSON: 用于哈希和幂等键生成。"""

    return json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _sha256_text(text: str) -> str:
    """文本哈希: 生成稳定 sha256 前缀字符串。"""

    return f"sha256:{sha256(text.encode('utf-8')).hexdigest()}"


def _ensure_parent(path: Path) -> None:
    """确保目录: 在落盘前创建父目录。"""

    path.parent.mkdir(parents=True, exist_ok=True)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """读取 JSONL: 文件不存在时返回空列表。"""

    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    """覆盖写 JSONL: 用于重建快照和批次记忆。"""

    _ensure_parent(path)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False) + "\n")


def _append_jsonl(path: Path, row: Mapping[str, object]) -> None:
    """追加写 JSONL: 用于权威事件账本。"""

    _ensure_parent(path)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(row), ensure_ascii=False) + "\n")


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    """覆盖写 JSON: 用于查询索引。"""

    _ensure_parent(path)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _normalize_mapping(value: Mapping[str, object] | None) -> dict[str, object]:
    """映射归一化: 避免上游传入只读映射。"""

    return dict(value or {})


def _candidate_metrics(record: AssetCandidateRecord) -> dict[str, object]:
    """候选指标: 从 payload 中抽出入库需要的 Gate 指标。"""

    metrics = record.candidate_payload.get("metrics", {})
    return dict(metrics) if isinstance(metrics, Mapping) else {}


def _event_id(
    *,
    source_run_id: str,
    factor_id: str,
    decision: str,
    matched_factor_id: str | None,
    event_type: str,
) -> str:
    """事件幂等键: 约束重复导入不会重复写事件。"""

    return _sha256_text(
        _canonical_json(
            {
                "source_run_id": source_run_id,
                "factor_id": factor_id,
                "decision": decision,
                "matched_factor_id": matched_factor_id,
                "event_type": event_type,
            }
        )
    )


def _event_record(
    *,
    event_type: str,
    factor_id: str,
    previous_status: str | None,
    new_status: str | None,
    reason: str | None,
    record: AssetCandidateRecord,
    replaces_factor_id: str | None = None,
    replaced_by_factor_id: str | None = None,
) -> dict[str, object]:
    """事件载荷: 统一账本字段合同。"""

    if event_type not in VALID_EVENT_TYPES:
        raise ValueError(f"unsupported asset event type: {event_type}")

    run_payload = dict(record.run_payload)
    candidate_payload = dict(record.candidate_payload)
    factor_id = str(factor_id)
    source_run_id = str(run_payload["run_id"])
    matched_factor_id = record.matched_factor_id
    created_at = str(run_payload["created_at"])
    metrics = _candidate_metrics(record)
    expression = str(candidate_payload.get("expression", ""))
    event = {
        "event_id": _event_id(
            source_run_id=source_run_id,
            factor_id=factor_id,
            decision=str(record.decision),
            matched_factor_id=matched_factor_id,
            event_type=event_type,
        ),
        "event_type": event_type,
        "factor_id": factor_id,
        "previous_status": previous_status,
        "new_status": new_status,
        "reason": reason,
        "decision": str(record.decision),
        "expression": expression,
        "expression_hash": _sha256_text(expression),
        "category": candidate_payload.get("category"),
        "factor_family": candidate_payload.get("factor_family"),
        "correlation_cluster_id": candidate_payload.get("correlation_cluster_id"),
        "economic_rationale": candidate_payload.get("economic_rationale"),
        "admission_metrics": metrics,
        "source_run_id": source_run_id,
        "matched_factor_id": matched_factor_id,
        "replaces_factor_id": replaces_factor_id,
        "replaced_by_factor_id": replaced_by_factor_id,
        "created_at": created_at,
        "source_universe_key": run_payload.get("source_universe_key"),
        "forward_return_definition": run_payload.get("forward_return_definition"),
        "sample_protocol_hash": run_payload.get("sample_protocol_hash"),
        "preprocess_config_hash": run_payload.get("preprocess_config_hash"),
        "engine_version": run_payload.get("engine_version"),
        "existing_metrics": _normalize_mapping(record.existing_metrics) or None,
        "metrics_delta": _normalize_mapping(record.metrics_delta) or None,
    }
    return event


def _replacement_quality_value(record: AssetCandidateRecord, quality_metric: str) -> float:
    """替换质量值: 从候选指标中读取排序字段。"""

    metrics = _candidate_metrics(record)
    raw_value = metrics.get(quality_metric)
    return float(raw_value) if raw_value is not None else float("-inf")


def _build_batch_winners(
    records: Sequence[AssetCandidateRecord],
    *,
    quality_metric: str,
) -> set[str]:
    """替换胜者集: 同一旧因子只保留质量值最优的新候选。"""

    best_by_target: dict[str, AssetCandidateRecord] = {}
    for record in records:
        if record.decision != "replace_candidate" or not record.matched_factor_id:
            continue
        target = record.matched_factor_id
        current = best_by_target.get(target)
        if current is None:
            best_by_target[target] = record
            continue
        current_value = _replacement_quality_value(current, quality_metric)
        next_value = _replacement_quality_value(record, quality_metric)
        if next_value > current_value:
            best_by_target[target] = record
            continue
        if next_value == current_value:
            current_id = str(current.candidate_payload.get("candidate_id"))
            next_id = str(record.candidate_payload.get("candidate_id"))
            if next_id < current_id:
                best_by_target[target] = record
    return {str(record.candidate_payload.get("candidate_id")) for record in best_by_target.values()}


def _scan_value_scopes(values_dir: Path) -> dict[str, list[str]]:
    """扫描值目录: 为重建快照补全 value scope 列表。"""

    scopes: dict[str, list[str]] = defaultdict(list)
    if not values_dir.exists():
        return scopes
    for factor_dir in values_dir.iterdir():
        if not factor_dir.is_dir():
            continue
        factor_id = factor_dir.name
        factor_scopes: list[str] = []
        for scope_dir in factor_dir.iterdir():
            manifest_path = scope_dir / "manifest.json"
            if scope_dir.is_dir() and manifest_path.exists():
                factor_scopes.append(scope_dir.name)
        scopes[factor_id] = sorted(set(factor_scopes))
    return scopes


# ============== 查询接口 ==============
def list_factor_records(asset_store_dir: str | Path, *, status: str | None = None) -> list[dict[str, Any]]:
    """列出因子快照: 支持按状态过滤。"""

    paths = _asset_paths(asset_store_dir)
    rows = _read_jsonl(paths["factors"])
    if status is None:
        return rows
    return [row for row in rows if row.get("status") == status]


def get_factor_record(asset_store_dir: str | Path, factor_id: str) -> dict[str, Any] | None:
    """读取单因子快照: 不存在时返回空。"""

    for row in list_factor_records(asset_store_dir):
        if row.get("factor_id") == factor_id:
            return row
    return None


def get_existing_factor_metrics(asset_store_dir: str | Path, factor_id: str | None) -> dict[str, object] | None:
    """读取旧因子指标: 给 Gate2 replacement 判定复用。"""

    if not factor_id:
        return None
    record = get_factor_record(asset_store_dir, factor_id)
    if record is None:
        return None
    metrics = record.get("admission_metrics")
    return dict(metrics) if isinstance(metrics, Mapping) else None


def read_asset_index(asset_store_dir: str | Path) -> dict[str, Any]:
    """读取查询索引: 文件不存在时返回空索引。"""

    path = _asset_paths(asset_store_dir)["asset_index"]
    if not path.exists():
        return {
            "factor_id": {},
            "expression_hash": {},
            "status": {},
            "category": {},
            "factor_family": {},
            "correlation_cluster_id": {},
            "source_run_id": {},
        }
    return json.loads(path.read_text(encoding="utf-8"))


def summarize_batch_memory(asset_store_dir: str | Path) -> list[dict[str, Any]]:
    """读取批次记忆: 供 CLI 和区块5 浏览。"""

    return _read_jsonl(_asset_paths(asset_store_dir)["batch_memory"])


# ============== 重建与增量同步 ==============
def rebuild_asset_store(asset_store_dir: str | Path) -> dict[str, Path]:
    """重建资产库: 从事件账本恢复快照、批次记忆和查询索引。"""

    paths = _asset_paths(asset_store_dir)
    events = _read_jsonl(paths["events"])
    factors: dict[str, dict[str, Any]] = {}
    value_scopes = _scan_value_scopes(paths["values"])

    for event in events:
        event_type = str(event["event_type"])
        factor_id = str(event["factor_id"])
        created_at = str(event["created_at"])
        if event_type == "factor_admitted":
            factors[factor_id] = {
                "factor_id": factor_id,
                "status": "active",
                "expression": event.get("expression"),
                "expression_hash": event.get("expression_hash"),
                "category": event.get("category"),
                "factor_family": event.get("factor_family"),
                "correlation_cluster_id": event.get("correlation_cluster_id"),
                "economic_rationale": event.get("economic_rationale"),
                "source_run_id": event.get("source_run_id"),
                "replaces_factor_id": event.get("replaces_factor_id"),
                "replaced_by_factor_id": event.get("replaced_by_factor_id"),
                "admission_metrics": dict(event.get("admission_metrics") or {}),
                "value_scopes": value_scopes.get(factor_id, []),
                "created_at": factors.get(factor_id, {}).get("created_at", created_at),
                "updated_at": created_at,
            }
            continue
        if event_type == "factor_replaced":
            record = factors.get(factor_id)
            if record is None:
                continue
            record["status"] = "replaced"
            record["replaced_by_factor_id"] = event.get("replaced_by_factor_id")
            record["updated_at"] = created_at
            continue
        if event_type == "factor_retired":
            record = factors.get(factor_id)
            if record is None:
                continue
            record["status"] = "retired"
            record["updated_at"] = created_at

    for factor_id, scopes in value_scopes.items():
        if factor_id in factors:
            factors[factor_id]["value_scopes"] = scopes

    factor_rows = [factors[key] for key in sorted(factors)]
    _write_jsonl(paths["factors"], factor_rows)

    batches: dict[str, dict[str, Any]] = {}
    for event in events:
        source_run_id = str(event["source_run_id"])
        batch = batches.setdefault(
            source_run_id,
            {
                "source_run_id": source_run_id,
                "candidate_count": 0,
                "admitted_count": 0,
                "rejected_count": 0,
                "duplicate_count": 0,
                "replaced_count": 0,
                "main_reject_reasons": [],
                "new_active_factor_ids": [],
                "replaced_relations": [],
                "failed_candidates": [],
            },
        )
        event_type = str(event["event_type"])
        factor_id = str(event["factor_id"])
        reason = event.get("reason")
        if event_type == "factor_admitted":
            batch["candidate_count"] += 1
            if event.get("replaces_factor_id"):
                batch["replaced_count"] += 1
                batch["replaced_relations"].append(
                    {
                        "old_factor_id": event.get("replaces_factor_id"),
                        "new_factor_id": factor_id,
                    }
                )
            else:
                batch["admitted_count"] += 1
            batch["new_active_factor_ids"].append(factor_id)
        elif event_type == "factor_rejected":
            batch["candidate_count"] += 1
            batch["rejected_count"] += 1
            if reason:
                batch["main_reject_reasons"].append(reason)
            batch["failed_candidates"].append(
                {"factor_id": factor_id, "decision": "reject", "reason": reason}
            )
        elif event_type == "factor_duplicate":
            batch["candidate_count"] += 1
            batch["duplicate_count"] += 1
            batch["failed_candidates"].append(
                {"factor_id": factor_id, "decision": "duplicate", "reason": reason}
            )

    batch_rows = [batches[key] for key in sorted(batches)]
    for batch in batch_rows:
        batch["main_reject_reasons"] = sorted(set(batch["main_reject_reasons"]))
    _write_jsonl(paths["batch_memory"], batch_rows)

    asset_index: dict[str, Any] = {
        "factor_id": {},
        "expression_hash": defaultdict(list),
        "status": defaultdict(list),
        "category": defaultdict(list),
        "factor_family": defaultdict(list),
        "correlation_cluster_id": defaultdict(list),
        "source_run_id": defaultdict(list),
    }
    for row in factor_rows:
        factor_id = str(row["factor_id"])
        asset_index["factor_id"][factor_id] = row
        for key in (
            "expression_hash",
            "status",
            "category",
            "factor_family",
            "correlation_cluster_id",
            "source_run_id",
        ):
            value = row.get(key)
            if value in (None, ""):
                continue
            asset_index[key][str(value)].append(factor_id)

    serializable_index: dict[str, object] = {"factor_id": asset_index["factor_id"]}
    for key in (
        "expression_hash",
        "status",
        "category",
        "factor_family",
        "correlation_cluster_id",
        "source_run_id",
    ):
        serializable_index[key] = {
            sub_key: sorted(set(values))
            for sub_key, values in dict(asset_index[key]).items()
        }
    _write_json(paths["asset_index"], serializable_index)
    return paths


def register_factor_value_scope(
    asset_store_dir: str | Path,
    *,
    factor_id: str,
    value_scope_hash: str,
) -> None:
    """注册值范围: 在快照与索引里挂上可复用 value scope。"""

    factor_rows = list_factor_records(asset_store_dir)
    updated_rows: list[dict[str, Any]] = []
    found = False
    for row in factor_rows:
        current = dict(row)
        if current.get("factor_id") == factor_id:
            scopes = sorted(set([*current.get("value_scopes", []), value_scope_hash]))
            current["value_scopes"] = scopes
            found = True
        updated_rows.append(current)
    if not found:
        raise ValueError(f"cannot register value scope for missing factor: {factor_id}")

    paths = _asset_paths(asset_store_dir)
    _write_jsonl(paths["factors"], updated_rows)
    rebuilt_index = read_asset_index(asset_store_dir)
    if factor_id in rebuilt_index.get("factor_id", {}):
        rebuilt_index["factor_id"][factor_id]["value_scopes"] = get_factor_record(
            asset_store_dir,
            factor_id,
        ).get("value_scopes", [])
        _write_json(paths["asset_index"], rebuilt_index)


# ============== 主入口 ==============
def ingest_block3_batch(
    asset_store_dir: str | Path,
    *,
    records: Sequence[AssetCandidateRecord],
    replacement_quality_metric: str = "directional_rankic_mean",
) -> AssetIngestSummary:
    """批量入库 Block3 结果: 写事件、重建快照，并处理替换冲突。"""

    paths = _asset_paths(asset_store_dir)
    paths["root"].mkdir(parents=True, exist_ok=True)

    if not records:
        raise ValueError("ingest_block3_batch requires at least one record")

    source_run_ids = {str(record.run_payload["run_id"]) for record in records}
    if len(source_run_ids) != 1:
        raise ValueError("all asset candidate records in one ingest batch must share the same source_run_id")
    source_run_id = next(iter(source_run_ids))

    existing_events = _read_jsonl(paths["events"])
    existing_event_ids = {str(event["event_id"]) for event in existing_events}
    active_records = {
        str(row["factor_id"]): row
        for row in list_factor_records(asset_store_dir, status="active")
    }
    replacement_winners = _build_batch_winners(records, quality_metric=replacement_quality_metric)

    new_events: list[dict[str, object]] = []
    admitted_factor_ids: list[str] = []
    replaced_factor_ids: list[str] = []
    retired_factor_ids: list[str] = []
    duplicate_factor_ids: list[str] = []
    rejected_factor_ids: list[str] = []

    for record in records:
        factor_id = str(record.candidate_payload["candidate_id"])
        if record.decision == "admitted":
            event = _event_record(
                event_type="factor_admitted",
                factor_id=factor_id,
                previous_status=None,
                new_status="active",
                reason="admitted",
                record=record,
            )
            if event["event_id"] not in existing_event_ids:
                new_events.append(event)
                existing_event_ids.add(str(event["event_id"]))
            admitted_factor_ids.append(factor_id)
            continue

        if record.decision == "reject":
            event = _event_record(
                event_type="factor_rejected",
                factor_id=factor_id,
                previous_status=None,
                new_status=None,
                reason=record.reject_reason or "rejected_by_gate",
                record=record,
            )
            if event["event_id"] not in existing_event_ids:
                new_events.append(event)
                existing_event_ids.add(str(event["event_id"]))
            rejected_factor_ids.append(factor_id)
            continue

        if record.decision == "duplicate":
            event = _event_record(
                event_type="factor_duplicate",
                factor_id=factor_id,
                previous_status=None,
                new_status=None,
                reason=record.reject_reason or "duplicate_by_gate",
                record=record,
            )
            if event["event_id"] not in existing_event_ids:
                new_events.append(event)
                existing_event_ids.add(str(event["event_id"]))
            duplicate_factor_ids.append(factor_id)
            continue

        if record.decision != "replace_candidate":
            raise ValueError(f"unsupported asset ingest decision: {record.decision}")

        if factor_id not in replacement_winners:
            duplicate_event = _event_record(
                event_type="factor_duplicate",
                factor_id=factor_id,
                previous_status=None,
                new_status=None,
                reason="replacement_superseded_by_stronger_candidate",
                record=record,
            )
            if duplicate_event["event_id"] not in existing_event_ids:
                new_events.append(duplicate_event)
                existing_event_ids.add(str(duplicate_event["event_id"]))
            duplicate_factor_ids.append(factor_id)
            continue

        matched_factor_id = record.matched_factor_id
        matched_record = active_records.get(str(matched_factor_id))
        if matched_record is None:
            raise ValueError(
                f"replace_candidate requires matched active factor; missing factor_id={matched_factor_id}"
            )

        replaced_event = _event_record(
            event_type="factor_replaced",
            factor_id=str(matched_factor_id),
            previous_status="active",
            new_status="replaced",
            reason="replaced_by_stronger_candidate",
            record=record,
            replaced_by_factor_id=factor_id,
        )
        admitted_event = _event_record(
            event_type="factor_admitted",
            factor_id=factor_id,
            previous_status=None,
            new_status="active",
            reason="replace_candidate_admitted",
            record=record,
            replaces_factor_id=str(matched_factor_id),
        )
        for event in (replaced_event, admitted_event):
            if event["event_id"] not in existing_event_ids:
                new_events.append(event)
                existing_event_ids.add(str(event["event_id"]))
        active_records.pop(str(matched_factor_id), None)
        active_records[factor_id] = {"factor_id": factor_id}
        admitted_factor_ids.append(factor_id)
        replaced_factor_ids.append(str(matched_factor_id))

    for event in new_events:
        _append_jsonl(paths["events"], event)
    rebuild_asset_store(asset_store_dir)
    return AssetIngestSummary(
        source_run_id=source_run_id,
        admitted_factor_ids=tuple(admitted_factor_ids),
        replaced_factor_ids=tuple(replaced_factor_ids),
        retired_factor_ids=tuple(retired_factor_ids),
        duplicate_factor_ids=tuple(duplicate_factor_ids),
        rejected_factor_ids=tuple(rejected_factor_ids),
    )


def retire_factor(
    asset_store_dir: str | Path,
    *,
    factor_id: str,
    source_run_id: str,
    reason: str = "manual_retire",
    created_at: str | None = None,
) -> None:
    """退役 active 因子: 只改状态，不删除值文件。"""

    record = get_factor_record(asset_store_dir, factor_id)
    if record is None or record.get("status") != "active":
        raise ValueError(f"retire_factor requires an active factor: {factor_id}")

    candidate_record = AssetCandidateRecord(
        decision="retire",
        candidate_payload={
            "candidate_id": factor_id,
            "expression": record.get("expression"),
            "category": record.get("category"),
            "economic_rationale": record.get("economic_rationale"),
            "metrics": record.get("admission_metrics", {}),
        },
        run_payload={
            "run_id": source_run_id,
            "created_at": created_at or record.get("updated_at") or record.get("created_at"),
            "source_universe_key": None,
            "forward_return_definition": None,
            "sample_protocol_hash": None,
            "preprocess_config_hash": None,
            "engine_version": None,
        },
        matched_factor_id=None,
        reject_reason=None,
    )
    paths = _asset_paths(asset_store_dir)
    event = _event_record(
        event_type="factor_retired",
        factor_id=factor_id,
        previous_status="active",
        new_status="retired",
        reason=reason,
        record=candidate_record,
    )
    existing_ids = {str(row["event_id"]) for row in _read_jsonl(paths["events"])}
    if event["event_id"] not in existing_ids:
        _append_jsonl(paths["events"], event)
    rebuild_asset_store(asset_store_dir)
