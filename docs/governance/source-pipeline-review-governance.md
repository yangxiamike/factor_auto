# Source Pipeline Review 维护制度

日期：2026-06-24

## 1. 这份文档解决什么问题

`source pipeline review` 不是普通 run 日志。

它解决的是：

- 这份 dataset 到底来自哪条上游数据流水线
- `source_universe_key` 对应什么业务口径
- 哪些基础过滤在上游做，哪些逻辑在本仓做
- 当前还有哪些 PIT（point-in-time，当时可见）风险没关掉
- 当 source pipeline 变化时，谁负责更新这份说明

如果没有这套制度，后续很容易出现：

- 同样叫 `sandbox_v1`，但上游口径已经变了
- 数据 warning 已经出现，但没人回头补 source review
- agent 知道要查问题，却不知道该更新哪份文档
- run manifest 只能看到 `source_path`，看不到审计结论

## 2. 这份制度的定位

这是一份轻量维护说明。

它的作用是：

- 帮 agent 知道什么时候该补 source review
- 帮人知道这份 review 是拿来审查什么的
- 帮 run 保留最基本的来源追溯

它不是：

- 每次 run 都写一份的新日志
- 某个 agent 的私人记忆
- 让 agent 全权判断数据逻辑是否合理的系统

## 3. 角色分工

### 3.1 人负责什么

人负责：

- 判断当前 review 是否过期
- 判断是否需要新开 review 文档
- 审核 agent 起草的更新
- 决定 `review_status`

### 3.2 Agent

agent 负责：

- 发现触发条件
- 读取上游和本仓代码
- 起草或更新 review 文档
- 把异常和未确认项写出来，方便人复核

agent 不负责：

- 擅自把未确认事项写成“已关闭风险”
- 为每次 run 自动重写 review
- 代替人做最终业务判断

## 4. review 文档放哪里

具体 review 文档放在：

```text
docs/data/source-pipeline-review-*.md
```

例如：

```text
docs/data/source-pipeline-review-zer0share-mining-v1.md
```

命名建议：

- 如果同一条上游 pipeline 服务多个 profile，但口径基本一致，可以按 pipeline + profile 写
- 如果不同 universe 差异很大，可以按 universe 单独拆文档

不要为每次普通 run 新建一份 review 文档。

## 5. 什么时候必须检查是否更新

以下场景必须检查 `source pipeline review` 是否需要更新。

### 5.1 新 universe

例如：

- 新 `source_universe_key`
- 从 `univ_trade_zz500` 扩到 `univ_trade_hs300`
- 从 sandbox profile 扩到新的 mining profile

### 5.2 上游 pipeline 逻辑变化

例如：

- universe 构造逻辑变化
- ST / 停牌 / 一字涨跌停 / 流动性过滤变化
- 行业来源变化
- 市值来源变化
- 复权因子来源或口径变化
- 交易日历来源变化

### 5.3 本仓 prepare 逻辑变化

例如：

- 后复权 OHLC 生成逻辑变化
- industry join 逻辑变化
- forward return 定义变化
- manifest 写法变化

### 5.4 data quality 出现结构性 warning / fail

例如：

- universe 数量异常低
- 某一段时间 `in_universe` 接近 0
- forward return 覆盖异常
- 暴露字段大面积缺失

这种场景至少要回头核对：

- 问题是上游 source pipeline 导致的
- 还是本仓 prepare / freeze 过程导致的

### 5.5 严肃协议上线前

例如：

- `mining_v1` 首次启用前
- 新 sample protocol 上线前
- 新 acceptance gate 接 OOS / walk-forward 前

## 6. 什么时候不需要更新

以下情况通常不需要更新：

- 普通 evaluate run
- 新 run_id
- 候选因子变化
- registry 变化
- metrics 结果变化，但数据来源没变

这些情况只需要在 run manifest 里引用当前 review，不需要重写 review 文档。

## 7. 标准维护流程

建议固定为 5 步：

1. agent 先判断是否已存在对应 review 文档
2. 如果已有文档，优先更新；只有差异明显时才新建
3. agent 起草这次变化、已确认项、未确认风险和建议 manifest 字段
4. 人审核并确认 `review_status`
5. dataset manifest 或 run manifest 引用对应 `review_doc`

## 8. review 文档最低应包含什么

每份 review 文档至少要回答：

- 上游路径是什么
- `source_universe_key` 对应什么业务口径
- 哪些基础过滤在上游做
- 哪些逻辑还在本仓做
- 当前行业 / 市值 / 复权 / 交易日历来源是什么
- 当前已确认哪些 PIT 事项
- 当前还没关掉哪些 PIT 风险
- 建议 manifest 写哪些 source pipeline 字段

## 9. review 状态怎么写

建议统一使用这些状态：

- `reviewed`
  - 已审查，且当前没有明显未关闭风险
- `reviewed_with_open_risks`
  - 已审查，但还有待确认风险
- `needs_refresh`
  - 上游或本仓逻辑已变，旧 review 可能过期

如果没有人最终确认，默认不要写成 `reviewed`。

## 10. manifest 应怎么引用

建议 dataset manifest 或 run manifest 至少预留：

```json
{
  "source_pipeline": {
    "name": "zer0share_daily_equity_pipeline",
    "review_doc": "docs/data/source-pipeline-review-zer0share-mining-v1.md",
    "review_status": "reviewed_with_open_risks",
    "reviewed_at": "2026-06-24"
  }
}
```

这样做的目的不是让每次 run 重复写长文，而是让每次 run 都能追溯到当前被认可的审查结论。

## 11. 和 AGENTS.md 的关系

这份文档是正式制度正文。

仓库根目录 `AGENTS.md` 只应保留短规则：

- 什么时候要检查 source pipeline review
- agent 负责起草，不负责最终拍板
- 具体制度看本文件

这样可以让：

- `AGENTS.md` 保持短、能扫读
- `docs/governance/` 保持正式、能审计

## 12. 当前执行建议

当前仓库建议采用下面的方式：

- 正式制度：`docs/governance/source-pipeline-review-governance.md`
- 当前事实：`docs/data/source-pipeline-review-zer0share-mining-v1.md`
- agent 入口规则：仓库根目录 `AGENTS.md`

## 13. 最终原则

这件事的成功标准不是“多写一份文档”，而是：

```text
有人负责看
触发条件清楚
agent 知道什么时候起草
人知道什么时候确认
run 能追溯到当前认可的 source review
```

只有做到这些，`source pipeline review` 才会变成可持续维护的制度，而不是一次性产物。
